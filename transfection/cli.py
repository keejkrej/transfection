from __future__ import annotations

from collections.abc import Sequence

import typer

from transfection.analyze.cli import app as analyze_cli
from transfection.slide.cli import app as slide_cli

HELP = "Microscopy ROI pipelines: slide mapping and timeseries metrics."

app = typer.Typer(add_completion=False, no_args_is_help=True, help=HELP)
app.add_typer(slide_cli, name="slide")
app.add_typer(analyze_cli, name="analyze")


def main(argv: Sequence[str] | None = None) -> None:
    app(args=list(argv) if argv is not None else None, prog_name="transfection")
