from __future__ import annotations

import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Callable

import pandas as pd
import typer

from lisca.analysis.roi import (
    compute_roi_metrics,
    quantile_column_name,
    write_metrics_csv,
)
from lisca.data.roi import position_dir, read_position_index, validate_channel_index
from lisca.data.slide import SlideChannelMapping, load_slide_mapping


HELP = (
    "Read cropped ROI TIFF timelapses from roi/PosN, compute per-ROI intensity "
    "metrics for each slide channel's mapped image channel, and write one long-form CSV "
    "per slide channel as scS_chC.csv under <workspace>/timeseries/."
)

OUTPUT_COLUMNS = ("pos", "roi", "t", "corrected")
DELIVERY_CORRECTION_QUARTILE = 0.25
CsvWrittenCallback = Callable[[int, Path, int], None]


@dataclass(frozen=True)
class SlideTimeseriesRunResult:
    written_outputs: list[tuple[int, Path, int]]
    skipped_positions: dict[int, list[int]]


load_slide_position_groups = load_slide_mapping


def default_slide_timeseries_csv_path(
    workspace: Path,
    slide_channel: int,
    image_channel: int,
) -> Path:
    csv_path = workspace / "timeseries" / f"sc{slide_channel}_ch{image_channel}.csv"
    return csv_path.resolve()


def consolidate_metrics(dataframes: list[pd.DataFrame]) -> pd.DataFrame:
    if not dataframes:
        raise ValueError('No position metrics to consolidate')
    return pd.concat(dataframes, ignore_index=True).sort_values(['pos', 'roi', 't']).reset_index(drop=True)


def simplify_metrics(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[:, list(OUTPUT_COLUMNS)].sort_values(['pos', 'roi', 't']).reset_index(drop=True)


def apply_delivery_correction(df: pd.DataFrame, *, correction_quartile: float = DELIVERY_CORRECTION_QUARTILE) -> pd.DataFrame:
    corrected_column = quantile_column_name(correction_quartile)
    if corrected_column not in df.columns:
        raise ValueError(
            f"Quartiles must include {correction_quartile:.2f} so delivery corrected intensity can be computed"
        )

    corrected_df = df.copy()
    corrected_df["corrected"] = corrected_df["sum"] - corrected_df["area"] * corrected_df[corrected_column]
    return corrected_df


def _run_position_metrics(
    workspace: Path,
    *,
    slide_channel: int,
    image_channel: int,
    resolved_pos: int,
    correction_quartile: float,
) -> tuple[int, int, int, pd.DataFrame | None]:
    try:
        pos_dir = position_dir(workspace, resolved_pos)
    except ValueError:
        return (slide_channel, image_channel, resolved_pos, None)

    index = read_position_index(pos_dir)
    validate_channel_index(index, image_channel)
    metrics_df = compute_roi_metrics(
        pos_dir,
        index,
        channel=image_channel,
        quartiles=[correction_quartile],
    )
    return (slide_channel, image_channel, resolved_pos, metrics_df)


def _position_timeseries_task(
    payload: tuple[str, int, int, int, float],
) -> tuple[int, int, int, pd.DataFrame | None]:
    workspace_str, slide_channel, image_channel, resolved_pos, correction_quartile = payload
    return _run_position_metrics(
        Path(workspace_str),
        slide_channel=slide_channel,
        image_channel=image_channel,
        resolved_pos=resolved_pos,
        correction_quartile=correction_quartile,
    )


def _write_slide_channel_csv(
    workspace: Path,
    *,
    slide_channel: int,
    image_channel: int,
    position_metrics_dfs: list[pd.DataFrame],
    correction_quartile: float,
) -> tuple[Path, int]:
    combined_df = consolidate_metrics(position_metrics_dfs)
    resolved_output_csv = default_slide_timeseries_csv_path(
        workspace=workspace,
        slide_channel=slide_channel,
        image_channel=image_channel,
    )
    write_metrics_csv(
        simplify_metrics(
            apply_delivery_correction(combined_df, correction_quartile=correction_quartile)
        ),
        resolved_output_csv,
    )
    return (resolved_output_csv, len(position_metrics_dfs))


@dataclass
class SlideChannelTimeseriesWriter:
    """Drops each slide position from a pending list as results arrive; writes CSV when the list is empty."""

    workspace: Path
    slide_channel: int
    image_channel: int
    correction_quartile: float
    _pending_positions: list[int]
    _metrics_dfs: list[pd.DataFrame] = field(default_factory=list, repr=False)

    def observe(self, resolved_pos: int, metrics_df: pd.DataFrame | None) -> tuple[Path, int] | None:
        try:
            self._pending_positions.remove(resolved_pos)
        except ValueError as exc:
            raise RuntimeError(
                f"slide channel {self.slide_channel}: unexpected or duplicate result for position {resolved_pos}"
            ) from exc
        if metrics_df is not None:
            self._metrics_dfs.append(metrics_df)
        if self._pending_positions:
            return None
        if not self._metrics_dfs:
            self._metrics_dfs.clear()
            return None
        written = _write_slide_channel_csv(
            self.workspace,
            slide_channel=self.slide_channel,
            image_channel=self.image_channel,
            position_metrics_dfs=self._metrics_dfs,
            correction_quartile=self.correction_quartile,
        )
        self._metrics_dfs.clear()
        return written


def _receivers_for_slide(
    workspace: Path,
    slide_positions: dict[int, SlideChannelMapping],
    correction_quartile: float,
) -> dict[int, SlideChannelTimeseriesWriter]:
    receivers: dict[int, SlideChannelTimeseriesWriter] = {}
    for slide_channel, entry in slide_positions.items():
        receivers[slide_channel] = SlideChannelTimeseriesWriter(
            workspace=workspace,
            slide_channel=slide_channel,
            image_channel=entry.image_channel,
            correction_quartile=correction_quartile,
            _pending_positions=list(entry.positions),
        )
    return receivers


def _consume_position_row(
    row: tuple[int, int, int, pd.DataFrame | None],
    *,
    receivers: dict[int, SlideChannelTimeseriesWriter],
    skipped_positions: dict[int, list[int]],
    written_by_channel: dict[int, tuple[Path, int]],
) -> None:
    slide_channel, _image_channel, resolved_pos, metrics_df = row
    if metrics_df is None:
        skipped_positions.setdefault(slide_channel, []).append(resolved_pos)
    written = receivers[slide_channel].observe(resolved_pos, metrics_df)
    if written is not None:
        written_by_channel[slide_channel] = written


def run_slide_timeseries(
    workspace: Path,
    *,
    sample: Path,
    correction_quartile: float = DELIVERY_CORRECTION_QUARTILE,
    on_csv_written: CsvWrittenCallback | None = None,
    jobs: int = 1,
) -> SlideTimeseriesRunResult:
    if jobs < 1:
        raise ValueError(f"--jobs must be >= 1, got {jobs}")
    workspace = workspace.resolve()
    slide_path = sample.resolve()
    quantile_column_name(correction_quartile)
    slide_positions = load_slide_mapping(slide_path)
    channel_order = [slide_channel for slide_channel, _ in slide_positions.items()]
    position_tasks: list[tuple[str, int, int, int, float]] = [
        (str(workspace), slide_channel, entry.image_channel, resolved_pos, correction_quartile)
        for slide_channel, entry in slide_positions.items()
        for resolved_pos in entry.positions
    ]

    if not position_tasks:
        raise ValueError(f"{slide_path} defines no valid positions")

    receivers = _receivers_for_slide(workspace, slide_positions, correction_quartile)
    skipped_positions: dict[int, list[int]] = defaultdict(list)
    written_by_channel: dict[int, tuple[Path, int]] = {}

    if jobs == 1 or len(position_tasks) <= 1:
        for ws_str, slide_channel, image_channel, resolved_pos, cq in position_tasks:
            row = _run_position_metrics(
                Path(ws_str),
                slide_channel=slide_channel,
                image_channel=image_channel,
                resolved_pos=resolved_pos,
                correction_quartile=cq,
            )
            _consume_position_row(
                row,
                receivers=receivers,
                skipped_positions=skipped_positions,
                written_by_channel=written_by_channel,
            )
    else:
        max_workers = min(jobs, len(position_tasks), os.cpu_count() or jobs)
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_position_timeseries_task, t) for t in position_tasks]
            for fut in as_completed(futures):
                row = fut.result()
                _consume_position_row(
                    row,
                    receivers=receivers,
                    skipped_positions=skipped_positions,
                    written_by_channel=written_by_channel,
                )

    for receiver in receivers.values():
        if receiver._pending_positions:
            raise RuntimeError(
                f"slide channel {receiver.slide_channel}: still awaiting positions {sorted(receiver._pending_positions)}"
            )

    written_outputs: list[tuple[int, Path, int]] = []
    for slide_channel in channel_order:
        if slide_channel not in written_by_channel:
            continue
        resolved_output_csv, position_count = written_by_channel[slide_channel]
        written_outputs.append((slide_channel, resolved_output_csv, position_count))
        if on_csv_written is not None:
            on_csv_written(slide_channel, resolved_output_csv, position_count)

    if not written_outputs:
        if skipped_positions:
            skipped_summary = "; ".join(
                f"slide channel {slide_channel} -> {', '.join(str(pos) for pos in positions)}"
                for slide_channel, positions in sorted(skipped_positions.items())
            )
            raise ValueError(
                f"No ROI directories found for positions in {slide_path}. "
                f"Skipped positions: {skipped_summary}"
            )
        raise ValueError(f"{slide_path} defines no valid positions")

    return SlideTimeseriesRunResult(
        written_outputs=written_outputs,
        skipped_positions=skipped_positions,
    )


def format_written_timeseries_csv_message(slide_channel: int, output_csv: Path, position_count: int) -> str:
    return (
        f"Wrote metrics CSV for slide channel {slide_channel} with {position_count} positions: "
        f"{output_csv}"
    )


def format_skipped_positions_message(skipped_positions: dict[int, list[int]]) -> str:
    total_skipped_positions = sum(len(positions) for positions in skipped_positions.values())
    skipped_summary = "; ".join(
        f"slide channel {slide_channel} -> {', '.join(str(pos) for pos in positions)}"
        for slide_channel, positions in sorted(skipped_positions.items())
    )
    return f"Skipped {total_skipped_positions} missing positions from slide mapping: {skipped_summary}"


def cli(
    workspace: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        metavar="WORKSPACE",
        help="Workspace containing roi/PosN/index.json and Roi*.tif files.",
    ),
    sample: Path = typer.Option(
        ...,
        "--sample",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help=(
            "Microscopy slide mapping JSON per slide_channel: positions, image_channel, and sample_name. "
            "Process every position from every slide channel in the file and write "
            "one CSV per slide channel."
        ),
    ),
    correction_quartile: float = typer.Option(
        DELIVERY_CORRECTION_QUARTILE,
        "--correction-quartile",
        help="Single quartile used to compute the corrected intensity column.",
    ),
    jobs: Annotated[
        int,
        typer.Option(
            "--jobs",
            min=1,
            help=(
                "Number of worker processes to use across per-position ROI metric extractions "
                "(each slide channel streams results in the main process, writes CSV when every "
                "position has reported, then drops accumulated DataFrames). "
                "Use scripts/delivery-expression-analyze.ps1 for a CPU-based default."
            ),
        ),
    ] = 1,
) -> None:
    result = run_slide_timeseries(
        workspace,
        sample=sample,
        correction_quartile=correction_quartile,
        on_csv_written=lambda slide_channel, resolved_output_csv, position_count: print(
            format_written_timeseries_csv_message(slide_channel, resolved_output_csv, position_count)
        ),
        jobs=jobs,
    )
    if result.skipped_positions:
        print(format_skipped_positions_message(result.skipped_positions))


def main(argv: list[str] | None = None, *, prog_name: str = "delivery expression timeseries") -> None:
    from delivery.expression import run_subcommand

    run_subcommand(cli, argv, prog_name=prog_name)


if __name__ == "__main__":
    main()
