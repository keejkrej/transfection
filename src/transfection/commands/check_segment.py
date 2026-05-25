from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from transfection.app import app
from transfection.services.check_segment import run_check_segment

NAME = "check-segment"
HELP = (
    "Overlay mask contours on the ROI TIFF signal and mask channels and write MP4 review videos "
    "under <workspace>/check-segment/PosN/."
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
            help="Workspace containing roi/PosN/index.json, Roi*.tif files, masks, and slide.json.",
        ),
    ],
    sample: Annotated[
        Path,
        typer.Option(
            "--sample",
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="Slide mapping JSON with signal_channel and mask_channel per slide channel.",
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
) -> None:
    videos = run_check_segment(
        workspace,
        sample=sample,
        output=output,
        fps=fps,
        force=force,
    )
    for video in videos:
        typer.echo(f"Wrote check video ({video.frame_count} frames): {video.output_path}")
