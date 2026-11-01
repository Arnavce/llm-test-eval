"""Test-suite generation for the LLM test-quality study.

Two modes are supported:

``mock``
    Fully offline and deterministic.  For every benchmark module it emits one
    of five synthetic "LLM profiles" per run -- high quality, medium quality,
    low quality, wrong expectation and broken syntax -- so that the complete
    evaluation pipeline (collection, execution, coverage, mutation scoring and
    failure classification) can be exercised without an API key.

``api``
    Calls a hosted chat-completions endpoint (OpenAI, DeepSeek) or the Google
    Gemini ``generateContent`` endpoint using only the standard library.  The
    prompt is fixed so that every run sees an identical instruction and only
    the target source module varies.  Responses are de-fenced, syntax-checked
    and written to ``generated_tests/{module}_gen_{run_id}.py``.

Generated files are written atomically and the manifest
``generated_tests/manifest.json`` records the prompt, provider, model, token
usage and quality profile for reproducibility.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .config import ProjectPaths

#: Provider -> (base URL, default model, environment variable).
PROVIDERS: dict[str, tuple[str, str, str]] = {
    "openai": (
        "https://api.openai.com/v1",
        "gpt-4o-mini",
        "OPENAI_API_KEY",
    ),
    "deepseek": (
        "https://api.deepseek.com/v1",
        "deepseek-chat",
        "DEEPSEEK_API_KEY",
    ),
    "gemini": (
        "https://generativelanguage.googleapis.com/v1beta",
        "gemini-2.5-flash",
        "GEMINI_API_KEY",
    ),
}

#: Provider -> environment variables that may hold the key, in priority order.
API_KEY_ENV: dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY",),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
}

#: The fixed generation prompt.  ``{source}`` is the only substitution.
GENERATION_PROMPT: str = """You are an expert Python test engineer.

Write a complete, self-contained pytest test module for the Python source file below.

Requirements:
1. Use `from {module_path} import ...` (absolute import); do not redefine the code under test.
2. Cover every public function/class, all boundary values, and every documented exception.
3. Use `pytest.raises` for error paths and `pytest.approx` for float comparisons.
4. Do not use network, filesystem, GUI or third-party libraries other than pytest.
5. Return only the Python code for the test module, with no explanations.

Source file: {module_path}.py
```python
{source}
```
"""


class GenerationMode(str, Enum):
    """How suites are produced."""

    MOCK = "mock"
    API = "api"


class GenerationError(RuntimeError):
    """Raised when a live provider cannot produce a usable test module."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class GeneratedSuite:
    """A generated pytest module plus provenance."""

    module: str
    run_id: int
    mode: GenerationMode
    path: Path
    code: str
    profile: str
    provider: str = "mock"
    model: str = "deterministic-templates"
    prompt_sha256: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_manifest_entry(self, project_root: Path) -> dict[str, Any]:
        try:
            relative = self.path.relative_to(project_root).as_posix()
        except ValueError:
            relative = self.path.as_posix()
        return {
            "module": self.module,
            "run_id": self.run_id,
            "mode": self.mode.value,
            "profile": self.profile,
            "provider": self.provider,
            "model": self.model,
            "path": relative,
            "prompt_sha256": self.prompt_sha256,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            **self.metadata,
        }


# ---------------------------------------------------------------------------
# Deterministic mock profiles
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MockProfile:
    """Recipe for one synthetic generation quality tier."""

    name: str
    description: str
    block_mode: str  # "all" | "partial" | "minimal"
    keep_assertions: bool
    expect_failure: bool = False
    syntax_error: bool = False


PROFILE_ORDER: tuple[str, ...] = ("high", "medium", "low", "wrong", "broken")

MOCK_PROFILES: dict[str, MockProfile] = {
    "high": MockProfile(
        name="high",
        description="Complete suite: every behaviour and guard is asserted.",
        block_mode="all",
        keep_assertions=True,
    ),
    "medium": MockProfile(
        name="medium",
        description="Partial suite: some test blocks never assert their result.",
        block_mode="partial",
        keep_assertions=False,
    ),
    "low": MockProfile(
        name="low",
        description="Shallow suite: few scenarios and most assertions removed.",
        block_mode="minimal",
        keep_assertions=False,
    ),
    "wrong": MockProfile(
        name="wrong",
        description="Plausible suite containing one incorrect expectation.",
        block_mode="all",
        keep_assertions=True,
        expect_failure=True,
    ),
    "broken": MockProfile(
        name="broken",
        description="Syntax error in the module body: pytest cannot collect it.",
        block_mode="all",
        keep_assertions=True,
        syntax_error=True,
    ),
}


def profile_for_run(run_id: int) -> MockProfile:
    """Deterministically map a 1-based run id onto a quality profile."""
    index = max(run_id - 1, 0) % len(PROFILE_ORDER)
    return MOCK_PROFILES[PROFILE_ORDER[index]]


def _fake_syntax_error() -> str:
    """A guaranteed ``SyntaxError`` that pytest reports as a collection error."""
    return (
        "\n\n# NOTE: the generator truncated this line, as LLMs sometimes do.\n"
        "def test_generated_incomplete_case(:\n"
        "    assert True\n"
    )


def _wrong_expectation() -> str:
    """A collectible test whose assertion is simply wrong."""
    return (
        "\n\ndef test_generated_expectation_is_incorrect() -> None:\n"
        '    """A plausible-looking assertion that is internally inconsistent."""\n'
        "    assert 2 + 2 == 5\n"
    )


# ---------------------------------------------------------------------------
# Per-module mock test blocks
# ---------------------------------------------------------------------------
# Each block is a (function source, assertion count) pair.  ``function source``
# is a complete top-level ``def`` with a four-space indented body.
MockBlock = tuple[str, int]


def _blocks_m1() -> list[MockBlock]:
    return [
        (
            """\
def test_add_and_subtract() -> None:
    assert add(2, 3) == 5
    assert subtract(10, 4) == 6
""",
            2,
        ),
        (
            """\
def test_multiply_and_divide() -> None:
    assert multiply(6, 7) == 42
    assert divide(9, 3) == 3
    assert divide(1, 4) == 0.25
""",
            3,
        ),
        (
            """\
def test_divide_by_zero_raises() -> None:
    with pytest.raises(ValueError, match="division by zero"):
        divide(1, 0)
""",
            1,
        ),
        (
            """\
def test_average_and_empty_error() -> None:
    assert average([1.0, 2.0, 3.0]) == 2.0
    with pytest.raises(ValueError):
        average([])
""",
            2,
        ),
        (
            """\
def test_is_close_tolerance() -> None:
    assert is_close(0.1 + 0.2, 0.3) is True
    assert is_close(1.0, 1.1) is False
    with pytest.raises(ValueError):
        is_close(1.0, 1.0, tolerance=-0.5)
""",
            3,
        ),
    ]


def _blocks_m2() -> list[MockBlock]:
    return [
        (
            """\
def test_normalise_and_reverse() -> None:
    assert normalise("  hello   world  ") == "hello world"
    assert reverse("abc") == "cba"
""",
            2,
        ),
        (
            """\
def test_palindrome_detection() -> None:
    assert is_palindrome("A man, a plan, a canal: Panama") is True
    assert is_palindrome("hello") is False
""",
            2,
        ),
        (
            """\
def test_word_count_and_truncate() -> None:
    assert word_count("the quick brown fox") == 4
    assert truncate("abcdefghij", 8) == "abcde..."
""",
            2,
        ),
        (
            """\
def test_type_errors() -> None:
    with pytest.raises(TypeError):
        normalise(42)
    with pytest.raises(TypeError):
        reverse(None)
""",
            2,
        ),
        (
            """\
def test_truncate_suffix_budget() -> None:
    with pytest.raises(ValueError, match="too small"):
        truncate("abcdef", 2)
""",
            1,
        ),
    ]


def _blocks_m3() -> list[MockBlock]:
    return [
        (
            """\
def test_valid_email_and_phone() -> None:
    assert validate_email("user@example.com") == "user@example.com"
    assert validate_phone("123 456 7890") == "1234567890"
""",
            2,
        ),
        (
            """\
def test_invalid_email_raises() -> None:
    with pytest.raises(InvalidEmailError):
        validate_email("not-an-email")
""",
            1,
        ),
        (
            """\
def test_username_and_age_rules() -> None:
    assert validate_username("arnav_99") == "arnav_99"
    assert validate_age(0) == 0
    with pytest.raises(ValidationError):
        validate_age(True)
""",
            3,
        ),
        (
            """\
def test_phone_and_age_boundaries() -> None:
    assert validate_phone("+14155552671") == "+14155552671"
    with pytest.raises(ValidationError):
        validate_age(131)
    with pytest.raises(ValidationError):
        validate_age(-1)
""",
            3,
        ),
        (
            """\
def test_exception_hierarchy() -> None:
    assert issubclass(InvalidPhoneError, ValidationError)
    assert issubclass(ValidationError, ValueError)
""",
            2,
        ),
    ]


def _blocks_m4() -> list[MockBlock]:
    return [
        (
            """\
def test_letter_grade_boundaries() -> None:
    assert letter_grade(90) == "A"
    assert letter_grade(89.99) == "B"
    assert letter_grade(60) == "D"
    assert letter_grade(59.99) == "F"
""",
            4,
        ),
        (
            """\
def test_grade_points() -> None:
    assert grade_point("A") == 4.0
    assert grade_point("F") == 0.0
    with pytest.raises(ValueError):
        grade_point("Z")
""",
            3,
        ),
        (
            """\
def test_weighted_average_and_errors() -> None:
    assert weighted_average([80.0, 100.0], [3.0, 1.0]) == 85.0
    with pytest.raises(ValueError):
        weighted_average([], [])
""",
            2,
        ),
        (
            """\
def test_passing_and_describing() -> None:
    assert passing_score([60.0]) is True
    assert passing_score([59.0]) is False
    assert describe_score(82.0) == "B - pass (82.0)"
""",
            3,
        ),
        (
            """\
def test_invalid_scores_raise() -> None:
    with pytest.raises(ValueError):
        letter_grade(101)
    with pytest.raises(ValueError):
        passing_score([100.0, 101.0])
""",
            2,
        ),
    ]


def _blocks_m5() -> list[MockBlock]:
    return [
        (
            """\
def test_add_and_remove_items() -> None:
    inv = Inventory()
    inv.add_item("apples", 10, 1.5)
    inv.remove_item("apples", 4)
    assert inv.stock_level("apples") == 6
""",
            1,
        ),
        (
            """\
def test_totals_and_low_stock() -> None:
    inv = Inventory()
    inv.add_item("apples", 10, 1.5)
    inv.add_item("pears", 2, 3.0)
    assert inv.total_value() == 21.0
    assert inv.low_stock() == ["pears"]
""",
            2,
        ),
        (
            """\
def test_discounts_and_report() -> None:
    inv = Inventory()
    inv.add_item("widget", 1, 9.99)
    assert inv.apply_discount("widget", 15) == 8.49
    rows = inv.inventory_report()
    assert rows[0]["name"] == "widget"
""",
            2,
        ),
        (
            """\
def test_invalid_operations_raise() -> None:
    inv = Inventory()
    inv.add_item("apples", 1, 1.0)
    with pytest.raises(KeyError):
        inv.remove_item("ghost", 1)
    with pytest.raises(ValueError):
        inv.add_item("", 1, 1.0)
""",
            2,
        ),
        (
            """\
def test_threshold_and_discount_bounds() -> None:
    with pytest.raises(ValueError):
        Inventory(threshold=-1)
    inv = Inventory()
    inv.add_item("item", 1, 1.0)
    with pytest.raises(ValueError):
        inv.apply_discount("item", 101)
""",
            2,
        ),
    ]


def _blocks_m6() -> list[MockBlock]:
    return [
        (
            """\
def test_creation_and_deposit() -> None:
    account = BankAccount("Ada")
    assert account.balance == 0.0
    assert account.deposit(50.0) == 50.0
""",
            2,
        ),
        (
            """\
def test_withdraw_fee_and_overdraft() -> None:
    account = BankAccount("Ada", monthly_fee=2.5, overdraft_limit=100.0)
    account.deposit(200.0)
    assert account.withdraw(150.0) == 47.5
    assert account.withdraw(120.0) == 47.5 - 120.0 - 2.5 - OVERDRAFT_FEE
""",
            2,
        ),
        (
            """\
def test_transfer_and_log() -> None:
    alice = BankAccount("Alice")
    bob = BankAccount("Bob")
    alice.deposit(100.0)
    alice.transfer(bob, 40.0)
    assert alice.balance == 60.0
    assert bob.balance == 40.0
    assert len(alice.transactions()) == 2
""",
            3,
        ),
        (
            """\
def test_interest_is_credited() -> None:
    account = BankAccount("Ada", interest_rate=0.01)
    account.deposit(1000.0)
    assert account.apply_monthly_interest() == 1010.0
""",
            1,
        ),
        (
            """\
def test_close_requires_zero_balance() -> None:
    account = BankAccount("Ada")
    account.deposit(10.0)
    with pytest.raises(ValueError, match="zero"):
        account.close()
    account.withdraw(10.0)
    account.close()
    assert account.closed is True
""",
            2,
        ),
        (
            """\
def test_rejected_operations() -> None:
    account = BankAccount("Ada", overdraft_limit=30.0)
    account.deposit(10.0)
    with pytest.raises(ValueError):
        account.withdraw(45.0)
    with pytest.raises(ValueError):
        account.deposit(0.5)
""",
            2,
        ),
    ]


MODULE_TEST_BLOCKS: dict[str, Callable[[], list[MockBlock]]] = {
    "m1_arithmetic": _blocks_m1,
    "m2_string_utils": _blocks_m2,
    "m3_validation": _blocks_m3,
    "m4_grade_calc": _blocks_m4,
    "m5_inventory": _blocks_m5,
    "m6_bank_account": _blocks_m6,
}

MODULE_IMPORTS: dict[str, list[str]] = {
    "m1_arithmetic": ["add", "average", "divide", "is_close", "multiply", "subtract"],
    "m2_string_utils": [
        "is_palindrome",
        "normalise",
        "reverse",
        "truncate",
        "word_count",
    ],
    "m3_validation": [
        "InvalidEmailError",
        "InvalidPhoneError",
        "ValidationError",
        "validate_age",
        "validate_email",
        "validate_phone",
        "validate_username",
    ],
    "m4_grade_calc": [
        "describe_score",
        "grade_point",
        "letter_grade",
        "passing_score",
        "weighted_average",
    ],
    "m5_inventory": ["Inventory"],
    "m6_bank_account": ["BankAccount", "OVERDRAFT_FEE", "MIN_DEPOSIT"],
}


def _strip_assertion_lines(function_source: str) -> str:
    """Remove top-level ``assert`` statements while keeping nested blocks valid.

    Assertions inside ``with pytest.raises(...)`` stay untouched, because
    removing one would leave the ``with`` block empty and turn a runnable
    suite into an uncollectable one.
    """
    lines = function_source.splitlines()
    if not lines:
        return function_source
    kept: list[str] = [lines[0]]
    index = 1
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if indent == 4 and stripped.startswith("assert "):
            index += 1
            continue
        kept.append(line)
        if stripped.startswith("with pytest.raises("):
            # Copy the whole indented body of the ``with`` block verbatim.
            index += 1
            while index < len(lines):
                inner = lines[index]
                inner_indent = len(inner) - len(inner.lstrip())
                if inner.strip() and inner_indent <= indent:
                    break
                kept.append(inner)
                index += 1
            continue
        index += 1
    return "\n".join(kept).rstrip() + "\n"


def _has_statements(function_source: str) -> bool:
    """Whether a rendered test function has any executable body statement."""
    lines = function_source.splitlines()
    for line in lines[1:]:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return True
    return False


def _body_only_call(function_source: str) -> str:
    """Keep the function signature and add a harmless pass-through assertion."""
    header = function_source.splitlines()[0]
    return (
        f"{header}\n"
        "    # generated suite exercises the call without asserting the result\n"
        "    assert True\n"
    )


def _render_mock_suite(module: str, run_id: int, profile: MockProfile) -> str:
    """Assemble one deterministic synthetic suite for ``module``."""
    rng = random.Random(f"{module}:{run_id}:{profile.name}")
    blocks = list(MODULE_TEST_BLOCKS[module]())
    rng.shuffle(blocks)

    if profile.block_mode == "partial":
        keep = max(2, len(blocks) - 2)
        blocks = blocks[:keep]
    elif profile.block_mode == "minimal":
        blocks = blocks[:2]

    rendered: list[str] = []
    for index, (function_source, _count) in enumerate(blocks):
        text = function_source
        strip_assertions = not profile.keep_assertions and index >= 1
        if strip_assertions:
            text = _strip_assertion_lines(text)
            if not _has_statements(text):
                # Never emit an empty test body: replace it with a smoke-only
                # call so the suite still collects and executes.
                text = _body_only_call(text)
        rendered.append(text.rstrip())

    module_path = f"benchmark.{module}"
    imported = ", ".join(sorted(MODULE_IMPORTS[module]))
    header = (
        f'"""LLM-generated pytest suite for {module_path} '
        f'(run {run_id}, profile {profile.name}).\n\n'
        f"{profile.description}\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        "import pytest\n\n"
        f"from {module_path} import {imported}\n"
    )
    body = "\n\n\n".join(rendered)
    code = f"{header}\n\n{body}\n"
    if profile.expect_failure:
        code += _wrong_expectation()
    if profile.syntax_error:
        code += _fake_syntax_error()
    return code


# ---------------------------------------------------------------------------
# Live API generation
# ---------------------------------------------------------------------------
def load_dotenv(path: Path) -> dict[str, str]:
    """Load ``KEY=VALUE`` pairs from a ``.env`` file into ``os.environ``.

    Deliberately minimal and dependency-free: blank lines and ``#`` comments
    are skipped, optional single/double quotes around the value are removed,
    and existing environment variables always win.  Values are never logged.
    """
    loaded: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return loaded
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value
            loaded[key] = value
    return loaded


def _read_api_key(provider: str) -> str:
    for variable in API_KEY_ENV.get(provider, ()):
        value = os.environ.get(variable, "").strip()
        if value:
            return value
    joined = " or ".join(API_KEY_ENV.get(provider, ()))
    raise GenerationError(
        f"no API key found for provider {provider!r}; set {joined} "
        "or run with --mock"
    )


def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float = 120.0,
) -> dict[str, Any]:
    """POST ``payload`` as JSON and return the decoded response."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        retry_after: float | None = None
        header = exc.headers.get("Retry-After") if exc.headers else None
        if header:
            try:
                retry_after = float(header)
            except ValueError:
                retry_after = None
        if exc.code == 429 and retry_after is None:
            retry_after = 30.0
        raise GenerationError(
            f"HTTP {exc.code} from {url}: {detail}", retry_after=retry_after
        ) from exc
    except urllib.error.URLError as exc:
        raise GenerationError(f"network error contacting {url}: {exc.reason}") from exc
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GenerationError(f"provider returned non-JSON payload: {raw[:500]!r}") from exc
    if not isinstance(decoded, dict):
        raise GenerationError("provider returned an unexpected JSON shape")
    return decoded


_CODE_START_RE = re.compile(
    r"^(?:import\s+\S+|from\s+\S+\s+import|def\s+\w|class\s+Test|@pytest\.|#!)"
)


def _slice_to_code(lines: list[str]) -> list[str]:
    """Drop leading prose/blank lines so parsing can start at real code."""
    for index, line in enumerate(lines):
        if line.strip() and _CODE_START_RE.match(line.strip()):
            return lines[index:]
    return lines


def _extract_code(text: str) -> str:
    """Pull the first Python code block out of a model response.

    Models sometimes wrap the module in a fence and sometimes prepend a
    sentence of prose ("Here are the tests:").  Both would otherwise waste an
    API request, so the extractor tries the whole response, the fenced block,
    and the fenced block sliced from its first code-looking line before
    giving up.
    """
    fenced = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    candidates: list[str] = [fenced.group(1) if fenced else text, text]
    if fenced:
        candidates.append("\n".join(_slice_to_code(fenced.group(1).splitlines())))

    errors: list[str] = []
    for raw in candidates:
        candidate = raw.strip()
        if not candidate:
            continue
        try:
            ast.parse(candidate)
        except SyntaxError as exc:
            errors.append(f"{exc.msg} (line {exc.lineno})")
            continue
        if "def test_" not in candidate and "class Test" not in candidate:
            continue
        return candidate + "\n"
    detail = errors[0] if errors else "no parseable Python found"
    raise GenerationError(f"generated code is not valid Python: {detail}")


class LLMTestGenerator:
    """Generates pytest suites either offline (mock) or from a hosted LLM."""

    def __init__(
        self,
        paths: ProjectPaths,
        mode: GenerationMode,
        provider: str = "openai",
        model: str | None = None,
        api_key: str | None = None,
        runs: int = 5,
        retries: int = 2,
        seed: int = 20260101,
        request_interval: float = 0.0,
        resume: bool = False,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        if runs < 1:
            raise ValueError("runs must be at least 1")
        if mode is GenerationMode.API and provider not in PROVIDERS:
            raise ValueError(
                f"unknown provider {provider!r}; choose from {sorted(PROVIDERS)}"
            )
        self.paths = paths
        self.mode = mode
        self.provider = provider
        self.model = (
            model
            or os.environ.get(f"{provider.upper()}_MODEL")
            or PROVIDERS.get(provider, ("", "mock", ""))[1]
        )
        self.api_key = api_key
        self.runs = runs
        self.retries = max(0, retries)
        self.seed = seed
        self.request_interval = max(0.0, float(request_interval))
        self.resume = resume
        self.log = logger or (lambda message: None)
        self._manifest: list[dict[str, Any]] = []
        if mode is GenerationMode.API:
            # Project .env first, then CWD .env; real env vars always win.
            for candidate in (self.paths.root / ".env", Path.cwd() / ".env"):
                load_dotenv(candidate)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def generate_all(self, modules: list[str]) -> list[GeneratedSuite]:
        """Generate ``runs`` suites for every module and return them."""
        self.paths.ensure_output_dirs()
        self._clear_stale_suites(modules)
        suites: list[GeneratedSuite] = []
        for module in modules:
            for run_id in range(1, self.runs + 1):
                suite = self.generate_one(module, run_id)
                suites.append(suite)
                self.log(
                    f"  [gen] {module} run {run_id}/{self.runs} -> {suite.path.name}"
                )
        self.write_manifest()
        return suites

    def _clear_stale_suites(self, modules: list[str]) -> None:
        """Remove generated suites that are not part of the current run grid.

        Only files matching ``{module}_gen_{n}.py`` for a known module are
        considered, so hand-written or unrelated files are never touched.
        """
        allowed = {
            f"{module}_gen_{run_id}.py"
            for module in modules
            for run_id in range(1, self.runs + 1)
        }
        for module in modules:
            for path in self.paths.generated_dir.glob(f"{module}_gen_*.py"):
                if path.name not in allowed and path.is_file():
                    path.unlink()

    def generate_one(self, module: str, run_id: int) -> GeneratedSuite:
        """Generate and persist one suite for ``module``."""
        source_path = self.paths.benchmark_source(module)
        if not source_path.is_file():
            raise FileNotFoundError(f"benchmark module not found: {source_path}")
        source = source_path.read_text(encoding="utf-8")

        destination = self.paths.generated_test(module, run_id)
        if self.resume and destination.is_file():
            existing = destination.read_text(encoding="utf-8", errors="replace")
            if _looks_like_test_module(existing):
                self.log(f"  [gen] {module} run {run_id} -> {destination.name} (resumed)")
                suite = GeneratedSuite(
                    module=module,
                    run_id=run_id,
                    mode=self.mode,
                    path=destination,
                    code=existing,
                    profile="resumed",
                    provider=self.provider,
                    model=self.model,
                    metadata={"resumed": True},
                )
                self._manifest.append(suite.as_manifest_entry(self.paths.root))
                return suite

        if self.mode is GenerationMode.MOCK:
            suite = self._generate_mock(module, run_id, source)
        else:
            suite = self._generate_api(module, run_id, source, source_path)

        _atomic_write(destination, suite.code)
        suite.path = destination
        self._manifest.append(suite.as_manifest_entry(self.paths.root))
        return suite

    def write_manifest(self) -> Path:
        """Persist the generation manifest to ``generated_tests/manifest.json``."""
        destination = self.paths.generated_dir / "manifest.json"
        payload = {
            "pipeline_version": "1.0.0",
            "mode": self.mode.value,
            "provider": self.provider,
            "model": self.model,
            "runs": self.runs,
            "seed": self.seed,
            "prompt_template": GENERATION_PROMPT,
            "suites": self._manifest,
        }
        _atomic_write(
            destination, json.dumps(payload, indent=2, sort_keys=False) + "\n"
        )
        return destination

    # ------------------------------------------------------------------
    # Mock implementation
    # ------------------------------------------------------------------
    def _generate_mock(self, module: str, run_id: int, source: str) -> GeneratedSuite:
        profile = profile_for_run(run_id)
        code = _render_mock_suite(module, run_id, profile)
        return GeneratedSuite(
            module=module,
            run_id=run_id,
            mode=GenerationMode.MOCK,
            path=self.paths.generated_test(module, run_id),
            code=code,
            profile=profile.name,
            provider="mock",
            model="deterministic-templates",
            prompt_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
            metadata={"profile_description": profile.description},
        )

    # ------------------------------------------------------------------
    # Live API implementation
    # ------------------------------------------------------------------
    def _generate_api(
        self, module: str, run_id: int, source: str, source_path: Path
    ) -> GeneratedSuite:
        prompt = GENERATION_PROMPT.format(
            module_path=f"benchmark.{module}", source=source
        )
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        key = (self.api_key or "").strip() or _read_api_key(self.provider)

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                text, usage = self._call_provider(prompt, key)
                code = _extract_code(text)
                if self.request_interval > 0:
                    time.sleep(self.request_interval)
                return GeneratedSuite(
                    module=module,
                    run_id=run_id,
                    mode=GenerationMode.API,
                    path=self.paths.generated_test(module, run_id),
                    code=code,
                    profile="live",
                    provider=self.provider,
                    model=self.model,
                    prompt_sha256=prompt_hash,
                    prompt_tokens=int(usage.get("prompt_tokens", 0)),
                    completion_tokens=int(usage.get("completion_tokens", 0)),
                    metadata={
                        "source_sha256": hashlib.sha256(
                            source.encode("utf-8")
                        ).hexdigest(),
                        "attempts": attempt + 1,
                    },
                )
            except GenerationError as exc:
                last_error = exc
                if attempt < self.retries:
                    base = 2.0 * (2**attempt)
                    hint = getattr(exc, "retry_after", None)
                    delay = min(max(base, hint or 0.0), 90.0)
                    self.log(
                        f"  [gen] {module} run {run_id} attempt {attempt + 1} "
                        f"failed ({exc}); retrying in {delay:.0f}s"
                    )
                    time.sleep(delay)
        raise GenerationError(
            f"could not generate a usable suite for {module} run {run_id} "
            f"after {self.retries + 1} attempts: {last_error}"
        )

    def _call_provider(self, prompt: str, api_key: str) -> tuple[str, dict[str, Any]]:
        base_url = PROVIDERS[self.provider][0]
        if self.provider == "gemini":
            url = f"{base_url}/models/{self.model}:generateContent"
            payload: dict[str, Any] = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 16384,
                },
            }
            # The key travels in a header so it never lands in a URL, a log
            # line or an exception message.
            decoded = _post_json(url, payload, {"x-goog-api-key": api_key})
            try:
                candidates = decoded["candidates"]
                parts = candidates[0]["content"]["parts"]
                text = "".join(part.get("text", "") for part in parts)
            except (KeyError, IndexError, TypeError) as exc:
                raise GenerationError(
                    f"unexpected Gemini response: {json.dumps(decoded)[:800]}"
                ) from exc
            usage_meta = decoded.get("usageMetadata", {})
            usage = {
                "prompt_tokens": usage_meta.get("promptTokenCount", 0),
                "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
            }
            return text, usage

        url = f"{base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": 8192,
            "messages": [
                {
                    "role": "system",
                    "content": "You write precise, runnable pytest test modules.",
                },
                {"role": "user", "content": prompt},
            ],
        }
        decoded = _post_json(
            url,
            payload,
            {"Authorization": f"Bearer {api_key}"},
        )
        try:
            text = decoded["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GenerationError(
                f"unexpected chat-completions response: {json.dumps(decoded)[:800]}"
            ) from exc
        usage = decoded.get("usage", {}) or {}
        return text, {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }


def _atomic_write(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` via a temporary file and ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _looks_like_test_module(code: str) -> bool:
    """Whether ``code`` parses and defines at least one pytest test."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            return True
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            return True
    return False


def default_modules(paths: ProjectPaths) -> list[str]:
    """Discover benchmark modules in canonical order."""
    return [
        path.stem
        for path in sorted(paths.benchmark_dir.glob("m*.py"))
        if not path.stem.startswith("__")
    ]


__all__ = [
    "API_KEY_ENV",
    "GENERATION_PROMPT",
    "PROVIDERS",
    "GenerationError",
    "GenerationMode",
    "GeneratedSuite",
    "LLMTestGenerator",
    "MOCK_PROFILES",
    "MockProfile",
    "default_modules",
    "profile_for_run",
]
