"""Shared paths, constants and process helpers for the evaluation pipeline."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Sequence

#: Version of the pipeline; recorded in every artefact for reproducibility.
PIPELINE_VERSION: Final[str] = "1.0.0"

#: Column order of ``results/evaluation_metrics.csv``.
RESULT_COLUMNS: Final[tuple[str, ...]] = (
    "module",
    "suite",
    "run_id",
    "generation_mode",
    "test_file",
    "collection_success",
    "execution_success",
    "total_tests",
    "passed",
    "failed",
    "errors",
    "skipped",
    "execution_time_s",
    "line_coverage",
    "branch_coverage",
    "combined_coverage",
    "avg_complexity",
    "max_complexity",
    "total_mutants",
    "killed_mutants",
    "survived_mutants",
    "timeout_mutants",
    "invalid_mutants",
    "mutation_score",
    "failure_category",
    "tests_per_kloc",
    "assertions_per_test",
    "generated_loc",
    "error_message",
    "notes",
)

#: Canonical failure categories used throughout the analysis.
FAILURE_CATEGORIES: Final[tuple[str, ...]] = (
    "None",
    "CollectionError",
    "AssertionFailure",
    "RuntimeError",
    "Timeout",
)

#: Mapping module name -> importable module path.
MODULE_IMPORTS: Final[dict[str, str]] = {
    "m1_arithmetic": "benchmark.m1_arithmetic",
    "m2_string_utils": "benchmark.m2_string_utils",
    "m3_validation": "benchmark.m3_validation",
    "m4_grade_calc": "benchmark.m4_grade_calc",
    "m5_inventory": "benchmark.m5_inventory",
    "m6_bank_account": "benchmark.m6_bank_account",
}


@dataclass(frozen=True)
class ProjectPaths:
    """Resolved locations used by the pipeline.

    ``root`` is the repository root (the directory that contains
    ``benchmark/``, ``baselines/`` and ``results/``).
    """

    root: Path

    @classmethod
    def resolve(cls, root: str | Path | None = None) -> "ProjectPaths":
        """Build a :class:`ProjectPaths` rooted at ``root`` or its parent directory."""
        if root is None:
            resolved = Path(__file__).resolve().parent.parent
        else:
            resolved = Path(root).expanduser().resolve()
        if not resolved.is_dir():
            raise FileNotFoundError(f"project root does not exist: {resolved}")
        return cls(root=resolved)

    @property
    def benchmark_dir(self) -> Path:
        return self.root / "benchmark"

    @property
    def baselines_dir(self) -> Path:
        return self.root / "baselines"

    @property
    def generated_dir(self) -> Path:
        return self.root / "generated_tests"

    @property
    def results_dir(self) -> Path:
        return self.root / "results"

    @property
    def figures_dir(self) -> Path:
        return self.results_dir / "figures"

    @property
    def reports_dir(self) -> Path:
        return self.results_dir / "reports"

    def benchmark_source(self, module: str) -> Path:
        """Path to ``benchmark/<module>.py``."""
        return self.benchmark_dir / f"{module}.py"

    def baseline_test(self, module: str) -> Path:
        """Path to the human ground-truth suite for ``module``."""
        return self.baselines_dir / f"test_{module.split('_', 1)[0]}_human.py"

    def generated_test(self, module: str, run_id: int) -> Path:
        """Path to the generated suite for ``module`` and ``run_id``."""
        return self.generated_dir / f"{module}_gen_{run_id}.py"

    def ensure_output_dirs(self) -> None:
        """Create every directory the pipeline writes into."""
        for directory in (
            self.benchmark_dir,
            self.baselines_dir,
            self.generated_dir,
            self.results_dir,
            self.figures_dir,
            self.reports_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@dataclass
class CommandResult:
    """Outcome of a subprocess invocation."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool = False

    @property
    def output(self) -> str:
        """Combined stdout and stderr."""
        return f"{self.stdout}\n{self.stderr}".strip()


def run_command(
    command: Sequence[str],
    cwd: str | Path | None = None,
    timeout: float = 300.0,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Run ``command`` to completion and capture its output.

    The child is placed in its own process group so that a timeout tears down
    the whole pytest tree rather than leaking workers.  A timeout is reported
    as ``timed_out=True`` with ``returncode=-1`` instead of raising, because
    the evaluator treats timeouts as a measured failure category.

    Args:
        command: Argument vector, executed without a shell.
        cwd: Working directory for the child process.
        timeout: Wall-clock budget in seconds.
        env: Extra environment variables merged over the current environment.

    Returns:
        A :class:`CommandResult` describing the run.
    """
    merged_env = os.environ.copy()
    merged_env.setdefault("PYTHONUNBUFFERED", "1")
    merged_env.setdefault("PYTHONHASHSEED", "0")
    merged_env.setdefault("MPLBACKEND", "Agg")
    # Generated tests must never see provider credentials: they are not needed
    # to run the suite, and keeping them out of child processes shrinks the
    # blast radius of any accidental environment dump.
    for secret in (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        merged_env.pop(secret, None)
    if env:
        merged_env.update(env)

    started = _monotonic()
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=merged_env,
            start_new_session=True,
        )
        return CommandResult(
            command=list(command),
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            duration_s=round(_monotonic() - started, 4),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _to_text(exc.stdout)
        stderr = _to_text(exc.stderr)
        return CommandResult(
            command=list(command),
            returncode=-1,
            stdout=stdout,
            stderr=stderr + f"\n[pipeline] timeout after {timeout:.1f}s",
            duration_s=round(_monotonic() - started, 4),
            timed_out=True,
        )
    except (FileNotFoundError, OSError) as exc:
        return CommandResult(
            command=list(command),
            returncode=-2,
            stdout="",
            stderr=f"[pipeline] failed to launch {command[0]!r}: {exc}",
            duration_s=round(_monotonic() - started, 4),
        )


def python_executable() -> str:
    """Return the interpreter that should run pytest subprocesses."""
    return sys.executable


def truncate(text: str, limit: int = 4000) -> str:
    """Shorten long diagnostic text while keeping both head and tail."""
    if len(text) <= limit:
        return text
    half = max(1, limit // 2)
    return f"{text[:half]}\n... [{len(text) - limit} chars elided] ...\n{text[-half:]}"


def _to_text(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _monotonic() -> float:
    import time

    return time.perf_counter()
