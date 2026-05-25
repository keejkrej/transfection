from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from transfection.app import app
from transfection.services.segment import (
    format_skipped_positions_message,
    format_written_masks_message,
    run_segment,
)

NAME = "segment"
HELP = (
    "Segment each mapped ROI channel with variation filter -> Gaussian filter -> Otsu, "
    "and write per-frame mask TIFFs under <workspace>/mask/PosN/."
)


@app.command(NAME, help=HELP)
def segment(
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
                "Masks are written for every mapped position and ROI."
            ),
        ),
    ],
    variation_radius: Annotated[
        int,
        typer.Option(
            "--variation-radius",
            min=0,
            help="Radius in pixels for the local variation filter before Gaussian smoothing.",
        ),
    ] = 2,
    gaussian_sigma: Annotated[
        float,
        typer.Option(
            "--gaussian-sigma",
            min=0.0,
            help="Sigma in pixels for Gaussian smoothing after local variation filtering.",
        ),
    ] = 1.0,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite existing mask TIFF files.",
        ),
    ] = False,
    jobs: Annotated[
        int,
        typer.Option(
            "--jobs",
            min=1,
            help="Number of worker processes to use across per-position segmentations.",
        ),
    ] = 1,
) -> None:
    result = run_segment(
        workspace,
        sample=sample,
        variation_radius=variation_radius,
        gaussian_sigma=gaussian_sigma,
        force=force,
        on_mask_written=lambda slide_channel, output_dir, mask_count: typer.echo(
            format_written_masks_message(slide_channel, output_dir, mask_count)
        ),
        jobs=jobs,
    )
    if result.skipped_positions:
        typer.echo(format_skipped_positions_message(result.skipped_positions))
