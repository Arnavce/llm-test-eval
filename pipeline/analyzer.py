"""Statistical analysis and figure generation for the evaluation results.

Reads ``results/evaluation_metrics.csv`` and produces:

* ``results/summary_statistics.csv`` -- per-generation-mode descriptive stats
  (mean, median, standard deviation, min, max, IQR) for every metric.
* ``results/correlation_analysis.csv`` -- Spearman rho, p-value, sample size
  and significance for each research question, computed both on generated
  suites only and on all suites (generated + human baseline).
* ``results/figures/rq2_rq3_coverage_vs_mutation.png``
* ``results/figures/rq5_complexity_vs_scores.png``
* ``results/figures/rq6_failure_categories.png``
* ``results/reports/analysis_report.md`` -- a prose report with RQ verdicts.

The module is import-safe: matplotlib is imported lazily and forced onto the
non-interactive ``Agg`` backend, so it can run on a headless server.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd

try:  # pragma: no cover - optional dependency
    from scipy import stats as _scipy_stats
except ImportError:  # pragma: no cover
    _scipy_stats = None

from .config import FAILURE_CATEGORIES, ProjectPaths

#: Metrics summarised in ``summary_statistics.csv``.
SUMMARY_METRICS: Final[tuple[str, ...]] = (
    "line_coverage",
    "branch_coverage",
    "combined_coverage",
    "mutation_score",
    "avg_complexity",
    "total_tests",
    "passed",
    "failed",
    "errors",
    "execution_time_s",
    "tests_per_kloc",
    "assertions_per_test",
    "generated_loc",
)

#: Human-readable labels for figures.
FEATURE_LABELS: Final[dict[str, str]] = {
    "line_coverage": "Line coverage (%)",
    "branch_coverage": "Branch coverage (%)",
    "combined_coverage": "Combined coverage (%)",
    "mutation_score": "Mutation score",
    "avg_complexity": "Average cyclomatic complexity",
    "total_tests": "Number of tests",
    "tests_per_kloc": "Tests per KLOC",
    "assertions_per_test": "Assertions per test",
    "execution_success": "Execution success rate",
}

#: The correlation questions of the study.
CORRELATION_QUESTIONS: Final[tuple[tuple[str, str, str], ...]] = (
    ("RQ2", "line_coverage", "mutation_score"),
    ("RQ3", "branch_coverage", "mutation_score"),
    ("RQ5a", "avg_complexity", "execution_success"),
    ("RQ5b", "avg_complexity", "mutation_score"),
    ("EXTRA1", "total_tests", "mutation_score"),
    ("EXTRA2", "assertions_per_test", "mutation_score"),
)

_PALETTE: Final[tuple[str, ...]] = (
    "#2E6F9E",
    "#D1495B",
    "#3F8F6B",
    "#B07A2A",
    "#6C5B7B",
    "#4C9F9F",
)
_NOTE = "Generated with pipeline.analyzer -- CPB-6 LLM test-quality study"


class AnalysisError(RuntimeError):
    """Raised when the metrics file is missing or unusable."""


@dataclass
class AnalysisOutput:
    """Paths written by :func:`run_analysis`."""

    summary_path: Path
    correlation_path: Path
    report_path: Path
    figures: list[Path]
    summary: pd.DataFrame
    correlations: pd.DataFrame


# ---------------------------------------------------------------------------
# Loading and descriptive statistics
# ---------------------------------------------------------------------------
def load_metrics(path: str | Path) -> pd.DataFrame:
    """Load the evaluation CSV and normalise its dtypes."""
    csv_path = Path(path)
    if not csv_path.is_file():
        raise AnalysisError(f"metrics file not found: {csv_path}")
    frame = pd.read_csv(csv_path)
    if frame.empty:
        raise AnalysisError(f"metrics file contains no rows: {csv_path}")

    required = {"module", "suite", "generation_mode", "line_coverage", "mutation_score"}
    missing = required.difference(frame.columns)
    if missing:
        raise AnalysisError(f"metrics file is missing columns: {sorted(missing)}")

    for column in (
        "collection_success",
        "execution_success",
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
        "total_tests",
        "passed",
        "failed",
        "errors",
        "skipped",
        "execution_time_s",
        "tests_per_kloc",
        "assertions_per_test",
        "generated_loc",
    ):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    for column in ("collection_success", "execution_success"):
        if column in frame.columns:
            frame[column] = frame[column].map(_to_bool).astype(float)

    frame["failure_category"] = (
        frame.get("failure_category", pd.Series(index=frame.index, dtype=object))
        .fillna("None")
        .astype(str)
    )
    return frame


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


def compute_summary(frame: pd.DataFrame, group_column: str = "generation_mode") -> pd.DataFrame:
    """Descriptive statistics per metric and ``group_column``."""
    rows: list[dict[str, Any]] = []
    for group, subset in frame.groupby(group_column, dropna=False):
        for metric in SUMMARY_METRICS:
            if metric not in subset.columns:
                continue
            series = pd.to_numeric(subset[metric], errors="coerce").dropna()
            if series.empty:
                continue
            q1 = float(series.quantile(0.25))
            q3 = float(series.quantile(0.75))
            rows.append(
                {
                    "scope": str(group),
                    "metric": metric,
                    "count": int(series.size),
                    "mean": float(series.mean()),
                    "median": float(series.median()),
                    "std": float(series.std(ddof=1)) if series.size > 1 else 0.0,
                    "min": float(series.min()),
                    "max": float(series.max()),
                    "q1": q1,
                    "q3": q3,
                    "iqr": q3 - q1,
                }
            )
    summary = pd.DataFrame(rows)
    if not summary.empty:
        numeric = summary.select_dtypes(include="number").columns
        summary[numeric] = summary[numeric].round(6)
    return summary


# ---------------------------------------------------------------------------
# Correlations
# ---------------------------------------------------------------------------
def _spearman(x: pd.Series, y: pd.Series) -> tuple[float | None, float | None, int]:
    """Spearman rho, two-sided p-value and n for two aligned numeric series."""
    data = pd.DataFrame({"x": x, "y": y}).dropna()
    data = data[np.isfinite(data["x"]) & np.isfinite(data["y"])]
    sample = int(len(data))
    if sample < 3 or data["x"].nunique() < 2 or data["y"].nunique() < 2:
        return None, None, sample
    if _scipy_stats is not None:
        rho, p_value = _scipy_stats.spearmanr(data["x"], data["y"])
        if rho is None or (isinstance(rho, float) and math.isnan(rho)):
            return None, None, sample
        p_val = float(p_value) if p_value is not None else float("nan")
        if math.isnan(p_val):
            return float(rho), None, sample
        return float(rho), p_val, sample
    # Pure-pandas fallback: Spearman == Pearson on average ranks.
    rho = float(data["x"].rank().corr(data["y"].rank()))
    p_value = _pearson_pvalue(rho, sample)
    return rho, p_value, sample


def _pearson_pvalue(rho: float, n: int) -> float | None:
    """Approximate two-sided p-value for a correlation coefficient."""
    if n < 3 or abs(rho) >= 1.0:
        return 0.0 if abs(rho) >= 1.0 else None
    # Student-t approximation without SciPy: use the incomplete beta function.
    df = n - 2
    t_stat = rho * math.sqrt(df / (1.0 - rho * rho))
    # Two-sided p for t distribution, approximated via the normal for df > 30.
    if df > 30:
        return float(math.erfc(abs(t_stat) / math.sqrt(2.0)))
    return _student_t_two_sided(t_stat, df)


def _student_t_two_sided(t_stat: float, df: int) -> float:
    """Two-sided Student-t tail probability via continued fraction (best effort)."""
    x = df / (df + t_stat * t_stat)
    # Regularised incomplete beta I_x(df/2, 1/2) computed by numerical integration.
    try:
        value = _incomplete_beta(df / 2.0, 0.5, x)
    except (ValueError, ZeroDivisionError):  # pragma: no cover - defensive
        return float("nan")
    return float(min(max(value, 0.0), 1.0))


def _incomplete_beta(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta using a simple series expansion."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_beta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    if x < (a + 1.0) / (a + b + 2.0):
        # Series around x = 0.
        front = math.exp(a * math.log(x) + b * math.log1p(-x) - log_beta) / a
        total = 1.0
        term = 1.0
        for index in range(1, 500):
            term *= (a + b + index - 1.0) * x / (a + index)
            total += term
            if abs(term) < 1e-12 * abs(total):
                break
        return front * total
    # Symmetry relation to keep the series in its fast-convergence region.
    return 1.0 - _incomplete_beta(b, a, 1.0 - x)


def compute_correlations(frame: pd.DataFrame) -> pd.DataFrame:
    """Spearman correlations for every question, per data scope."""
    scopes: list[tuple[str, pd.DataFrame]] = [
        ("generated", frame[frame["generation_mode"] == "generated"]),
        ("all", frame),
    ]
    if frame["generation_mode"].nunique() > 2:
        scopes.extend(
            (str(mode), frame[frame["generation_mode"] == mode])
            for mode in sorted(frame["generation_mode"].unique())
            if mode not in {"generated", "human"}
        )

    rows: list[dict[str, Any]] = []
    for scope_name, subset in scopes:
        if subset.empty:
            continue
        for question, x_column, y_column in CORRELATION_QUESTIONS:
            if x_column not in subset.columns or y_column not in subset.columns:
                continue
            x = pd.to_numeric(subset[x_column], errors="coerce")
            y = pd.to_numeric(subset[y_column], errors="coerce")
            if y_column == "execution_success":
                y = y.astype(float)
            rho, p_value, sample = _spearman(x, y)
            rows.append(
                {
                    "scope": scope_name,
                    "question": question,
                    "x": x_column,
                    "y": y_column,
                    "n": sample,
                    "spearman_rho": rho,
                    "p_value": p_value,
                    "significant_at_0.05": (
                        bool(p_value is not None and p_value < 0.05)
                        if rho is not None
                        else False
                    ),
                }
            )
    correlations = pd.DataFrame(rows)
    if not correlations.empty:
        correlations["spearman_rho"] = correlations["spearman_rho"].astype(float).round(6)
        correlations["p_value"] = correlations["p_value"].astype(float).round(6)
    return correlations


def _interpret(rho: float | None) -> str:
    if rho is None or math.isnan(rho):
        return "not estimable (insufficient variation or n < 3)"
    if abs(rho) < 1e-9:
        return "no monotonic association"
    magnitude = abs(rho)
    direction = "positive" if rho > 0 else "negative"
    if magnitude >= 0.8:
        strength = "very strong"
    elif magnitude >= 0.6:
        strength = "strong"
    elif magnitude >= 0.4:
        strength = "moderate"
    elif magnitude >= 0.2:
        strength = "weak"
    else:
        strength = "negligible"
    return f"{strength} {direction}"


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def _pyplot() -> Any:
    try:
        import os
        import tempfile

        # A writable config dir keeps font-cache warnings out of headless runs.
        os.environ.setdefault(
            "MPLCONFIGDIR",
            str(Path(tempfile.gettempdir()) / "llm_test_eval_mplconfig"),
        )
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise AnalysisError(
            "matplotlib is required for figures; install requirements.txt"
        ) from exc
    return plt


def _module_color_map(modules: list[str]) -> dict[str, str]:
    return {
        module: _PALETTE[index % len(_PALETTE)]
        for index, module in enumerate(sorted(modules))
    }


def plot_coverage_vs_mutation(frame: pd.DataFrame, destination: Path) -> Path:
    """RQ2/RQ3: coverage against mutation score, with least-squares trend lines."""
    plt = _pyplot()
    data = frame.dropna(subset=["mutation_score"]).copy()
    if data.empty:
        raise AnalysisError("no rows with both coverage and mutation score")

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.4), sharey=True)
    colors = _module_color_map(sorted(data["module"].unique()))
    scopes = [("Line coverage", "line_coverage"), ("Branch coverage", "branch_coverage")]

    for axis, (title, column) in zip(axes, scopes):
        subset = data.dropna(subset=[column])
        for module, group in subset.groupby("module"):
            axis.scatter(
                group[column],
                group["mutation_score"],
                s=46,
                alpha=0.85,
                color=colors[module],
                edgecolor="white",
                linewidth=0.8,
                label=module,
                zorder=3,
            )
        if subset[column].nunique() > 1 and len(subset) >= 3:
            slope, intercept = np.polyfit(subset[column], subset["mutation_score"], 1)
            xs = np.linspace(subset[column].min(), subset[column].max(), 100)
            axis.plot(
                xs,
                slope * xs + intercept,
                color="#333333",
                linewidth=1.8,
                linestyle="--",
                label="OLS trend",
                zorder=2,
            )
            rho, p_value, sample = _spearman(
                pd.to_numeric(subset[column], errors="coerce"),
                subset["mutation_score"],
            )
            if rho is not None:
                axis.text(
                    0.03,
                    0.97,
                    f"Spearman rho = {rho:+.3f}\np = {p_value:.3g}\nn = {sample}",
                    transform=axis.transAxes,
                    va="top",
                    fontsize=9,
                    family="monospace",
                    bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.9},
                )
        axis.set_title(f"{title} vs Mutation score", fontsize=11, weight="bold")
        axis.set_xlabel(FEATURE_LABELS[column])
        axis.set_ylabel(FEATURE_LABELS["mutation_score"])
        axis.grid(True, color="#d9d9d9", linewidth=0.7, alpha=0.8)
        axis.set_axisbelow(True)
        axis.set_ylim(bottom=-0.03, top=1.03)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=min(7, len(labels)),
        frameon=False,
        fontsize=8.5,
        bbox_to_anchor=(0.5, 0.0),
    )
    fig.suptitle(
        "RQ2/RQ3 - Coverage and mutation score of generated test suites",
        fontsize=13,
        weight="bold",
    )
    fig.tight_layout(rect=(0, 0.09, 1, 0.95))
    fig.text(0.01, 0.005, _NOTE, fontsize=7, color="#666666")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=300, facecolor="white")
    plt.close(fig)
    return destination


def plot_complexity_vs_scores(frame: pd.DataFrame, destination: Path) -> Path:
    """RQ5: module complexity against mutation score, test count and coverage."""
    plt = _pyplot()
    data = frame.dropna(subset=["avg_complexity"]).copy()
    if data.empty:
        raise AnalysisError("no rows with average complexity")

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.2))

    # Panel 1: box plot per module of mutation scores.
    axes[0].set_title("Mutation score by module", fontsize=11, weight="bold")
    groups = [
        group["mutation_score"].dropna().to_numpy()
        for _, group in data.groupby("module")
    ]
    labels = [name for name, _ in data.groupby("module")]
    non_empty = [(values, label) for values, label in zip(groups, labels) if len(values)]
    if non_empty:
        axes[0].boxplot(
            [values for values, _ in non_empty],
            tick_labels=[label for _, label in non_empty],
            patch_artist=True,
            boxprops={"facecolor": "#DCE8F2", "edgecolor": "#2E6F9E"},
            medianprops={"color": "#D1495B", "linewidth": 2},
            whiskerprops={"color": "#2E6F9E"},
            capprops={"color": "#2E6F9E"},
            widths=0.6,
        )
        axes[0].set_xticklabels(
            [label for _, label in non_empty], rotation=35, ha="right", fontsize=8
        )
    axes[0].set_ylabel("Mutation score")
    axes[0].set_ylim(-0.03, 1.03)
    axes[0].grid(True, axis="y", color="#d9d9d9", linewidth=0.7)
    axes[0].set_axisbelow(True)

    # Panel 2: average complexity vs mutation score scatter.
    axes[1].set_title("Complexity vs mutation score", fontsize=11, weight="bold")
    colors = _module_color_map(sorted(data["module"].unique()))
    for module, group in data.groupby("module"):
        axes[1].scatter(
            group["avg_complexity"],
            group["mutation_score"],
            s=46,
            alpha=0.85,
            color=colors[module],
            edgecolor="white",
            linewidth=0.8,
            label=module,
        )
    if data["avg_complexity"].nunique() > 1 and len(data) >= 3:
        slope, intercept = np.polyfit(data["avg_complexity"], data["mutation_score"], 1)
        xs = np.linspace(data["avg_complexity"].min(), data["avg_complexity"].max(), 100)
        axes[1].plot(xs, slope * xs + intercept, color="#333333", linestyle="--", linewidth=1.6)
    axes[1].set_xlabel(FEATURE_LABELS["avg_complexity"])
    axes[1].set_ylabel("Mutation score")
    axes[1].set_ylim(-0.03, 1.03)
    axes[1].grid(True, color="#d9d9d9", linewidth=0.7)
    axes[1].set_axisbelow(True)
    axes[1].legend(fontsize=7, frameon=False)

    # Panel 3: per-module average of mutation score, line coverage, execution rate.
    axes[2].set_title("Mean outcome per module", fontsize=11, weight="bold")
    module_means = (
        data.groupby("module")[["mutation_score", "line_coverage", "execution_success"]]
        .mean(numeric_only=True)
        .sort_index()
    )
    x = np.arange(len(module_means.index))
    width = 0.26
    series = (
        ("mutation_score", "Mutation score", "#2E6F9E"),
        ("line_coverage", "Line coverage / 100", "#3F8F6B"),
        ("execution_success", "Execution success", "#B07A2A"),
    )
    for offset, (column, label, color) in enumerate(series):
        values = module_means[column].fillna(0.0).to_numpy(dtype=float)
        if column == "line_coverage":
            values = values / 100.0
        axes[2].bar(x + (offset - 1) * width, values, width, label=label, color=color)
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(
        [label.split("_", 1)[0] for label in module_means.index],
        rotation=0,
        fontsize=9,
    )
    axes[2].set_ylim(0, 1.05)
    axes[2].set_ylabel("Score (0-1)")
    axes[2].legend(fontsize=7, frameon=False, loc="upper left")
    axes[2].grid(True, axis="y", color="#d9d9d9", linewidth=0.7)
    axes[2].set_axisbelow(True)

    fig.suptitle("RQ5 - Cyclomatic complexity and test-quality outcomes", fontsize=13, weight="bold")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.text(0.01, 0.005, _NOTE, fontsize=7, color="#666666")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=300, facecolor="white")
    plt.close(fig)
    return destination


def plot_failure_categories(frame: pd.DataFrame, destination: Path) -> Path:
    """RQ6: distribution of failure categories across evaluated suites."""
    plt = _pyplot()
    counts = (
        frame["failure_category"]
        .fillna("None")
        .astype(str)
        .value_counts()
        .reindex(list(FAILURE_CATEGORIES), fill_value=0)
    )
    counts = counts[counts > 0]
    if counts.empty:
        raise AnalysisError("no failure categories to plot")

    fig, axis = plt.subplots(figsize=(8.4, 5.0))
    colors = ["#3F8F6B" if label == "None" else "#D1495B" for label in counts.index]
    bars = axis.bar(counts.index, counts.to_numpy(), color=colors, width=0.62, edgecolor="white")
    axis.set_title("RQ6 - Failure category distribution", fontsize=13, weight="bold")
    axis.set_xlabel("Failure category")
    axis.set_ylabel("Number of suites")
    axis.grid(True, axis="y", color="#d9d9d9", linewidth=0.7)
    axis.set_axisbelow(True)
    total = int(counts.sum())
    for bar, value in zip(bars, counts.to_numpy()):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(total * 0.015, 0.05),
            f"{int(value)} ({100.0 * value / total:.1f}%)",
            ha="center",
            va="bottom",
            fontsize=8.5,
        )
    axis.set_ylim(0, max(counts.to_numpy()) * 1.22 + 0.2)
    fig.text(0.01, 0.005, _NOTE, fontsize=7, color="#666666")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=300, facecolor="white")
    plt.close(fig)
    return destination


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def _load_complexity_table(frame: pd.DataFrame) -> list[dict[str, Any]] | None:
    """Read ``complexity_report.json`` next to the metrics file, when present."""
    candidate = Path("results/complexity_report.json")
    if not candidate.is_file():
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    modules = payload.get("modules", {})
    if not isinstance(modules, dict):
        return None
    rows: list[dict[str, Any]] = []
    for module, item in sorted(modules.items()):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "module": module,
                "average": float(item.get("average_complexity", 0.0)),
                "maximum": int(item.get("max_complexity", 0)),
                "functions": len(item.get("functions", [])),
            }
        )
    return rows or None


def build_report(
    frame: pd.DataFrame,
    summary: pd.DataFrame,
    correlations: pd.DataFrame,
    figure_paths: list[Path],
) -> str:
    """Render the markdown analysis report."""
    generated = frame[frame["generation_mode"] == "generated"]
    human = frame[frame["generation_mode"] == "human"]

    def mean_of(subset: pd.DataFrame, column: str) -> str:
        if column not in subset.columns or subset[column].dropna().empty:
            return "n/a"
        return f"{subset[column].mean():.2f}"

    lines: list[str] = []
    lines.append("# LLM Test-Quality Evaluation - Analysis Report")
    lines.append("")
    lines.append(
        "This report is generated automatically by `pipeline/analyzer.py` from "
        "`results/evaluation_metrics.csv`."
    )
    lines.append("")
    lines.append("## Corpus and measurement protocol")
    lines.append("")
    lines.append(f"- Benchmark modules: **{frame['module'].nunique()}** (CPB-6)")
    lines.append(f"- Evaluated suites: **{len(frame)}** rows")
    lines.append(f"- LLM/generated suites: **{len(generated)}**")
    lines.append(f"- Human baseline suites: **{len(human)}**")
    lines.append(
        "- Mutation engine: deterministic AST single-point mutations, each run "
        "in an isolated copy of the benchmark package."
    )
    lines.append("")
    lines.append("## Complexity of the CPB-6 corpus (RQ1)")
    lines.append("")
    complexity = _load_complexity_table(frame)
    if complexity is not None:
        lines.append("| Module | Avg CC | Max CC | Functions |")
        lines.append("| --- | ---: | ---: | ---: |")
        for row in complexity:
            lines.append(
                f"| {row['module']} | {row['average']:.2f} | {row['maximum']} | "
                f"{row['functions']} |"
            )
        lines.append("")
        lines.append(
            "Average CC is the radon block average (classes, properties and "
            "exception shells included); max CC is the highest single block."
        )
    else:
        lines.append("_Run `run_experiments.py` to produce `complexity_report.json`._")
    lines.append("")
    lines.append("## Headline numbers")
    lines.append("")
    lines.append(
        "Coverage and mutation means are computed over suites where that metric "
        "is defined: mutation testing is only attempted on suites that pass "
        "cleanly, so the mutation mean has a smaller denominator than the "
        "coverage mean. Table values therefore exclude `NaN` rows rather than "
        "treating an unscored suite as zero."
    )
    lines.append("")
    lines.append("| Metric | Generated (mean) | Human baseline (mean) |")
    lines.append("| --- | ---: | ---: |")
    for column in (
        "line_coverage",
        "branch_coverage",
        "mutation_score",
        "total_tests",
        "assertions_per_test",
        "execution_time_s",
    ):
        lines.append(
            f"| {column} | {mean_of(generated, column)} | {mean_of(human, column)} |"
        )
    lines.append("")
    if "execution_success" in frame.columns:
        success = generated["execution_success"].mean() if not generated.empty else float("nan")
        collection = (
            generated["collection_success"].mean() if not generated.empty else float("nan")
        )
        lines.append(
            f"- Collection success rate (generated): **{100.0 * collection:.1f}%**"
        )
        lines.append(f"- Execution success rate (generated): **{100.0 * success:.1f}%**")
        lines.append("")

    lines.append("## Research questions")
    lines.append("")
    answers = {
        "RQ2": "Does line coverage predict mutation score?",
        "RQ3": "Does branch coverage predict mutation score?",
        "RQ5a": "Does module complexity predict execution success?",
        "RQ5b": "Does module complexity predict mutation score?",
        "EXTRA1": "Does the number of tests predict mutation score?",
        "EXTRA2": "Do assertions per test predict mutation score?",
    }
    for question, description in answers.items():
        subset = correlations[
            (correlations["question"] == question) & (correlations["scope"] == "generated")
        ]
        lines.append(f"### {question} - {description}")
        lines.append("")
        if subset.empty:
            lines.append("_Not estimable from the current run._")
            lines.append("")
            continue
        row = subset.iloc[0]
        rho = row.get("spearman_rho")
        p_value = row.get("p_value")
        rho_text = "n/a" if pd.isna(rho) else f"{float(rho):+.3f}"
        p_text = "n/a" if pd.isna(p_value) else f"{float(p_value):.4f}"
        lines.append(
            f"Spearman rho = **{rho_text}** (p = {p_text}, n = {int(row['n'])}); "
            f"interpretation: {_interpret(None if pd.isna(rho) else float(rho))}."
        )
        lines.append("")

    lines.append("## Failure taxonomy (RQ6)")
    lines.append("")
    counts = frame["failure_category"].value_counts()
    for category in FAILURE_CATEGORIES:
        if category in counts:
            lines.append(f"- `{category}`: {int(counts[category])}")
    lines.append("")

    lines.append("## Figures")
    lines.append("")
    for figure in figure_paths:
        lines.append(f"![{figure.stem}]({figure.relative_to(figure.parent.parent).as_posix()})")
        lines.append("")

    lines.append("## Caveats")
    lines.append("")
    lines.append(
        "- The mock corpus is synthetic and deterministic; absolute scores are "
        "illustrative and should be replaced by live-API runs (`--api`) for "
        "publication."
    )
    lines.append(
        "- Mutation scores are only defined for suites that pass cleanly, because "
        "a failing suite would otherwise score high for the wrong reason."
    )
    lines.append(
        "- Spearman p-values with $n < 10$ are indicative only; the pipeline "
        "reports them transparently rather than gating on significance."
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run_analysis(
    paths: ProjectPaths,
    metrics_path: Path | None = None,
    make_figures: bool = True,
) -> AnalysisOutput:
    """Run the full analysis and write every artefact."""
    metrics = metrics_path or (paths.results_dir / "evaluation_metrics.csv")
    frame = load_metrics(metrics)
    summary = compute_summary(frame)
    correlations = compute_correlations(frame)

    paths.results_dir.mkdir(parents=True, exist_ok=True)
    paths.figures_dir.mkdir(parents=True, exist_ok=True)
    paths.reports_dir.mkdir(parents=True, exist_ok=True)

    summary_path = paths.results_dir / "summary_statistics.csv"
    correlation_path = paths.results_dir / "correlation_analysis.csv"
    summary.to_csv(summary_path, index=False)
    correlations.to_csv(correlation_path, index=False)

    figures: list[Path] = []
    if make_figures:
        # RQ2/RQ3/RQ5 figures describe the generated corpus, matching the
        # `generated` scope of the correlation table; the human baselines are
        # reported separately in the tables and text.
        generated = frame[frame["generation_mode"] == "generated"]
        figure_frame = generated if not generated.empty else frame
        coverage_rows = figure_frame.dropna(subset=["mutation_score"])
        if not coverage_rows.empty and coverage_rows["line_coverage"].notna().any():
            figures.append(
                plot_coverage_vs_mutation(
                    figure_frame, paths.figures_dir / "rq2_rq3_coverage_vs_mutation.png"
                )
            )
            figures.append(
                plot_complexity_vs_scores(
                    figure_frame, paths.figures_dir / "rq5_complexity_vs_scores.png"
                )
            )
        figures.append(
            plot_failure_categories(frame, paths.figures_dir / "rq6_failure_categories.png")
        )

    report = build_report(frame, summary, correlations, figures)
    report_path = paths.reports_dir / "analysis_report.md"
    report_path.write_text(report, encoding="utf-8")

    return AnalysisOutput(
        summary_path=summary_path,
        correlation_path=correlation_path,
        report_path=report_path,
        figures=figures,
        summary=summary,
        correlations=correlations,
    )


__all__ = [
    "AnalysisError",
    "AnalysisOutput",
    "analysis",
    "build_report",
    "compute_correlations",
    "compute_summary",
    "load_metrics",
    "plot_complexity_vs_scores",
    "plot_coverage_vs_mutation",
    "plot_failure_categories",
    "run_analysis",
]

# Backwards-compatible alias for callers that use ``analyzer.analysis``.
analysis = run_analysis
