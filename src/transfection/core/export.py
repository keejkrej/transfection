from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

XLSX_EXTENSION = ".xlsx"


def parallel_xlsx_path(csv_path: Path) -> Path:
    return csv_path.with_suffix(XLSX_EXTENSION)


def write_csv_and_parallel_xlsx(df: pd.DataFrame, output_csv: Path) -> Path:
    output_csv = output_csv.resolve()
    output_xlsx = parallel_xlsx_path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    def write_csv() -> None:
        df.to_csv(output_csv, index=False)

    def write_xlsx() -> None:
        df.to_excel(output_xlsx, index=False, engine="openpyxl")

    with ThreadPoolExecutor(max_workers=2) as executor:
        csv_future = executor.submit(write_csv)
        xlsx_future = executor.submit(write_xlsx)
        csv_future.result()
        xlsx_future.result()

    return output_xlsx
