"""Instrumented evaluation of a pytest suite against one benchmark module.

The evaluator answers four of the study's measurement questions for a single
``(module, suite)`` pair:

* **Collection** -- can pytest import and collect the suite at all?
* **Execution** -- how many tests pass, fail or error, and how long does it take?
* **Coverage** -- line and branch coverage of the benchmark module.
* **Mutation score** -- how many single-point source mutants are detected?

Mutation testing is implemented with a self-contained AST engine rather than
the ``mutmut`` CLI: mutants are generated deterministically from the module's
abstract syntax tree, each one is written into an isolated copy of the
``benchmark`` package together with the suite under test, and pytest is run in
a fresh subprocess.  This makes every measurement reproducible and avoids
``mutmut``'s on-disk cache, which is version-specific and hard to reuse across
many short-lived suites.  ``mutmut`` is still installed by ``requirements.txt``
and can be used for independent cross-checks of the engine's output.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from .config import (
    ProjectPaths,
    RESULT_COLUMNS,
    CommandResult,
    python_executable,
    run_command,
    truncate,
)

# ---------------------------------------------------------------------------
# Regexes for parsing pytest / coverage output
# ---------------------------------------------------------------------------
_PASSED_RE = re.compile(r"(\d+) passed")
_FAILED_RE = re.compile(r"(\d+) failed")
_ERROR_RE = re.compile(r"(\d+) errors?")
_SKIPPED_RE = re.compile(r"(\d+) skipped")
_DURATION_RE = re.compile(r"in (\d+(?:\.\d+)?)s")

_TOTAL_TESTS_RE = re.compile(r"collected (\d+) items?")

assertion_like = "AssertionError"
_runtime_error_re = re.compile(
    r"\b(?:RuntimeError|TypeError|ValueError|KeyError|IndexError|AttributeError|"
    r"ZeroDivisionError|NameError|RecursionError|MemoryError|OverflowError)\b"
)
_timeout_like = re.compile(r"timeout|timed out", re.IGNORECASE)

#: Mutation operators: AST node type -> {operator: [replacements]}.
MUTATION_OPERATORS: dict[str, dict[str, tuple[str, ...]]] = {
    "arithmetic": {
        "+": ("-",),
        "-": ("+",),
        "*": ("/",),
        "/": ("*",),
        "//": ("/",),
        "%": ("*",),
    },
    "comparison": {
        "<": ("<=",),
        "<=": ("<",),
        ">": (">=",),
        ">=": (">",),
        "==": ("!=",),
        "!=": ("==",),
    },
    "boolean": {
        "and": ("or",),
        "or": ("and",),
    },
}

_BINOP_SYMBOLS: dict[type[ast.operator], str] = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.FloorDiv: "//",
    ast.Mod: "%",
}

_CMPOP_SYMBOLS: dict[type[ast.cmpop], str] = {
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.In: "in",
    ast.NotIn: "not in",
    ast.Is: "is",
    ast.IsNot: "is not",
}

_BOOLOP_SYMBOLS: dict[type[ast.boolop], str] = {
    ast.And: "and",
    ast.Or: "or",
}


# ---------------------------------------------------------------------------
# Mutation engine
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Mutation:
    """A single-point source mutation."""

    line: int
    col: int
    original: str
    replacement: str
    operator: str
    function: str

    @property
    def mutant_id(self) -> str:
        """Stable identifier used in logs and reports."""
        return f"L{self.line}:C{self.col}:{self.operator}:{self.original}->{self.replacement}"


@dataclass(frozen=True)
class MutantVerdict:
    """Outcome of running the suite against one mutant."""

    mutation: Mutation
    killed: bool
    status: str  # killed | survived | timeout | invalid | error
    detail: str = ""


class MutationEngine:
    """Deterministic AST-based single-point mutation generator/evaluator."""

    def __init__(
        self,
        timeout_per_mutant: float = 20.0,
        max_mutants: int | None = None,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        self.timeout_per_mutant = timeout_per_mutant
        self.max_mutants = max_mutants
        self.log = logger or (lambda message: None)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------
    def find_mutations(self, source: str) -> list[Mutation]:
        """Return the deterministic list of mutations for ``source``."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        found: list[Mutation] = []
        for node in ast.walk(tree):
            function = self._enclosing_function(node, parents)
            if isinstance(node, ast.BinOp):
                self._collect_binary(node, function, source, found)
            elif isinstance(node, ast.Compare):
                self._collect_comparison(node, function, source, found)
            elif isinstance(node, ast.BoolOp):
                self._collect_boolean(node, function, source, found)
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
                self._collect_not(node, function, source, found)
            elif (
                isinstance(node, ast.Return)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, bool)
            ):
                found.append(
                    Mutation(
                        line=node.value.lineno,
                        col=node.value.col_offset,
                        original="True" if node.value.value else "False",
                        replacement="False" if node.value.value else "True",
                        operator="boolean_literal",
                        function=function,
                    )
                )

        unique: dict[tuple[int, int, str, str], Mutation] = {}
        for mutation in found:
            key = (mutation.line, mutation.col, mutation.original, mutation.replacement)
            unique.setdefault(key, mutation)
        ordered = sorted(
            unique.values(), key=lambda item: (item.line, item.col, item.replacement)
        )
        if self.max_mutants is not None:
            ordered = ordered[: max(0, self.max_mutants)]
        return ordered

    def _collect_binary(
        self,
        node: ast.BinOp,
        function: str,
        source: str,
        found: list[Mutation],
    ) -> None:
        symbol = _BINOP_SYMBOLS.get(type(node.op))
        if symbol is None:
            return
        located = self._find_operator_between(source, node.left, node.right, (symbol,))
        if located is None:
            return
        line, col, operator = located
        for replacement in MUTATION_OPERATORS["arithmetic"].get(operator, ()):
            found.append(
                Mutation(
                    line=line,
                    col=col,
                    original=operator,
                    replacement=replacement,
                    operator="arithmetic",
                    function=function,
                )
            )

    def _collect_comparison(
        self,
        node: ast.Compare,
        function: str,
        source: str,
        found: list[Mutation],
    ) -> None:
        if self._is_identity_none(node):
            return
        operands = [node.left, *node.comparators]
        for index, op in enumerate(node.ops):
            symbol = _CMPOP_SYMBOLS.get(type(op))
            if symbol is None:
                continue
            located = self._find_operator_between(
                source, operands[index], operands[index + 1], (symbol,)
            )
            if located is None:
                continue
            line, col, operator = located
            for replacement in MUTATION_OPERATORS["comparison"].get(operator, ()):
                found.append(
                    Mutation(
                        line=line,
                        col=col,
                        original=operator,
                        replacement=replacement,
                        operator="comparison",
                        function=function,
                    )
                )

    def _collect_boolean(
        self,
        node: ast.BoolOp,
        function: str,
        source: str,
        found: list[Mutation],
    ) -> None:
        symbol = _BOOLOP_SYMBOLS.get(type(node.op))
        if symbol is None:
            return
        for left, right in zip(node.values, node.values[1:]):
            located = self._find_operator_between(source, left, right, (symbol,))
            if located is None:
                continue
            line, col, operator = located
            for replacement in MUTATION_OPERATORS["boolean"].get(operator, ()):
                found.append(
                    Mutation(
                        line=line,
                        col=col,
                        original=operator,
                        replacement=replacement,
                        operator="boolean",
                        function=function,
                    )
                )

    def _collect_not(
        self,
        node: ast.UnaryOp,
        function: str,
        source: str,
        found: list[Mutation],
    ) -> None:
        line_text = source.splitlines()[node.lineno - 1] if node.lineno <= len(source.splitlines()) else ""
        segment = line_text[node.col_offset :]
        token = "not"
        if not segment.startswith(token):
            return
        after = segment[len(token) : len(token) + 1]
        if after and after not in " ([":
            return
        found.append(
            Mutation(
                line=node.lineno,
                col=node.col_offset,
                original=token,
                replacement="",
                operator="negation",
                function=function,
            )
        )

    @staticmethod
    def _find_operator_between(
        source: str,
        left: ast.AST,
        right: ast.AST,
        candidates: tuple[str, ...],
    ) -> tuple[int, int, str] | None:
        """Locate the unique operator token between two same-line operands.

        Returns ``(line, column, token)`` or ``None`` when the operands span
        lines, the slice is ambiguous, or no candidate token is present.
        """
        if left.lineno != right.lineno or left.end_lineno != right.lineno:
            return None
        line_text = source.splitlines()[left.end_lineno - 1]
        start = left.end_col_offset or 0
        end = right.col_offset if right.col_offset is not None else len(line_text)
        if start > end:
            return None
        segment = line_text[start:end]
        unique: list[tuple[int, str]] = []
        for token in candidates:
            index = segment.find(token)
            if index >= 0 and segment.find(token, index + len(token)) < 0:
                unique.append((start + index, token))
        if len(unique) != 1:
            # Zero hits means the token is written differently (e.g. "is not");
            # several hits means the slice is ambiguous and must be skipped.
            return None
        position, token = unique[0]
        return left.lineno, position, token

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    def apply(self, source: str, mutation: Mutation) -> str | None:
        """Apply ``mutation`` to ``source``; return ``None`` if impossible."""
        lines = source.splitlines(keepends=True)
        if mutation.line < 1 or mutation.line > len(lines):
            return None
        original_line = lines[mutation.line - 1]
        col = mutation.col
        if col > len(original_line):
            return None
        token = mutation.original
        if mutation.operator == "negation":
            segment = original_line[col:].lstrip()
            if not segment.startswith("not"):
                return None
            offset = len(original_line[col:]) - len(segment)
            start = col + offset
            end = start + 3
            remainder = original_line[end:]
            if not (remainder.startswith(" ") or remainder.startswith("(")):
                return None
            new_line = original_line[:start] + remainder.lstrip(" ")
            lines[mutation.line - 1] = new_line
        else:
            if original_line[col : col + len(token)] != token:
                return None
            after = original_line[col + len(token) : col + len(token) + 1]
            if after and not (after.isspace() or after in ")]},:"):
                return None
            prefix = original_line[:col]
            suffix = original_line[col + len(token) :]
            replacement = mutation.replacement
            # ``<=`` -> ``<`` already ends with a space-safe prefix; adding one
            # would turn ``x < = 1`` into a syntax error.
            shrinking = bool(replacement) and replacement in token
            needs_space = (
                bool(suffix)
                and not suffix[0].isspace()
                and suffix[0] not in ")]},:"
                and not shrinking
            )
            if needs_space:
                replacement = replacement + " "
            lines[mutation.line - 1] = prefix + replacement + suffix

        mutant = "".join(lines)
        try:
            compile(mutant, "<mutant>", "exec")
        except SyntaxError:
            return None
        return mutant

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    def evaluate(
        self,
        project_root: Path,
        module: str,
        source_path: Path,
        test_file: Path,
    ) -> list[MutantVerdict]:
        """Run ``test_file`` against every mutant of ``source_path``."""
        source = source_path.read_text(encoding="utf-8")
        mutations = self.find_mutations(source)
        verdicts: list[MutantVerdict] = []
        benchmark_dir = project_root / "benchmark"
        for mutation in mutations:
            mutant_source = self.apply(source, mutation)
            if mutant_source is None:
                verdicts.append(
                    MutantVerdict(
                        mutation=mutation,
                        killed=False,
                        status="invalid",
                        detail="mutation could not be applied safely",
                    )
                )
                continue
            status, detail = self._run_mutant(
                project_root=project_root,
                benchmark_dir=benchmark_dir,
                module=module,
                mutant_source=mutant_source,
                test_file=test_file,
            )
            verdicts.append(
                MutantVerdict(
                    mutation=mutation,
                    killed=status in {"killed", "timeout"},
                    status=status,
                    detail=detail,
                )
            )
        return verdicts

    def _run_mutant(
        self,
        project_root: Path,
        benchmark_dir: Path,
        module: str,
        mutant_source: str,
        test_file: Path,
    ) -> tuple[str, str]:
        with tempfile.TemporaryDirectory(prefix=f"mutant_{module}_") as temporary:
            sandbox = Path(temporary)
            package_dir = sandbox / "benchmark"
            package_dir.mkdir(parents=True, exist_ok=True)
            init_file = benchmark_dir / "__init__.py"
            if init_file.is_file():
                shutil.copy2(init_file, package_dir / "__init__.py")
            (package_dir / f"{module}.py").write_text(mutant_source, encoding="utf-8")
            destination_test = sandbox / test_file.name
            shutil.copy2(test_file, destination_test)

            result = run_command(
                [
                    python_executable(),
                    "-m",
                    "pytest",
                    destination_test.name,
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "--rootdir",
                    str(sandbox),
                    "--basetemp",
                    str(sandbox / ".pytest_tmp"),
                ],
                cwd=sandbox,
                timeout=self.timeout_per_mutant,
                env={
                    "PYTHONPATH": str(sandbox),
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
            )
        if result.timed_out:
            return "timeout", "suite exceeded the per-mutant timeout"
        if result.returncode == 0:
            return "survived", "mutant not detected by any test"
        if result.returncode == 5:
            return "survived", "no tests were collected"
        if "SyntaxError" in result.output or "ImportError" in result.output:
            return "invalid", truncate(result.output, 300)
        if _timeout_like.search(result.output):
            return "timeout", "suite reported a timeout"
        return "killed", "mutant detected by at least one failing test"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _enclosing_function(
        node: ast.AST, parents: dict[ast.AST, ast.AST]
    ) -> str:
        current: ast.AST | None = node
        while current is not None:
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return current.name
            current = parents.get(current)
        return "<module>"

    @staticmethod
    def _is_identity_none(node: ast.Compare) -> bool:
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, (ast.Is, ast.IsNot)):
                if isinstance(comparator, ast.Constant) and comparator.value is None:
                    return True
        return False

    @staticmethod
    def _is_single_token(source: str, left: ast.AST, right: ast.AST, token: str) -> bool:
        if left.lineno != right.lineno:
            return False
        source_lines = source.splitlines()
        line_index = (left.end_lineno or left.lineno) - 1
        if line_index < 0 or line_index >= len(source_lines):
            return False
        line = source_lines[line_index]
        start = left.end_col_offset or 0
        end = right.col_offset if right.col_offset is not None else len(line)
        return token in line[start:end]


# ---------------------------------------------------------------------------
# Suite descriptors and results
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SuiteDescriptor:
    """Identifies a test suite to evaluate."""

    module: str
    suite: str
    run_id: int
    generation_mode: str
    test_file: Path


@dataclass
class SuiteResult:
    """All measurements for one ``(module, suite)`` pair."""

    module: str
    suite: str
    run_id: int
    generation_mode: str
    test_file: str
    collection_success: bool = False
    execution_success: bool = False
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    execution_time_s: float = 0.0
    line_coverage: float | None = None
    branch_coverage: float | None = None
    combined_coverage: float | None = None
    avg_complexity: float | None = None
    max_complexity: int | None = None
    total_mutants: int = 0
    killed_mutants: int = 0
    survived_mutants: int = 0
    timeout_mutants: int = 0
    invalid_mutants: int = 0
    mutation_score: float | None = None
    failure_category: str = "None"
    tests_per_kloc: float | None = None
    assertions_per_test: float | None = None
    generated_loc: int = 0
    error_message: str = ""
    notes: str = ""
    mutation_verdicts: list[MutantVerdict] = field(default_factory=list, repr=False)

    def as_row(self) -> dict[str, Any]:
        """Return a CSV-friendly row with a stable column order."""
        mapping = {
            "module": self.module,
            "suite": self.suite,
            "run_id": self.run_id,
            "generation_mode": self.generation_mode,
            "test_file": self.test_file,
            "collection_success": self.collection_success,
            "execution_success": self.execution_success,
            "total_tests": self.total_tests,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "skipped": self.skipped,
            "execution_time_s": round(self.execution_time_s, 4),
            "line_coverage": _round_or_none(self.line_coverage),
            "branch_coverage": _round_or_none(self.branch_coverage),
            "combined_coverage": _round_or_none(self.combined_coverage),
            "avg_complexity": _round_or_none(self.avg_complexity),
            "max_complexity": self.max_complexity,
            "total_mutants": self.total_mutants,
            "killed_mutants": self.killed_mutants,
            "survived_mutants": self.survived_mutants,
            "timeout_mutants": self.timeout_mutants,
            "invalid_mutants": self.invalid_mutants,
            "mutation_score": _round_or_none(self.mutation_score),
            "failure_category": self.failure_category,
            "tests_per_kloc": _round_or_none(self.tests_per_kloc),
            "assertions_per_test": _round_or_none(self.assertions_per_test),
            "generated_loc": self.generated_loc,
            "error_message": self.error_message,
            "notes": self.notes,
        }
        return {column: mapping[column] for column in RESULT_COLUMNS}


@dataclass
class EvaluationSettings:
    """Timeouts and toggles for :class:`TestEvaluator`."""

    skip_mutation: bool = False
    collection_timeout: float = 120.0
    execution_timeout: float = 180.0
    coverage_timeout: float = 240.0
    mutation_timeout: float = 20.0
    max_mutants: int | None = None

    def __post_init__(self) -> None:
        for name in (
            "collection_timeout",
            "execution_timeout",
            "coverage_timeout",
            "mutation_timeout",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------
class TestEvaluator:
    """Runs the full measurement protocol for a single test suite."""

    def __init__(
        self,
        paths: ProjectPaths,
        complexities: dict[str, Any] | None = None,
        settings: EvaluationSettings | None = None,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        self.paths = paths
        self.complexities = complexities or {}
        self.settings = settings or EvaluationSettings()
        self.log = logger or (lambda message: None)
        self.mutation_engine = MutationEngine(
            timeout_per_mutant=self.settings.mutation_timeout,
            max_mutants=self.settings.max_mutants,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def evaluate(self, descriptor: SuiteDescriptor) -> SuiteResult:
        """Measure one suite and return a fully populated :class:`SuiteResult`."""
        test_file = Path(descriptor.test_file)
        relative_test = _relative(test_file, self.paths.root)
        result = SuiteResult(
            module=descriptor.module,
            suite=descriptor.suite,
            run_id=descriptor.run_id,
            generation_mode=descriptor.generation_mode,
            test_file=relative_test,
        )
        if not test_file.is_file():
            result.failure_category = "CollectionError"
            result.error_message = f"test file not found: {test_file}"
            return result

        try:
            code = test_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            result.failure_category = "CollectionError"
            result.error_message = f"cannot read test file: {exc}"
            return result
        result.generated_loc = len(code.splitlines())
        result.total_tests, result.assertions_per_test = _count_tests_and_assertions(code)

        complexity = self.complexities.get(descriptor.module)
        if complexity is not None:
            result.avg_complexity = float(complexity.average)
            result.max_complexity = int(complexity.maximum)

        # 1. Collection -------------------------------------------------
        collection = self._collect(test_file)
        result.collection_success = collection.returncode == 0 and not collection.timed_out
        if not result.collection_success:
            result.failure_category = self._classify_failure(
                collection, collected_ok=False, executed_ok=False, has_tests=False
            )
            result.error_message = truncate(self._sanitize(collection.output), 1200)
            return result

        # 2. Execution --------------------------------------------------
        execution = self._execute(test_file)
        result.execution_time_s = execution.duration_s
        summary = self._parse_pytest_summary(execution.output)
        result.passed = summary["passed"]
        result.failed = summary["failed"]
        result.errors = summary["errors"]
        result.skipped = summary["skipped"]
        result.total_tests = summary["total"] or result.total_tests
        result.execution_success = (
            execution.returncode == 0
            and not execution.timed_out
            and result.failed == 0
            and result.errors == 0
            and result.passed > 0
        )
        result.failure_category = self._classify_failure(
            execution,
            collected_ok=True,
            executed_ok=result.execution_success,
            has_tests=result.total_tests > 0,
        )
        if execution.timed_out:
            result.execution_time_s = execution.duration_s
            result.error_message = truncate(self._sanitize(execution.output), 1200)
            return result
        if not result.execution_success and not result.error_message:
            result.error_message = truncate(self._sanitize(execution.output), 1200)

        # 3. Coverage ---------------------------------------------------
        coverage = self._coverage(descriptor.module, test_file)
        result.line_coverage = coverage["line"]
        result.branch_coverage = coverage["branch"]
        result.combined_coverage = coverage["combined"]
        if coverage["error"]:
            result.notes = f"coverage: {self._sanitize(str(coverage['error']))}"

        # 4. Mutation testing ------------------------------------------
        if self.settings.skip_mutation:
            result.notes = _join_notes(result.notes, "mutation testing skipped")
            return result
        if not result.execution_success or result.total_tests == 0:
            result.notes = _join_notes(
                result.notes,
                "mutation testing skipped: suite did not pass cleanly",
            )
            return result

        verdicts = self.mutation_engine.evaluate(
            project_root=self.paths.root,
            module=descriptor.module,
            source_path=self.paths.benchmark_source(descriptor.module),
            test_file=test_file,
        )
        result.mutation_verdicts = verdicts
        viable = [v for v in verdicts if v.status != "invalid"]
        result.total_mutants = len(viable)
        result.invalid_mutants = sum(1 for v in verdicts if v.status == "invalid")
        result.killed_mutants = sum(1 for v in viable if v.status == "killed")
        result.survived_mutants = sum(1 for v in viable if v.status == "survived")
        result.timeout_mutants = sum(1 for v in viable if v.status == "timeout")
        if viable:
            result.mutation_score = round(
                (result.killed_mutants + result.timeout_mutants) / len(viable), 4
            )
        if not verdicts:
            result.notes = _join_notes(result.notes, "no viable mutants found")
        return result

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------
    def _sanitize(self, text: str) -> str:
        """Strip the absolute project root so artefacts stay portable.

        pytest occasionally prints absolute paths even when invoked with a
        relative test path; publishing those would leak the local filesystem
        layout, so every captured message goes through this filter.
        """
        root = str(self.paths.root)
        return text.replace(root + "/", "").replace(root, ".")

    def _collect(self, test_file: Path) -> CommandResult:
        root = self.paths.root
        display = _relative(test_file, root)
        return run_command(
            [
                python_executable(),
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                "-p",
                "no:cacheprovider",
                display,
            ],
            cwd=root,
            timeout=self.settings.collection_timeout,
            env={"PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def _execute(self, test_file: Path) -> CommandResult:
        root = self.paths.root
        display = _relative(test_file, root)
        return run_command(
            [
                python_executable(),
                "-m",
                "pytest",
                display,
                "-q",
                "-p",
                "no:cacheprovider",
                "-o",
                "addopts=",
            ],
            cwd=root,
            timeout=self.settings.execution_timeout,
            env={"PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def _coverage(self, module: str, test_file: Path) -> dict[str, Any]:
        """Measure coverage in an isolated copy of the benchmark package."""
        with tempfile.TemporaryDirectory(prefix=f"cov_{module}_") as temporary:
            sandbox = Path(temporary)
            package_dir = sandbox / "benchmark"
            package_dir.mkdir(parents=True, exist_ok=True)
            init_file = self.paths.benchmark_dir / "__init__.py"
            if init_file.is_file():
                shutil.copy2(init_file, package_dir / "__init__.py")
            shutil.copy2(
                self.paths.benchmark_source(module), package_dir / f"{module}.py"
            )
            destination_test = sandbox / test_file.name
            shutil.copy2(test_file, destination_test)
            data_file = sandbox / ".coverage"
            json_path = sandbox / "coverage.json"

            command = [
                python_executable(),
                "-m",
                "pytest",
                destination_test.name,
                "-q",
                "-p",
                "no:cacheprovider",
                "-o",
                "addopts=",
                f"--cov=benchmark.{module}",
                "--cov-branch",
                f"--cov-report=json:{json_path}",
                "--cov-report=term-missing",
                f"--cov-config={Path(__file__).resolve().parent / 'coverage.ini'}",
                f"--rootdir={sandbox}",
            ]
            result = run_command(
                command,
                cwd=sandbox,
                timeout=self.settings.coverage_timeout,
                env={
                    "PYTHONPATH": str(sandbox),
                    "COVERAGE_FILE": str(data_file),
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
            )
            if result.timed_out:
                return {"line": None, "branch": None, "combined": None, "error": "timeout"}
            if not json_path.is_file():
                return {
                    "line": None,
                    "branch": None,
                    "combined": None,
                    "error": truncate(result.output, 300),
                }
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                return {
                    "line": None,
                    "branch": None,
                    "combined": None,
                    "error": f"unreadable coverage JSON: {exc}",
                }
            return _extract_coverage(payload, module)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_pytest_summary(output: str) -> dict[str, int]:
        def grab(pattern: re.Pattern[str]) -> int:
            match = pattern.search(output)
            return int(match.group(1)) if match else 0

        passed = grab(_PASSED_RE)
        failed = grab(_FAILED_RE)
        errors = grab(_ERROR_RE)
        skipped = grab(_SKIPPED_RE)
        total_match = _TOTAL_TESTS_RE.search(output)
        total = int(total_match.group(1)) if total_match else passed + failed + errors
        return {
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "total": total,
        }

    def _classify_failure(
        self,
        result: CommandResult,
        collected_ok: bool,
        executed_ok: bool,
        has_tests: bool,
    ) -> str:
        if result.timed_out:
            return "Timeout"
        if not collected_ok:
            return "CollectionError"
        if executed_ok:
            return "None"
        output = result.output
        if not has_tests:
            return "CollectionError"
        if "ERROR collecting" in output or "errors during collection" in output:
            return "CollectionError"
        if "SyntaxError" in output or "ImportError" in output or "ModuleNotFoundError" in output:
            return "CollectionError"
        if assertion_like in output:
            return "AssertionFailure"
        if _runtime_error_re.search(output):
            return "RuntimeError"
        if result.returncode == 0:
            return "None"
        return "RuntimeError"


# ---------------------------------------------------------------------------
# Suite discovery helpers used by the CLI
# ---------------------------------------------------------------------------
def generated_descriptors(
    paths: ProjectPaths, modules: Iterable[str], runs: int
) -> list[SuiteDescriptor]:
    """Descriptors for mocked/API-generated suites, in stable order."""
    descriptors: list[SuiteDescriptor] = []
    for module in modules:
        for run_id in range(1, runs + 1):
            test_file = paths.generated_test(module, run_id)
            descriptors.append(
                SuiteDescriptor(
                    module=module,
                    suite=f"gen_{run_id}",
                    run_id=run_id,
                    generation_mode="generated",
                    test_file=test_file,
                )
            )
    return descriptors


def baseline_descriptors(paths: ProjectPaths, modules: Iterable[str]) -> list[SuiteDescriptor]:
    """Descriptors for the human ground-truth suites."""
    descriptors: list[SuiteDescriptor] = []
    for module in modules:
        test_file = paths.baseline_test(module)
        descriptors.append(
            SuiteDescriptor(
                module=module,
                suite="human_baseline",
                run_id=0,
                generation_mode="human",
                test_file=test_file,
            )
        )
    return descriptors


def _as_float(value: Any) -> float | None:
    """Coerce a JSON scalar to ``float`` without raising."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_coverage(payload: dict[str, Any], module: str) -> dict[str, Any]:
    """Pull line/branch/combined coverage for ``module`` out of coverage JSON."""
    files = payload.get("files", {})
    record: dict[str, Any] | None = None
    wanted = f"benchmark/{module}.py"
    for filename, data in files.items():
        normalised = filename.replace("\\", "/")
        if normalised == wanted or normalised.endswith("/" + wanted):
            record = data
            break
    if record is None and len(files) == 1:
        # Only one file was measured: use it even if the key is unusual.
        record = next(iter(files.values()))
    if not isinstance(record, dict):
        return {
            "line": 0.0,
            "branch": None,
            "combined": 0.0,
            "error": "module not imported by the suite",
        }
    if not record:
        return {
            "line": 0.0,
            "branch": 0.0,
            "combined": 0.0,
            "error": "module not imported by the suite",
        }
    summary = record.get("summary", {})
    line = _as_float(summary.get("percent_covered"))
    branch_total = summary.get("num_branches")
    branch_covered = summary.get("covered_branches")
    branch: float | None = None
    if isinstance(branch_total, (int, float)) and branch_total > 0:
        branch = round(100.0 * float(branch_covered or 0) / float(branch_total), 4)
    else:
        branch = 0.0
    combined: float | None = None
    if branch is not None:
        num_statements = float(summary.get("num_statements") or 0)
        missed_lines = float(summary.get("missing_lines") or 0)
        covered_lines = max(num_statements - missed_lines, 0.0)
        denominator = num_statements + float(branch_total)
        if denominator > 0:
            combined = round(
                100.0
                * (covered_lines + float(branch_covered or 0))
                / denominator,
                4,
            )
    return {"line": line, "branch": branch, "combined": combined, "error": ""}


def _count_tests_and_assertions(code: str) -> tuple[int, float | None]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0, None
    tests = 0
    assertions = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            tests += 1
            for inner in ast.walk(node):
                if isinstance(inner, ast.Assert):
                    assertions += 1
                elif isinstance(inner, ast.Call):
                    func = inner.func
                    if isinstance(func, ast.Attribute) and func.attr == "raises":
                        assertions += 1
    ratio = round(assertions / tests, 4) if tests else None
    return tests, ratio


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _round_or_none(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _join_notes(existing: str, note: str) -> str:
    return f"{existing}; {note}" if existing else note


__all__ = [
    "EvaluationSettings",
    "MUTATION_OPERATORS",
    "Mutation",
    "MutationEngine",
    "MutantVerdict",
    "SuiteDescriptor",
    "SuiteResult",
    "TestEvaluator",
    "baseline_descriptors",
    "generated_descriptors",
]
