from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from transfection import core as paths
from transfection.app import app
from transfection.services.plot_fit import format_written_fit_plot_messages, run_plot_fit

NAME = "plot-fit"
HELP = (
    "Plot fit summaries as one box plot per slide channel for each semantic fit parameter, "
    "and render fitted trace grids from the sibling timeseries CSVs."
)


@app.command(NAME, help=HELP)
def plot_fit(
    fit_csv: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            metavar="FIT_CSV",
            help=(
                f"Must be <workspace>/{paths.RESULTS_DIRNAME}/fit.csv; sibling "
                f"{paths.TIMESERIES_DIRNAME}/ supplies raw traces for the fitted-trace grid."
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
    output_plots = run_plot_fit(
        fit_csv,
        output=output,
        interval=interval,
        columns=columns,
    )
    for message in format_written_fit_plot_messages(output_plots):
        typer.echo(message)
