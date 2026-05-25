from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from transfection import core as paths
from transfection.app import app
from transfection.services.auc import format_written_auc_csv_message, run_auc

NAME = "auc"
HELP = (
    "Integrate every metrics CSV in <workspace>/timeseries/ and write "
    f"<workspace>/{paths.RESULTS_DIRNAME}/auc.csv."
)


@app.command(NAME, help=HELP)
def auc(
    workspace: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            metavar="WORKSPACE",
            help=f"Workspace with {paths.TIMESERIES_DIRNAME}/ containing ROI metrics CSV files.",
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
    resolved_output_csv = run_auc(workspace=workspace, interval=interval)
    typer.echo(format_written_auc_csv_message(resolved_output_csv))
