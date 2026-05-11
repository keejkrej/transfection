from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import typer

from lisca.analysis.roi import load_timeseries_csv

from . import paths


GROUP_COLUMNS = ("pos", "roi")
OUTPUT_COLUMNS = ("slide_channel", "pos", "roi", "auc")

HELP = (
    "Integrate every metrics CSV in <workspace>/timeseries/ and write "
    f"<workspace>/{paths.RESULTS_DIRNAME}/auc.csv."
)


def is_compact_channel_bundle_stem(stem: str) -> bool:
    """True when the aggregate stem is only ch{n} (one shared microscopy channel)."""

    return bool(re.fullmatch(r"ch\d+", stem))


def uses_bare_results_filenames(aggregate_stem: str) -> bool:
    """Compact stem ch{n} or the fallback label when stems disagree (`timeseries`)."""

    return is_compact_channel_bundle_stem(aggregate_stem) or aggregate_stem == "timeseries"


def results_plot_grid_basename(aggregate_stem: str) -> str:
    if uses_bare_results_filenames(aggregate_stem):
        return "overview"
    return aggregate_stem


def default_results_table_csv_path(results_dir: Path, aggregate_stem: str, *, kind: str) -> Path:
    """kind is 'auc' or 'fit' -> auc.csv / fit.csv or {stem}_auc.csv."""

    name = f"{kind}.csv" if uses_bare_results_filenames(aggregate_stem) else f"{aggregate_stem}_{kind}.csv"
    return (results_dir.resolve() / name).resolve()


def run_auc(timeseries_csvs: list[Path], *, interval: float, output_csv: Path | None) -> Path:
    if interval <= 0:
        raise ValueError(f"--interval must be > 0, got {interval}")

    resolved_csvs = sorted((csv_path.resolve() for csv_path in timeseries_csvs), key=lambda path: path.name)
    auc_df = compute_auc_table(resolved_csvs, interval=interval)
    resolved_output_csv = default_output_csv_path(resolved_csvs, output_csv)
    write_auc_csv(auc_df, resolved_output_csv)
    return resolved_output_csv


def strip_slide_channel_segment(stem: str) -> str:
    return re.sub(r"^sc\d+_", "", stem)


def normalize_output_stem(csv_path: Path) -> str:
    return strip_slide_channel_segment(csv_path.stem)


def aggregate_output_stem(timeseries_csvs: list[Path]) -> str:
    normalized_stems = {normalize_output_stem(csv_path) for csv_path in timeseries_csvs}
    if len(normalized_stems) == 1:
        stem = next(iter(normalized_stems))
        return stem if stem != "" else "timeseries"
    if len(timeseries_csvs) == 1:
        stem = normalize_output_stem(timeseries_csvs[0])
        return stem if stem != "" else "timeseries"
    return "timeseries"


def aggregate_output_stem_candidates(csv_path: Path) -> set[str]:
    return {normalize_output_stem(csv_path)}


def default_output_csv_path(
    timeseries_csvs: list[Path],
    output_csv: Path | None,
    *,
    results_dir: Path | None = None,
) -> Path:
    if output_csv is not None:
        return output_csv.resolve()
    stem = aggregate_output_stem(timeseries_csvs)
    if results_dir is not None:
        return default_results_table_csv_path(results_dir, stem, kind="auc")
    name = "auc.csv" if uses_bare_results_filenames(stem) else f"{stem}_auc.csv"
    return timeseries_csvs[0].with_name(name).resolve()


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


def main(argv: list[str] | None = None, *, prog_name: str = "delivery expression auc") -> None:
    from delivery.expression import run_subcommand

    run_subcommand(cli, argv, prog_name=prog_name)


if __name__ == "__main__":
    main()
