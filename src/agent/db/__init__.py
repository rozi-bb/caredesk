"""Operational database of the nursing home."""

from datetime import date
from pathlib import Path

# "Today" inside the synthetic data. Fixed so that answers about "today"
# do not change from one day to the next and evaluations stay comparable.
REFERENCE_DATE = date(2026, 10, 5)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
