"""Human-authored ground-truth test suites for the CPB-6 benchmark.

These suites are the reference point of the study: each one is written by a
human to cover the documented contract of one benchmark module, including
boundary conditions and expected exceptions.  The pipeline measures them with
exactly the same instrumentation (pytest, coverage.py, the AST mutator) as the
LLM-generated suites so that comparisons are apples-to-apples.
"""

from __future__ import annotations

__all__ = [
    "test_m1_human",
    "test_m2_human",
    "test_m3_human",
    "test_m4_human",
    "test_m5_human",
    "test_m6_human",
]
