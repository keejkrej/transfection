from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from transfection.app import app
from transfection.services.timeseries import (
    DELIVERY_CORRECTION_QUARTILE,
    format_skipped_positions_message,
    format_written_timeseries_csv_message,
    run_timeseries,
)

NAME = "timeseries"
HELP = (
    "Read cropped ROI TIFF timelapses from roi/PosN, compute per-ROI intensity "
    "metrics using segment masks for each slide channel's mapped signal channel, and write "
    "one long-form CSV and parallel XLSX per slide channel as scS_chC.csv and scS_chC.xlsx "
    "under <workspace>/timeseries/."
)


@app.command(NAME, help=HELP)
def timeseries(
    workspace: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            metavar="WORKSPACE",
            help="Workspace containing roi/PosN/index.json and Roi*.tif files.",
        ),
    ],
    sample: Annotated[
        Path,
        typer.Option(
            "--sample",
            exists=True,
            file_okay=True,
            dir_okay=False,
            help=(
                "Microscopy slide mapping JSON per slide_channel: positions, signal_channel, mask_channel, "
                "and sample_name. "
                "Process every position from every slide channel in the file and write "
                "one CSV per slide channel."
            ),
        ),
    ],
    mask_channel: Annotated[
        int | None,
        typer.Option(
            "--mask-channel",
            min=0,
            help="Override mask TIFF channel to read. Defaults to each slide mapping's mask_channel.",
        ),
    ] = None,
    correction_quartile: Annotated[
        float,
        typer.Option(
            "--correction-quartile",
            help="Deprecated; timeseries now uses segment masks for background correction.",
        ),
    ] = DELIVERY_CORRECTION_QUARTILE,
    jobs: Annotated[
        int,
        typer.Option(
            "--jobs",
            min=1,
            help=(
                "Number of worker processes to use across per-position ROI metric extractions "
                "(each slide channel streams results in the main process, writes CSV when every "
                "position has reported, then drops accumulated DataFrames). "
                "Use transfection-analyze.ps1 for a CPU-based default."
            ),
        ),
    ] = 1,
) -> None:
    result = run_timeseries(
        workspace=workspace,
        sample=sample,
        mask_channel=mask_channel,
        correction_quartile=correction_quartile,
        on_csv_written=lambda slide_channel, resolved_output_csv, position_count: typer.echo(
            format_written_timeseries_csv_message(slide_channel, resolved_output_csv, position_count)
        ),
        jobs=jobs,
    )
    if result.skipped_positions:
        typer.echo(format_skipped_positions_message(result.skipped_positions))
