"""Controlled benchmark modules (CPB-6) used by the LLM test-quality study.

CPB-6 is a six-module corpus spanning increasing cyclomatic complexity:

===== ============================================ ==========================
ID    Module                                       Target complexity band
===== ============================================ ==========================
M1    :mod:`benchmark.m1_arithmetic`                low          (1-3)
M2    :mod:`benchmark.m2_string_utils`              low-medium   (2-4)
M3    :mod:`benchmark.m3_validation`                medium       (3-5)
M4    :mod:`benchmark.m4_grade_calc`                medium       (4-6)
M5    :mod:`benchmark.m5_inventory`                 medium-high  (5-8)
M6    :mod:`benchmark.m6_bank_account`              high         (6-10)
===== ============================================ ==========================

Every module is pure Python, standard-library only, and free of I/O, network,
database, GUI and wall-clock dependencies so that measurements are exactly
reproducible on any machine.
"""

from __future__ import annotations

__all__ = [
    "m1_arithmetic",
    "m2_string_utils",
    "m3_validation",
    "m4_grade_calc",
    "m5_inventory",
    "m6_bank_account",
]

#: Canonical ordering of the corpus, used by the pipeline and the analyser.
MODULE_ORDER: tuple[str, ...] = (
    "m1_arithmetic",
    "m2_string_utils",
    "m3_validation",
    "m4_grade_calc",
    "m5_inventory",
    "m6_bank_account",
)

#: Human-readable labels for figures and report tables.
MODULE_LABELS: dict[str, str] = {
    "m1_arithmetic": "M1 Arithmetic",
    "m2_string_utils": "M2 String Utils",
    "m3_validation": "M3 Validation",
    "m4_grade_calc": "M4 Grade Calc",
    "m5_inventory": "M5 Inventory",
    "m6_bank_account": "M6 Bank Account",
}
