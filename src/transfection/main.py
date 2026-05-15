from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer

from transfection import core
from transfection.commands import check_segment as check_segment_command
from transfection.commands import auc as auc_command
from transfection.commands import fit as fit_command
from transfection.commands import plot_auc as plot_auc_command
from transfection.commands import plot_fit as plot_fit_command
from transfection.commands import plot_timeseries as plot_timeseries_command
from transfection.commands import segment as segment_command
from transfection.commands import slide as slide_command
from transfection.commands import timeseries as timeseries_command

app = typer.Typer(add_completion=False, no_args_is_help=True, help=core.HELP)


@app.command(slide_command.NAME, help=slide_command.HELP)
def slide(
    sample: Annotated[
        str,
        typer.Option(
            "--sample",
            help=(
                'Pipe-separated segments "positions@signal_channel/mask_channel#sample_name" in entry order '
                "(slide_channel keys in slide.json are 0, 1, 2, ...). "
                "Use signal_channel for intensity and mask_channel for segmentation. "
                'Example: --sample "10,11@2/0#condA|20@1/0#condB". Positions use commas and slices; '
                "each segment requires #sample_name."
            ),
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            file_okay=True,
            dir_okay=False,
            help="Path for the slide.json file to write.",
        ),
    ],
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite the output file if it already exists.",
        ),
    ] = False,
) -> None:
    slide_command.run_command(sample=sample, output=output, force=force)


@app.command(check_segment_command.NAME, help=check_segment_command.HELP)
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
    check_segment_command.run_command(
        workspace=workspace,
        sample=sample,
        output=output,
        fps=fps,
        force=force,
    )


@app.command(segment_command.NAME, help=segment_command.HELP)
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
    segment_command.run_command(
        workspace=workspace,
        sample=sample,
        variation_radius=variation_radius,
        gaussian_sigma=gaussian_sigma,
        force=force,
        jobs=jobs,
    )


@app.command(timeseries_command.NAME, help=timeseries_command.HELP)
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
    ] = timeseries_command.DELIVERY_CORRECTION_QUARTILE,
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
    timeseries_command.run_command(
        workspace=workspace,
        sample=sample,
        mask_channel=mask_channel,
        correction_quartile=correction_quartile,
        jobs=jobs,
    )


@app.command(auc_command.NAME, help=auc_command.HELP)
def auc(
    workspace: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            metavar="WORKSPACE",
            help=f"Workspace with {core.TIMESERIES_DIRNAME}/ containing ROI metrics CSV files.",
        ),
    ],
    interval: Annotated[
        float,
        typer.Option(
            "--interval",
            min=0.0,
            help="Frame interval in minutes used to convert t into time before integration.",
        ),
    ],
) -> None:
    auc_command.run_command(workspace=workspace, interval=interval)


@app.command(fit_command.NAME, help=fit_command.HELP)
def fit(
    workspace: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            metavar="WORKSPACE",
            help=f"Workspace with {core.TIMESERIES_DIRNAME}/ containing ROI metrics CSV files.",
        ),
    ],
    interval: Annotated[
        float,
        typer.Option(
            "--interval",
            min=0.0,
            help=(
                "Frame interval in minutes used to convert t into time for fitting "
                "y=intensity_offset + expression_amplitude * "
                "(exp(-protein_decay_rate*t) - exp(-mrna_decay_rate*t))."
            ),
        ),
    ],
    max_onset_minutes: Annotated[
        float,
        typer.Option(
            "--max-onset-minutes",
            min=0.0,
            help=(
                "Cap on second-pass candidate translation_onset values in minutes. "
                "0 keeps translation_onset fixed at 0."
            ),
        ),
    ] = 0.0,
    jobs: Annotated[
        int,
        typer.Option(
            "--jobs",
            min=1,
            help=(
                "Number of worker processes to use across independent trace fits. "
                "Use transfection-analyze.ps1 for a CPU-based default."
            ),
        ),
    ] = 1,
) -> None:
    fit_command.run_command(
        workspace=workspace,
        interval=interval,
        max_onset_minutes=max_onset_minutes,
        jobs=jobs,
    )


@app.command(plot_timeseries_command.NAME, help=plot_timeseries_command.HELP)
def plot_timeseries(
    metrics_dir: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            metavar="TIMESERIES_DIR",
            help=(
                f"Directory of per-channel metrics CSVs (typically <workspace>/{core.TIMESERIES_DIRNAME}). "
                f"Default PNG is written alongside AUC/fit outputs under <workspace>/{core.RESULTS_DIRNAME}/."
            ),
        ),
    ],
    interval: Annotated[
        float,
        typer.Option(
            "--interval",
            min=0.0,
            help="Minutes per frame index in metrics CSVs; x axis is t * interval (same as auc/fit).",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help=(
                f"Primary output PNG path. Default: <workspace>/{core.RESULTS_DIRNAME}/traces.png "
                "with a companion traces_shared_y.png for unified y limits."
            ),
        ),
    ] = None,
    columns: Annotated[
        int,
        typer.Option(
            "--columns",
            min=1,
            help="Number of subplot columns in the output grid.",
        ),
    ] = 3,
) -> None:
    plot_timeseries_command.run_command(
        metrics_dir=metrics_dir,
        output=output,
        columns=columns,
        interval=interval,
    )


@app.command(plot_auc_command.NAME, help=plot_auc_command.HELP)
def plot_auc(
    auc_csv: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            metavar="AUC_CSV",
            help="AUC summary CSV generated by transfection auc.",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output PNG path. Default: auc.png in the same directory as the AUC CSV.",
        ),
    ] = None,
) -> None:
    plot_auc_command.run_command(auc_csv=auc_csv, output=output)


@app.command(plot_fit_command.NAME, help=plot_fit_command.HELP)
def plot_fit(
    fit_csv: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            metavar="FIT_CSV",
            help=(
                f"Must be <workspace>/{core.RESULTS_DIRNAME}/fit.csv; sibling "
                f"{core.TIMESERIES_DIRNAME}/ supplies raw traces for the fitted-trace grid."
            ),
        ),
    ],
    interval: Annotated[
        float,
        typer.Option(
            "--interval",
            min=0.0,
            help="Frame interval in minutes used to reconstruct fitted traces against the sibling timeseries CSVs.",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            file_okay=False,
            dir_okay=True,
            help="Directory for output PNGs. Default: same directory as the fit CSV.",
        ),
    ] = None,
    columns: Annotated[
        int,
        typer.Option(
            "--columns",
            min=1,
            help="Number of subplot columns in the fitted-trace grid.",
        ),
    ] = 3,
) -> None:
    plot_fit_command.run_command(
        fit_csv=fit_csv,
        output=output,
        interval=interval,
        columns=columns,
    )


def main(argv: Sequence[str] | None = None) -> None:
    app(args=core.normalize_argv(argv), prog_name=core.PROG_NAME)
