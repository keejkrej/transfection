"""Typer application and dispatch for analyze subcommands."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import typer

from . import auc, fit, plot_auc, plot_fit, plot_timeseries, timeseries

HELP = "ROI timeseries metrics, AUC, kinetic fits, and summary plots."

app = typer.Typer(add_completion=False, no_args_is_help=True, help=HELP)

for _name, _mod in (
    ("timeseries", timeseries),
    ("auc", auc),
    ("fit", fit),
    ("plot-auc", plot_auc),
    ("plot-fit", plot_fit),
    ("plot-timeseries", plot_timeseries),
):
    app.command(_name, help=_mod.HELP)(_mod.cli)


def run_subcommand(
    command: Callable[..., None],
    argv: Sequence[str] | None,
    *,
    prog_name: str,
) -> None:
    runner = typer.Typer(add_completion=False, no_args_is_help=True)
    runner.command()(command)
    runner(prog_name=prog_name, args=list(argv) if argv is not None else None)
