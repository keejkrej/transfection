from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer

from transfection.analyze import auc as auc_command
from transfection.analyze import fit as fit_command
from transfection.analyze import plot_auc as plot_auc_command
from transfection.analyze import plot_fit as plot_fit_command
from transfection.analyze import plot_timeseries as plot_timeseries_command
from transfection.analyze import timeseries as timeseries_command
from transfection.slide import config as slide_command

HELP = "Microscopy ROI pipelines: slide mapping and timeseries metrics."

app = typer.Typer(add_completion=False, no_args_is_help=True, help=HELP)


@app.command("slide", help=slide_command.HELP)
def slide(
    sample: Annotated[
        str,
        typer.Option(
            "--sample",
            help=(
                'Pipe-separated segments "positions@image_channel#sample_name" in entry order '
                "(slide_channel keys in slide.json are 0, 1, 2, ...). "
                'Example: --sample "10,11@2#condA|20@1#condB". Positions use commas and slices; '
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


@app.command("timeseries", help=timeseries_command.HELP)
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
                "Microscopy slide mapping JSON per slide_channel: positions, image_channel, and sample_name. "
                "Process every position from every slide channel in the file and write "
                "one CSV per slide channel."
            ),
        ),
    ],
    correction_quartile: Annotated[
        float,
        typer.Option(
            "--correction-quartile",
            help="Single quartile used to compute the corrected intensity column.",
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
        correction_quartile=correction_quartile,
        jobs=jobs,
    )


@app.command("auc", help=auc_command.HELP)
def auc(
    workspace: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            metavar="WORKSPACE",
            help=f"Workspace with {auc_command.paths.TIMESERIES_DIRNAME}/ containing ROI metrics CSV files.",
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


@app.command("fit", help=fit_command.HELP)
def fit(
    workspace: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            metavar="WORKSPACE",
            help=f"Workspace with {fit_command.paths.TIMESERIES_DIRNAME}/ containing ROI metrics CSV files.",
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


@app.command("plot-timeseries", help=plot_timeseries_command.HELP)
def plot_timeseries(
    metrics_dir: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            metavar="TIMESERIES_DIR",
            help=(
                f"Directory of per-channel metrics CSVs (typically <workspace>/{plot_timeseries_command.paths.TIMESERIES_DIRNAME}). "
                f"Default PNG is written alongside AUC/fit outputs under <workspace>/{plot_timeseries_command.paths.RESULTS_DIRNAME}/."
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
                f"Primary output PNG path. Default: <workspace>/{plot_timeseries_command.paths.RESULTS_DIRNAME}/traces.png "
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


@app.command("plot-auc", help=plot_auc_command.HELP)
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


@app.command("plot-fit", help=plot_fit_command.HELP)
def plot_fit(
    fit_csv: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            metavar="FIT_CSV",
            help=(
                f"Must be <workspace>/{plot_fit_command.paths.RESULTS_DIRNAME}/fit.csv; sibling "
                f"{plot_fit_command.paths.TIMESERIES_DIRNAME}/ supplies raw traces for the fitted-trace grid."
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
    app(args=list(argv) if argv is not None else None, prog_name="transfection")
