"""Expression analysis commands."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import typer

from . import auc, fit, plot_auc, plot_fit, plot_timeseries, timeseries


HELP = "ROI timeseries metrics, AUC, kinetic fits, and summary plots."

app = typer.Typer(add_completion=False, no_args_is_help=True, help=HELP)

app.command("timeseries", help=timeseries.HELP)(timeseries.cli)
app.command("auc", help=auc.HELP)(auc.cli)
app.command("fit", help=fit.HELP)(fit.cli)
app.command("plot-auc", help=plot_auc.HELP)(plot_auc.cli)
app.command("plot-fit", help=plot_fit.HELP)(plot_fit.cli)
app.command("plot-timeseries", help=plot_timeseries.HELP)(plot_timeseries.cli)


def run_subcommand(
    command: Callable[..., None],
    argv: Sequence[str] | None,
    *,
    prog_name: str,
) -> None:
    runner = typer.Typer(add_completion=False, no_args_is_help=True)
    runner.command()(command)
    runner(prog_name=prog_name, args=list(argv) if argv is not None else None)
