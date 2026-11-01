"""Evaluation pipeline for the CPB-6 LLM test-quality study."""

from __future__ import annotations

from .config import FAILURE_CATEGORIES, PIPELINE_VERSION, RESULT_COLUMNS, ProjectPaths

__all__ = [
    "FAILURE_CATEGORIES",
    "PIPELINE_VERSION",
    "ProjectPaths",
    "RESULT_COLUMNS",
]

__version__ = PIPELINE_VERSION
