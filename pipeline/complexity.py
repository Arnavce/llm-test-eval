"""Cyclomatic-complexity measurement for the CPB-6 benchmark (RADON)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import ProjectPaths, run_command

try:  # pragma: no cover - exercised implicitly when radon is installed
    from radon.complexity import cc_visit
    from radon.visitors import Class
except ImportError:  # pragma: no cover - fallback for minimal environments
    cc_visit = None  # type: ignore[assignment]
    Class = None  # type: ignore[assignment,misc]


@dataclass
class FunctionComplexity:
    """Complexity of a single function or class block."""

    name: str
    complexity: int
    lineno: int
    kind: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "complexity": self.complexity,
            "lineno": self.lineno,
            "kind": self.kind,
        }


@dataclass
class ModuleComplexity:
    """Aggregate complexity metrics for one module."""

    module: str
    path: str
    average: float
    maximum: int
    total: int
    functions: list[FunctionComplexity] = field(default_factory=list)
    source: str = "radon"

    def as_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "path": self.path,
            "average_complexity": self.average,
            "max_complexity": self.maximum,
            "total_complexity": self.total,
            "functions": [f.as_dict() for f in self.functions],
            "source": self.source,
        }


class ComplexityAnalyzer:
    """Computes average and maximum cyclomatic complexity per benchmark module.

    The primary path shells out to ``radon cc -j`` (the canonical CLI form
    required by the study protocol).  If the ``radon`` executable is not on
    ``PATH`` -- for example when the project is run through ``python -m`` in an
    environment where scripts live outside ``PATH`` -- the analyzer falls back
    to the ``radon`` Python API and finally to an internal McCabe counter, and
    records which mechanism was used in the ``source`` field.
    """

    def __init__(self, paths: ProjectPaths, modules: list[str] | None = None) -> None:
        self.paths = paths
        self.modules = modules or [
            path.stem
            for path in sorted(paths.benchmark_dir.glob("m*.py"))
            if not path.stem.startswith("__")
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def analyze_all(self) -> dict[str, ModuleComplexity]:
        """Return ``{module_name: ModuleComplexity}`` for every benchmark module."""
        results: dict[str, ModuleComplexity] = {}
        for module in self.modules:
            source_path = self.paths.benchmark_source(module)
            if not source_path.is_file():
                raise FileNotFoundError(f"benchmark module not found: {source_path}")
            results[module] = self.analyze_module(module)
        return results

    def analyze_module(self, module: str) -> ModuleComplexity:
        """Measure one module, trying the CLI, the API, then the fallback."""
        source_path = self.paths.benchmark_source(module)
        cli = self._via_radon_cli(source_path)
        if cli is not None:
            return self._build(module, source_path, cli, source="radon.cc_cli")
        api = self._via_radon_api(source_path)
        if api is not None:
            return self._build(module, source_path, api, source="radon.cc_api")
        fallback = self._via_ast_fallback(source_path)
        return self._build(module, source_path, fallback, source="ast_fallback")

    def to_rows(self) -> list[dict[str, Any]]:
        """One flat row per module, convenient for CSV/analysis consumers."""
        return [item.as_dict() for item in self.analyze_all().values()]

    # ------------------------------------------------------------------
    # Radon CLI
    # ------------------------------------------------------------------
    def _via_radon_cli(self, source_path: Path) -> list[dict[str, Any]] | None:
        executable = shutil.which("radon")
        if executable is None:
            maybe = Path(sys.executable).parent / "radon"
            executable = str(maybe) if maybe.is_file() else None
        if executable is None:
            return None
        result = run_command(
            [executable, "cc", "-j", str(source_path)],
            timeout=120,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        return self._flatten_radon_payload(payload, source_path)

    # ------------------------------------------------------------------
    # Radon API
    # ------------------------------------------------------------------
    def _via_radon_api(self, source_path: Path) -> list[dict[str, Any]] | None:
        if cc_visit is None:
            return None
        try:
            source = source_path.read_text(encoding="utf-8")
            blocks = cc_visit(source)
        except (OSError, SyntaxError, ValueError):
            return None
        rows: list[dict[str, Any]] = []
        for block in blocks:
            kind = "class" if Class is not None and isinstance(block, Class) else "function"
            rows.append(
                {
                    "name": block.name,
                    "complexity": int(block.complexity),
                    "lineno": int(block.lineno),
                    "kind": kind,
                }
            )
        return rows

    def _flatten_radon_payload(
        self, payload: Any, source_path: Path
    ) -> list[dict[str, Any]]:
        """Normalise ``radon cc -j`` output (keyed by path) into flat rows."""
        if isinstance(payload, dict):
            entries: Any = payload.get(str(source_path), payload)
            if isinstance(entries, dict):
                # Older radon versions key by path but may nest differently.
                collected: list[dict[str, Any]] = []
                for value in entries.values():
                    if isinstance(value, list):
                        collected.extend(value)
                entries = collected
        else:
            entries = payload
        if not isinstance(entries, list):
            return []
        rows: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            rows.append(
                {
                    "name": str(entry.get("name", "<anonymous>")),
                    "complexity": int(entry.get("complexity", 1)),
                    "lineno": int(entry.get("lineno", 0)),
                    "kind": str(entry.get("type", "function")).lower(),
                }
            )
        return rows

    # ------------------------------------------------------------------
    # Pure-Python fallback (no radon installed)
    # ------------------------------------------------------------------
    def _via_ast_fallback(self, source_path: Path) -> list[dict[str, Any]]:
        """A conservative McCabe counter used only when radon is unavailable."""
        import ast

        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            return []

        decision_nodes = (
            ast.If,
            ast.For,
            ast.AsyncFor,
            ast.While,
            ast.ExceptHandler,
            ast.With,
            ast.AsyncWith,
            ast.Assert,
            ast.IfExp,
            ast.comprehension,
            ast.BoolOp,
        )

        def complexity_of(node: ast.AST) -> int:
            score = 1
            stack = list(ast.iter_child_nodes(node))
            while stack:
                current = stack.pop()
                if isinstance(current, decision_nodes):
                    score += 1
                stack.extend(ast.iter_child_nodes(current))
            return score

        rows: list[dict[str, Any]] = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                rows.append(
                    {
                        "name": node.name,
                        "complexity": complexity_of(node),
                        "lineno": node.lineno,
                        "kind": kind,
                    }
                )
        return rows

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------
    def _build(
        self,
        module: str,
        source_path: Path,
        rows: list[dict[str, Any]],
        source: str,
    ) -> ModuleComplexity:
        functions = [
            FunctionComplexity(
                name=row["name"],
                complexity=row["complexity"],
                lineno=row["lineno"],
                kind=row["kind"],
            )
            for row in rows
        ]
        valid = [item.complexity for item in functions]
        average = round(sum(valid) / len(valid), 4) if valid else 0.0
        maximum = max(valid) if valid else 0
        display_path = source_path
        try:
            display_path = source_path.resolve().relative_to(self.paths.root)
        except (ValueError, OSError):
            pass
        return ModuleComplexity(
            module=module,
            path=display_path.as_posix(),
            average=average,
            maximum=maximum,
            total=sum(valid),
            functions=functions,
            source=source,
        )


def write_complexity_report(
    complexities: dict[str, ModuleComplexity],
    output_dir: Path,
) -> Path:
    """Write a JSON report and return its path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "complexity_report.json"
    payload = {
        "generated_by": "pipeline.complexity",
        "modules": {
            name: item.as_dict() for name, item in sorted(complexities.items())
        },
    }
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return destination


def format_complexity_table(complexities: dict[str, ModuleComplexity]) -> str:
    """Render a compact plain-text summary for the CLI."""
    lines = ["Complexity (radon CC):", f"{'module':<18}{'avg':>7}{'max':>6}{'blocks':>8}"]
    for name, item in sorted(complexities.items()):
        lines.append(
            f"{name:<18}{item.average:>7.2f}{item.maximum:>6d}{len(item.functions):>8d}"
        )
    return "\n".join(lines)


def radon_available() -> bool:
    """Whether the radon package can be imported."""
    return cc_visit is not None


__all__ = [
    "ComplexityAnalyzer",
    "FunctionComplexity",
    "ModuleComplexity",
    "format_complexity_table",
    "radon_available",
    "write_complexity_report",
]
