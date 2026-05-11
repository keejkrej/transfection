from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import typer

from transfection.analysis.roi import load_timeseries_csv

from . import paths


GROUP_COLUMNS = ("pos", "roi")
OUTPUT_COLUMNS = ("slide_channel", "pos", "roi", "auc")

HELP = (
    "Integrate every metrics CSV in <workspace>/timeseries/ and write "
    f"<workspace>/{paths.RESULTS_DIRNAME}/auc.csv."
)


def default_results_table_csv_path(results_dir: Path, *, kind: str) -> Path:
    """Write ``auc.csv`` or ``fit.csv`` under ``results_dir``."""

    return (results_dir.resolve() / f"{kind}.csv").resolve()


def run_auc(timeseries_csvs: list[Path], *, interval: float, output_csv: Path | None) -> Path:
    if interval <= 0:
        raise ValueError(f"--interval must be > 0, got {interval}")

    resolved_csvs = sorted((csv_path.resolve() for csv_path in timeseries_csvs), key=lambda path: path.name)
    auc_df = compute_auc_table(resolved_csvs, interval=interval)
    resolved_output_csv = default_output_csv_path(resolved_csvs, output_csv)
    write_auc_csv(auc_df, resolved_output_csv)
    return resolved_output_csv


def default_output_csv_path(
    timeseries_csvs: list[Path],
    output_csv: Path | None,
    *,
    results_dir: Path | None = None,
) -> Path:
    if output_csv is not None:
        return output_csv.resolve()
    if results_dir is not None:
        return default_results_table_csv_path(results_dir, kind="auc")
    return timeseries_csvs[0].with_name("auc.csv").resolve()


def parse_slide_channel(csv_path: Path) -> int | None:
    match = re.fullmatch(r"sc(\d+)_ch\d+", csv_path.stem)
    if match is None:
        return None
    return int(match.group(1))


def integrate_trace(trace_df: pd.DataFrame, *, interval: float) -> float:
    sorted_df = trace_df.sort_values("t").reset_index(drop=True)
    if len(sorted_df) < 2:
        return 0.0

    times = sorted_df["t"].astype(float).to_numpy() * interval
    values = sorted_df["corrected"].astype(float).to_numpy()
    widths = times[1:] - times[:-1]
    heights = (values[:-1] + values[1:]) * 0.5
    return float((widths * heights).sum())


def compute_auc_table(timeseries_csvs: list[Path], *, interval: float) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for csv_path in timeseries_csvs:
        df = load_timeseries_csv(csv_path)
        slide_channel = parse_slide_channel(csv_path)
        group_columns = [column for column in GROUP_COLUMNS if column in df.columns]
        if not group_columns:
            raise ValueError(f"{csv_path} has no supported grouping columns: {GROUP_COLUMNS}")

        for group_key, trace_df in df.groupby(group_columns, sort=True):
            if not isinstance(group_key, tuple):
                group_key = (group_key,)
            row = dict(zip(group_columns, group_key, strict=True))
            sorted_df = trace_df.sort_values("t").reset_index(drop=True)
            row.update(
                {
                    "slide_channel": slide_channel,
                    "auc": integrate_trace(sorted_df, interval=interval),
                }
            )
            rows.append(row)

    if not rows:
        raise ValueError("No AUC rows produced")

    result = pd.DataFrame(rows)
    sort_columns = [column for column in ("slide_channel", *GROUP_COLUMNS) if column in result.columns]
    return result.sort_values(sort_columns).reset_index(drop=True).loc[:, list(OUTPUT_COLUMNS)]


def write_auc_csv(df: pd.DataFrame, output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)


def format_written_auc_csv_message(output_csv: Path) -> str:
    return f"Wrote AUC CSV: {output_csv}"


def cli(
    workspace: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        metavar="WORKSPACE",
        help=f"Workspace with {paths.TIMESERIES_DIRNAME}/ containing ROI metrics CSV files.",
    ),
    interval: float = typer.Option(
        ...,
        "--interval",
        min=0.0,
        help="Frame interval in minutes used to convert t into time before integration.",
    ),
) -> None:
    timeseries_csvs = paths.discover_timeseries_csvs(paths.workspace_timeseries_dir(workspace))
    results_dir = paths.workspace_results_dir(workspace)
    output_csv = default_output_csv_path(timeseries_csvs, None, results_dir=results_dir)
    resolved_output_csv = run_auc(timeseries_csvs, interval=interval, output_csv=output_csv)
    print(format_written_auc_csv_message(resolved_output_csv))


def main(argv: list[str] | None = None, *, prog_name: str = "transfection analyze auc") -> None:
    from transfection.analyze.cli import run_subcommand

    run_subcommand(cli, argv, prog_name=prog_name)


if __name__ == "__main__":
    main()
