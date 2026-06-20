"""Step 1 - load the raw air raid alerts dataset from disk."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

# Columns we expect in the official Ukrainian dataset.
EXPECTED_COLUMNS = [
    "oblast",
    "raion",
    "hromada",
    "level",
    "started_at",
    "finished_at",
    "source",
]


def load_raw_data(csv_path: str | Path) -> pd.DataFrame:
    """Read the raw alerts CSV into a pandas DataFrame.

    Parameters
    ----------
    csv_path:
        Path to ``official_data_uk.csv`` inside ``data/raw/``.

    Returns
    -------
    pd.DataFrame
        One row per raw alert record, with the seven source columns.

    Raises
    ------
    FileNotFoundError
        If the file does not exist at the given path.
    ValueError
        If the file does not have the expected columns.
    """
    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(
            f"Data file not found: {csv_path}. "
            "Make sure 'official_data_uk.csv' is placed in data/raw/."
        )

    df = pd.read_csv(csv_path)

    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Unexpected file format. Missing columns: {missing}. "
            f"Found columns: {list(df.columns)}"
        )

    return df
