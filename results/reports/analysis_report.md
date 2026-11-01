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
| line_coverage | 99.60 | 99.35 |
| branch_coverage | 99.44 | 98.85 |
| mutation_score | 0.96 | 0.76 |
| total_tests | 62.40 | 35.33 |
| assertions_per_test | 1.23 | 1.27 |
| execution_time_s | 0.40 | 0.36 |

- Collection success rate (generated): **100.0%**
- Execution success rate (generated): **43.3%**

## Research questions

### RQ2 - Does line coverage predict mutation score?

Spearman rho = **+0.608** (p = 0.0274, n = 13); interpretation: strong positive.

### RQ3 - Does branch coverage predict mutation score?

Spearman rho = **+0.608** (p = 0.0274, n = 13); interpretation: strong positive.

### RQ5a - Does module complexity predict execution success?

Spearman rho = **-0.532** (p = 0.0025, n = 30); interpretation: moderate negative.

### RQ5b - Does module complexity predict mutation score?

Spearman rho = **-0.574** (p = 0.0400, n = 13); interpretation: moderate negative.

### EXTRA1 - Does the number of tests predict mutation score?

Spearman rho = **-0.250** (p = 0.4100, n = 13); interpretation: weak negative.

### EXTRA2 - Do assertions per test predict mutation score?

Spearman rho = **-0.572** (p = 0.0413, n = 13); interpretation: moderate negative.

## Failure taxonomy (RQ6)

- `None`: 19
- `AssertionFailure`: 14
- `RuntimeError`: 3

## Figures

![rq2_rq3_coverage_vs_mutation](figures/rq2_rq3_coverage_vs_mutation.png)

![rq5_complexity_vs_scores](figures/rq5_complexity_vs_scores.png)

![rq6_failure_categories](figures/rq6_failure_categories.png)

## Caveats

- Generated suites were produced by the live `deepseek` API using model `deepseek-chat`; the corpus is not synthetic.
- Only **13/30** generated suites executed cleanly, so mutation scores exist for that subset only.
- Mutation scores are only defined for suites that pass cleanly, because a failing suite would otherwise score high for the wrong reason.
- Spearman p-values with $n < 10$ are indicative only; the pipeline reports them transparently rather than gating on significance.
