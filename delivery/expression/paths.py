from __future__ import annotations

import re
from pathlib import Path

TIMESERIES_DIRNAME = "timeseries"
RESULTS_DIRNAME = "results"

_WORKSPACE_METRICS_STEM = re.compile(r"^sc\d+_ch\d+$")


def is_workspace_metrics_timeseries_csv(path: Path) -> bool:
    """True when the filename stem matches ``sc{S}_ch{C}`` (workspace metrics convention)."""

    return bool(_WORKSPACE_METRICS_STEM.fullmatch(path.stem))


def workspace_timeseries_dir(workspace: Path) -> Path:
    return workspace.resolve() / TIMESERIES_DIRNAME


def workspace_results_dir(workspace: Path) -> Path:
    return workspace.resolve() / RESULTS_DIRNAME


def discover_timeseries_csvs(timeseries_dir: Path) -> list[Path]:
    if not timeseries_dir.is_dir():
        raise ValueError(
            f"Expected {TIMESERIES_DIRNAME}/ directory at {timeseries_dir}. "
            "Run delivery expression timeseries first."
        )
    csvs = sorted(timeseries_dir.glob("*.csv"), key=lambda path: path.name)
    if not csvs:
        raise ValueError(f"No CSV metrics files in {timeseries_dir}")
    metrics = [path for path in csvs if is_workspace_metrics_timeseries_csv(path)]
    if not metrics:
        raise ValueError(
            f"No workspace metrics CSV files (expected stem sc{{slide}}_ch{{channel}}.csv) in {timeseries_dir}"
        )
    return metrics
