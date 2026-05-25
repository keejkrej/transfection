from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from transfection import core as paths
from transfection.app import app
from transfection.services.plot_timeseries import (
    format_written_timeseries_plot_message,
    run_plot_timeseries,
)

NAME = "plot-timeseries"
HELP = (
    f"Plot every metrics CSV in a {paths.TIMESERIES_DIRNAME}/ folder as subplots in PNGs "
    f"(default: sibling {paths.RESULTS_DIRNAME}/traces.png, traces_shared_y.png, "
    "area.png, and area_shared_y.png). "
    "X axis is frame index times --interval (minutes per frame). "
    "Y limits use 1–99% percentiles per panel; each shared-y figure uses one "
    "y range (min of panel 1% values, max of panel 99% values)."
)


@app.command(NAME, help=HELP)
def plot_timeseries(
    metrics_dir: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            metavar="TIMESERIES_DIR",
            help=(
                f"Directory of per-channel metrics CSVs (typically <workspace>/{paths.TIMESERIES_DIRNAME}). "
                f"Default PNG is written alongside AUC/fit outputs under <workspace>/{paths.RESULTS_DIRNAME}/."
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
                f"Primary output PNG path. Default: <workspace>/{paths.RESULTS_DIRNAME}/traces.png "
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
    written_plots = run_plot_timeseries(
        metrics_dir=metrics_dir,
        interval=interval,
        output=output,
        columns=columns,
    )
    for output_plot in written_plots:
        typer.echo(format_written_timeseries_plot_message(output_plot))
