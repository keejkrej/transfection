from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from transfection import core as paths
from transfection.app import app
from transfection.services.fit import format_written_fit_csv_message, run_fit

NAME = "fit"
HELP = (
    "Fit every metrics CSV in <workspace>/timeseries/ to y=intensity_offset + "
    "expression_amplitude * (exp(-protein_decay_rate*t) - exp(-mrna_decay_rate*t)), "
    f"where t is minutes from t * --interval. translation_onset is fixed at 0 unless "
    f"--max-onset-minutes enables second-pass onset search. "
    f"Writes <workspace>/{paths.RESULTS_DIRNAME}/fit.csv."
)


@app.command(NAME, help=HELP)
def fit(
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
    resolved_output_csv = run_fit(
        workspace=workspace,
        interval=interval,
        max_onset_minutes=max_onset_minutes,
        jobs=jobs,
    )
    typer.echo(format_written_fit_csv_message(resolved_output_csv))
