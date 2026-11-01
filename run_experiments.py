#!/usr/bin/env python
"""Top-level experiment driver for the LLM test-quality study.

Typical use::

    # Fast offline validation (no API key required).
    python run_experiments.py --mock --runs 5

    # Very fast validation without mutation testing.
    python run_experiments.py --mock --runs 5 --skip-mutation

    # Live generation with a hosted model.
    export OPENAI_API_KEY="..."
    python run_experiments.py --api --provider openai --model gpt-4o-mini --runs 5

The command runs the entire protocol -- complexity measurement, test
generation, collection, execution, coverage, mutation testing, statistics and
figures -- writes every artefact under ``results/`` and prints a formatted
summary table.
"""

from __future__ import annotations

import argparse

import sys
import time
import traceback
from pathlib import Path
from typing import Any, Sequence

import pandas as pd
from tabulate import tabulate

from pipeline.analyzer import AnalysisError, run_analysis
from pipeline.complexity import ComplexityAnalyzer, write_complexity_report
from pipeline.config import (
    PIPELINE_VERSION,
    FAILURE_CATEGORIES,
    ProjectPaths,
    RESULT_COLUMNS,
)
from pipeline.evaluator import (
    EvaluationSettings,
    SuiteDescriptor,
    SuiteResult,
    TestEvaluator,
    baseline_descriptors,
    generated_descriptors,
)
from pipeline.generator import (
    GenerationError,
    GenerationMode,
    LLMTestGenerator,
    default_modules,
)

#: Default per-mutant timeout in seconds.
DEFAULT_MUTATION_TIMEOUT = 20.0


def build_parser() -> argparse.ArgumentParser:
    """Construct the command-line interface."""
    parser = argparse.ArgumentParser(
        prog="run_experiments.py",
        description="Evaluate LLM-generated Python unit tests on the CPB-6 corpus.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--mock",
        action="store_true",
        help="offline deterministic generation (no API key needed)",
    )
    mode.add_argument(
        "--api",
        action="store_true",
        help="live generation through a hosted LLM API",
    )
    parser.add_argument(
        "--provider",
        choices=("openai", "deepseek", "gemini"),
        default="openai",
        help="LLM provider used with --api",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="model name override (provider default is used when omitted)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key; defaults to the provider's environment variable",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="number of generated suites per module",
    )
    parser.add_argument(
        "--skip-mutation",
        action="store_true",
        help="skip mutation testing (fast validation of the rest of the pipeline)",
    )
    parser.add_argument(
        "--skip-baseline",
        action="store_true",
        help="do not evaluate the human baseline suites",
    )
    parser.add_argument(
        "--no-figures",
        action="store_true",
        help="write statistics but skip matplotlib figures",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="project root (defaults to the directory containing this script)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260101,
        help="deterministic seed for mock generation",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="with --api, keep suites already on disk instead of regenerating them",
    )
    parser.add_argument(
        "--request-interval",
        type=float,
        default=1.0,
        help="seconds to wait between live API requests (rate-limit friendly)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="retries per live API request before aborting",
    )
    parser.add_argument(
        "--mutation-timeout",
        type=float,
        default=DEFAULT_MUTATION_TIMEOUT,
        help="per-mutant timeout in seconds",
    )
    parser.add_argument(
        "--max-mutants",
        type=int,
        default=None,
        help="cap the number of mutants evaluated per suite (debugging aid)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="only print the final summary",
    )
    return parser


def _log(message: str, quiet: bool = False) -> None:
    if not quiet:
        print(message, flush=True)


def _print_banner(settings: argparse.Namespace) -> None:
    mode = "API" if settings.api else "MOCK"
    print("=" * 78)
    print(f" LLM Test Quality Evaluation  |  pipeline v{PIPELINE_VERSION}")
    print(f" mode={mode}  runs/module={settings.runs}  "
          f"mutation={'off' if settings.skip_mutation else 'on'}")
    print("=" * 78)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point; returns a process exit code."""
    parser = build_parser()
    settings = parser.parse_args(argv)
    if settings.runs < 1:
        parser.error("--runs must be at least 1")
    if settings.max_mutants is not None and settings.max_mutants < 1:
        parser.error("--max-mutants must be at least 1")
    if settings.mutation_timeout <= 0:
        parser.error("--mutation-timeout must be positive")
    if settings.api and settings.provider not in {"openai", "deepseek", "gemini"}:
        parser.error(f"unsupported provider: {settings.provider}")

    started = time.perf_counter()
    try:
        paths = ProjectPaths.resolve(settings.root)
    except (FileNotFoundError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    paths.ensure_output_dirs()

    _print_banner(settings)
    if not settings.api:
        settings.mock = True
        if not settings.quiet:
            print(
                "note: no --api flag supplied; running in offline mock mode "
                "(use --api for live LLM generation).\n"
            )
    mode = GenerationMode.API if settings.api else GenerationMode.MOCK
    modules = default_modules(paths)
    if not modules:
        print("error: no benchmark modules found under benchmark/", file=sys.stderr)
        return 2

    evaluator_settings = EvaluationSettings(
        skip_mutation=settings.skip_mutation,
        mutation_timeout=settings.mutation_timeout,
        max_mutants=settings.max_mutants,
    )

    try:
        # ----------------------------------------------------------
        # 1. Complexity
        # ----------------------------------------------------------
        _log("\n[1/5] Measuring cyclomatic complexity ...", settings.quiet)
        analyzer = ComplexityAnalyzer(paths, modules)
        complexities = analyzer.analyze_all()
        complexity_path = write_complexity_report(complexities, paths.results_dir)
        table_rows = [
            [
                module,
                f"{item.average:.2f}",
                item.maximum,
                len(item.functions),
            ]
            for module, item in sorted(complexities.items())
        ]
        _log(
            tabulate(
                table_rows,
                headers=["module", "avg CC", "max CC", "blocks"],
                tablefmt="rounded_grid",
            ),
            settings.quiet,
        )
        _log(f"      -> {complexity_path.relative_to(paths.root)}", settings.quiet)

        # ----------------------------------------------------------
        # 2. Generation
        # ----------------------------------------------------------
        _log("\n[2/5] Generating test suites ...", settings.quiet)
        generator = LLMTestGenerator(
            paths=paths,
            mode=mode,
            provider=settings.provider,
            model=settings.model,
            api_key=settings.api_key,
            runs=settings.runs,
            seed=settings.seed,
            retries=settings.retries,
            request_interval=settings.request_interval,
            resume=settings.resume,
            logger=lambda message: _log(message, settings.quiet),
        )
        generated = generator.generate_all(modules)
        _log(f"      {len(generated)} suites written to generated_tests/", settings.quiet)

        # ----------------------------------------------------------
        # 3. Evaluation
        # ----------------------------------------------------------
        _log("\n[3/5] Evaluating suites (collection, execution, coverage, mutation) ...",
             settings.quiet)
        evaluator = TestEvaluator(
            paths=paths,
            complexities=complexities,
            settings=evaluator_settings,
            logger=lambda message: _log(message, settings.quiet),
        )
        descriptors: list[SuiteDescriptor] = generated_descriptors(
            paths, modules, settings.runs
        )
        if not settings.skip_baseline:
            descriptors.extend(baseline_descriptors(paths, modules))

        results: list[SuiteResult] = []
        total = len(descriptors)
        for index, descriptor in enumerate(descriptors, start=1):
            _log(
                f"  [{index:>2}/{total}] {descriptor.module:<16} {descriptor.suite:<16}",
                settings.quiet,
            )
            try:
                result = evaluator.evaluate(descriptor)
            except Exception as exc:  # noqa: BLE001 - reported, never fatal
                result = SuiteResult(
                    module=descriptor.module,
                    suite=descriptor.suite,
                    run_id=descriptor.run_id,
                    generation_mode=descriptor.generation_mode,
                    test_file=str(descriptor.test_file),
                    failure_category="RuntimeError",
                    error_message=f"evaluator crashed: {exc}",
                )
                _log(f"        ! {exc}", settings.quiet)
            results.append(result)
            _log(
                "        "
                f"collect={result.collection_success!s:<5} "
                f"exec={result.execution_success!s:<5} "
                f"tests={result.total_tests:<3} "
                f"line={_fmt(result.line_coverage, '%')} "
                f"branch={_fmt(result.branch_coverage, '%')} "
                f"mut={_fmt(result.mutation_score)} "
                f"cat={result.failure_category}",
                settings.quiet,
            )

        # ----------------------------------------------------------
        # 4. Compile metrics
        # ----------------------------------------------------------
        _log("\n[4/5] Compiling metrics ...", settings.quiet)
        metrics_path = paths.results_dir / "evaluation_metrics.csv"
        rows = [result.as_row() for result in results]
        frame = pd.DataFrame(rows, columns=list(RESULT_COLUMNS))
        frame.to_csv(metrics_path, index=False)
        _log(f"      -> {metrics_path.relative_to(paths.root)} ({len(frame)} rows)",
             settings.quiet)

        # ----------------------------------------------------------
        # 5. Analysis
        # ----------------------------------------------------------
        _log("\n[5/5] Statistical analysis and figures ...", settings.quiet)
        analysis = run_analysis(paths, metrics_path, make_figures=not settings.no_figures)
        _log(f"      -> {analysis.summary_path.relative_to(paths.root)}", settings.quiet)
        _log(f"      -> {analysis.correlation_path.relative_to(paths.root)}", settings.quiet)
        for figure in analysis.figures:
            _log(f"      -> {figure.relative_to(paths.root)}", settings.quiet)
        _log(f"      -> {analysis.report_path.relative_to(paths.root)}", settings.quiet)

    except (GenerationError, AnalysisError, FileNotFoundError, ValueError) as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - top-level safety net
        print(f"\nunexpected error: {exc}", file=sys.stderr)
        if not settings.quiet:
            traceback.print_exc()
        return 1

    elapsed = time.perf_counter() - started
    _print_summary(frame, analysis.correlations, paths, elapsed, settings.skip_mutation)
    return 0


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def _fmt(value: Any, suffix: str = "") -> str:
    if value is None:
        return "-"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if numeric != numeric:  # NaN
        return "-"
    if suffix == "%":
        return f"{numeric:.1f}{suffix}"
    return f"{numeric:.3f}"


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series([float("nan")] * len(frame), index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _module_summary(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    work["line_coverage"] = _numeric(work, "line_coverage")
    work["branch_coverage"] = _numeric(work, "branch_coverage")
    work["mutation_score"] = _numeric(work, "mutation_score")
    work["execution_success"] = _numeric(work, "execution_success")
    work["collection_success"] = _numeric(work, "collection_success")
    grouped = (
        work.groupby("module", sort=True)
        .agg(
            suites=("suite", "count"),
            collection=("collection_success", "mean"),
            execution=("execution_success", "mean"),
            line_cov=("line_coverage", "mean"),
            branch_cov=("branch_coverage", "mean"),
            mutation=("mutation_score", "mean"),
        )
        .reset_index()
    )
    grouped["collection"] = grouped["collection"] * 100.0
    grouped["execution"] = grouped["execution"] * 100.0
    return grouped


def _mode_summary(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    for column in ("line_coverage", "branch_coverage", "mutation_score",
                   "execution_success", "collection_success", "total_tests"):
        work[column] = _numeric(work, column)
    grouped = (
        work.groupby("generation_mode", sort=True)
        .agg(
            suites=("suite", "count"),
            collection=("collection_success", "mean"),
            execution=("execution_success", "mean"),
            tests=("total_tests", "mean"),
            line_cov=("line_coverage", "mean"),
            branch_cov=("branch_coverage", "mean"),
            mutation=("mutation_score", "mean"),
            line_cov_all=("line_coverage", lambda values: _zero_filled_mean(values)),
            mutation_all=("mutation_score", lambda values: _zero_filled_mean(values)),
        )
        .reset_index()
    )
    grouped["collection"] = grouped["collection"] * 100.0
    grouped["execution"] = grouped["execution"] * 100.0
    return grouped


def _zero_filled_mean(values: pd.Series) -> float:
    """Mean with missing suites counted as zero, matching the per-module table."""
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.empty:
        return float("nan")
    return float(numeric.fillna(0.0).mean())


def _print_summary(
    frame: pd.DataFrame,
    correlations: pd.DataFrame,
    paths: ProjectPaths,
    elapsed: float,
    mutation_skipped: bool,
) -> None:
    """Print the formatted final report to stdout."""
    print("\n" + "=" * 78)
    print(" RESULTS - mean metrics per benchmark module")
    print("=" * 78)
    modules = _module_summary(frame)
    module_rows = [
        [
            row["module"],
            int(row["suites"]),
            f"{row['collection']:.0f}%",
            f"{row['execution']:.0f}%",
            _fmt(row["line_cov"], "%"),
            _fmt(row["branch_cov"], "%"),
            _fmt(row["mutation"]),
        ]
        for _, row in modules.iterrows()
    ]
    print(
        tabulate(
            module_rows,
            headers=[
                "module", "suites", "collect", "exec", "line cov", "branch cov", "mutation"
            ],
            tablefmt="rounded_grid",
            stralign="right",
        )
    )

    print("\n" + "=" * 78)
    print(" RESULTS - by suite origin")
    print("=" * 78)
    modes = _mode_summary(frame)
    mode_rows = [
        [
            row["generation_mode"],
            int(row["suites"]),
            f"{row['collection']:.0f}%",
            f"{row['execution']:.0f}%",
            _fmt(row["tests"]),
            _fmt(row["line_cov"], "%"),
            _fmt(row["line_cov_all"], "%"),
            _fmt(row["branch_cov"], "%"),
            _fmt(row["mutation_all"]),
        ]
        for _, row in modes.iterrows()
    ]
    print(
        tabulate(
            mode_rows,
            headers=[
                "origin", "suites", "collect", "exec", "tests",
                "line cov*", "line cov", "branch cov", "mutation",
            ],
            tablefmt="rounded_grid",
            stralign="right",
        )
    )

    if not mutation_skipped:
        generated_block = correlations[
            (correlations["scope"] == "generated")
            & (correlations["question"].isin(["RQ2", "RQ3", "RQ5a", "RQ5b"]))
        ]
        if not generated_block.empty:
            print("\n" + "=" * 78)
            print(" SPEARMAN CORRELATIONS - generated suites")
            print("=" * 78)
            corr_rows: list[list[str]] = []
            for _, row in generated_block.iterrows():
                corr_rows.append(
                    [
                        str(row["question"]),
                        f"{row['x']} ~ {row['y']}",
                        str(int(row["n"])),
                        _fmt(row["spearman_rho"]),
                        _fmt(row["p_value"]),
                        "yes" if bool(row["significant_at_0.05"]) else "no",
                    ]
                )
            print(
                tabulate(
                    corr_rows,
                    headers=["RQ", "pair", "n", "rho", "p", "p<0.05"],
                    tablefmt="rounded_grid",
                    stralign="right",
                )
            )

    categories = (
        frame["failure_category"].fillna("None").astype(str).value_counts()
    )
    ordered = [(category, int(categories.get(category, 0))) for category in FAILURE_CATEGORIES]
    print("\n" + "=" * 78)
    print(" FAILURE CATEGORIES (RQ6)")
    print("=" * 78)
    print(
        tabulate(
            [[name, count] for name, count in ordered],
            headers=["category", "suites"],
            tablefmt="rounded_grid",
            stralign="right",
        )
    )

    print("\n" + "-" * 78)
    print(f" Artifacts written under {paths.results_dir.relative_to(paths.root)}/")
    print(f"   metrics      : results/evaluation_metrics.csv")
    print(f"   statistics   : results/summary_statistics.csv")
    print(f"   correlations : results/correlation_analysis.csv")
    print(f"   report       : results/reports/analysis_report.md")
    print(f"   figures      : results/figures/")
    print(f" Elapsed: {elapsed:.1f}s")
    print("-" * 78)


if __name__ == "__main__":
    raise SystemExit(main())
