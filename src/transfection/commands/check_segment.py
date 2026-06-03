from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from transfection.app import app
from transfection.services.check_segment import (
    format_skipped_positions_message,
    format_written_check_segment_video_message,
    run_check_segment,
)

NAME = "check-segment"
HELP = (
    "Overlay mask contours on the ROI TIFF signal and mask channels and write MP4 review videos "
    "under <workspace>/check-segment/PosN/. "
    "For manual mask QA; not part of transfection-analyze."
)

SAMPLE_HELP = (
    "Microscopy slide mapping JSON per slide_channel: positions, signal_channel, mask_channel, "
    "and sample_name. "
    "Review videos are written for every mapped position and ROI (mask and signal channels)."
)


@app.command(NAME, help=HELP)
def check_segment(
    workspace: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            metavar="WORKSPACE",
            help="Workspace containing roi/PosN/index.json, Roi*.tif files, and segment masks under mask/.",
        ),
    ],
    sample: Annotated[
        Path,
        typer.Option(
            "--sample",
            exists=True,
            file_okay=True,
            dir_okay=False,
            help=SAMPLE_HELP,
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            file_okay=False,
            dir_okay=True,
            help="Directory for MP4 outputs. Default: <workspace>/check-segment/.",
        ),
    ] = None,
    fps: Annotated[
        float,
        typer.Option(
            "--fps",
            min=0.001,
            help="Frames per second for each check-segment MP4.",
        ),
    ] = 6.0,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite existing MP4 files.",
        ),
    ] = False,
    jobs: Annotated[
        int,
        typer.Option(
            "--jobs",
            min=1,
            help="Number of worker processes to use across per-position review video generation.",
        ),
    ] = 1,
) -> None:
    result = run_check_segment(
        workspace=workspace,
        sample=sample,
        output=output,
        fps=fps,
        force=force,
        jobs=jobs,
        on_video_written=lambda video: typer.echo(
            format_written_check_segment_video_message(video)
        ),
    )
    if result.skipped_positions:
        typer.echo(format_skipped_positions_message(result.skipped_positions))
