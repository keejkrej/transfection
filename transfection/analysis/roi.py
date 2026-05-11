from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from transfection.data.roi import PositionIndex, read_roi_stack, roi_frame_2d


DEFAULT_QUARTILES = "0.10,0.25,0.50,0.75,0.90"


def quantile_column_name(quartile: float) -> str:
    quartile_pct = quartile * 100.0
    if abs(quartile_pct - round(quartile_pct)) > 1e-9:
        raise ValueError(
            f"Quartiles must map to integer percentage column names, got {quartile}"
        )
    return f"q{int(round(quartile_pct))}"


def parse_quartiles(quartiles: str) -> list[float]:
    values: list[float] = []
    for raw_value in quartiles.split(","):
        value = float(raw_value.strip())
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"Quartiles must be between 0 and 1, got {value}")
        quantile_column_name(value)
        values.append(value)
    if not values:
        raise ValueError("At least one quartile is required")
    unique_values = sorted(set(values))
    if len(unique_values) != len(values):
        raise ValueError(f"Quartiles must be unique, got {quartiles}")
    return unique_values


def compute_roi_metrics(
    pos_dir: Path,
    index: PositionIndex,
    *,
    channel: int,
    quartiles: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, int | float | None]] = []
    for roi in index.rois:
        roi_path = pos_dir / roi.file_name
        if not roi_path.is_file():
            raise ValueError(f"Missing ROI TIFF referenced by index.json: {roi_path}")

        stack = read_roi_stack(roi_path, roi.shape)
        for timepoint in range(index.time_count):
            patch = np.asarray(
                roi_frame_2d(stack, index.axis_order, timepoint=timepoint, channel=channel),
                dtype=np.uint64,
            )
            quantile_values = np.quantile(patch, quartiles, method="linear")
            metrics = {
                quantile_column_name(quartile): float(quantile_value)
                for quartile, quantile_value in zip(quartiles, np.atleast_1d(quantile_values))
            }
            sum_value = int(patch.sum(dtype=np.uint64))
            rows.append(
                {
                    "pos": index.position,
                    "channel": channel,
                    "t": timepoint,
                    "roi": roi.roi,
                    "x": roi.x,
                    "y": roi.y,
                    "w": roi.w,
                    "h": roi.h,
                    "area": int(patch.size),
                    "sum": sum_value,
                    **metrics,
                }
            )

    if not rows:
        raise ValueError("No rows produced")
    return pd.DataFrame(rows).sort_values(["roi", "t"]).reset_index(drop=True)


def write_metrics_csv(df: pd.DataFrame, output_csv: Path) -> None:
    if df.empty:
        raise ValueError("No rows to write")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)


def load_timeseries_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    required = {"roi", "t", "corrected"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(
            f"{csv_path} is missing required columns for timeseries metrics: {sorted(missing)}"
        )
    sort_columns = ["roi", "t"]
    if "pos" in df.columns:
        sort_columns = ["pos", *sort_columns]
    return df.sort_values(sort_columns).reset_index(drop=True)
