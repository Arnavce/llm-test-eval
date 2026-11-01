# LLM Test-Quality Evaluation - Analysis Report

This report is generated automatically by `pipeline/analyzer.py` from `results/evaluation_metrics.csv`.

## Corpus and measurement protocol

- Benchmark modules: **6** (CPB-6)
- Evaluated suites: **36** rows
- LLM/generated suites: **30**
- Human baseline suites: **6**
- Mutation engine: deterministic AST single-point mutations, each run in an isolated copy of the benchmark package.

## Complexity of the CPB-6 corpus (RQ1)

| Module | Avg CC | Max CC | Functions |
| --- | ---: | ---: | ---: |
| m1_arithmetic | 1.67 | 3 | 6 |
| m2_string_utils | 2.00 | 4 | 6 |
| m3_validation | 5.57 | 11 | 7 |
| m4_grade_calc | 5.00 | 9 | 5 |
| m5_inventory | 3.50 | 5 | 12 |
| m6_bank_account | 3.22 | 7 | 18 |

Average CC is the radon block average (classes, properties and exception shells included); max CC is the highest single block.

## Headline numbers

Coverage and mutation means are computed over suites where that metric is defined: mutation testing is only attempted on suites that pass cleanly, so the mutation mean has a smaller denominator than the coverage mean. Table values therefore exclude `NaN` rows rather than treating an unscored suite as zero.

| Metric | Generated (mean) | Human baseline (mean) |
| --- | ---: | ---: |
| line_coverage | 60.34 | 99.35 |
| branch_coverage | 49.59 | 98.85 |
| mutation_score | 0.28 | 0.76 |
| total_tests | 3.30 | 35.33 |
| assertions_per_test | 1.86 | 1.27 |
| execution_time_s | 0.27 | 0.36 |

- Collection success rate (generated): **80.0%**
- Execution success rate (generated): **60.0%**

## Research questions

### RQ2 - Does line coverage predict mutation score?

Spearman rho = **+0.858** (p = 0.0000, n = 18); interpretation: very strong positive.

### RQ3 - Does branch coverage predict mutation score?

Spearman rho = **+0.911** (p = 0.0000, n = 18); interpretation: very strong positive.

### RQ5a - Does module complexity predict execution success?

Spearman rho = **+0.000** (p = 1.0000, n = 30); interpretation: no monotonic association.

### RQ5b - Does module complexity predict mutation score?

Spearman rho = **+0.082** (p = 0.7472, n = 18); interpretation: negligible positive.

### EXTRA1 - Does the number of tests predict mutation score?

Spearman rho = **+0.701** (p = 0.0012, n = 18); interpretation: strong positive.

### EXTRA2 - Do assertions per test predict mutation score?

Spearman rho = **+0.492** (p = 0.0380, n = 18); interpretation: moderate positive.

## Failure taxonomy (RQ6)

- `None`: 24
- `CollectionError`: 6
- `AssertionFailure`: 6

## Figures

![rq2_rq3_coverage_vs_mutation](figures/rq2_rq3_coverage_vs_mutation.png)

![rq5_complexity_vs_scores](figures/rq5_complexity_vs_scores.png)

![rq6_failure_categories](figures/rq6_failure_categories.png)

## Caveats

- The mock corpus is synthetic and deterministic; absolute scores are illustrative and should be replaced by live-API runs (`--api`) for publication.
- Mutation scores are only defined for suites that pass cleanly, because a failing suite would otherwise score high for the wrong reason.
- Spearman p-values with $n < 10$ are indicative only; the pipeline reports them transparently rather than gating on significance.
