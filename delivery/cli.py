from __future__ import annotations

from collections.abc import Sequence

import typer

from . import binding, expression, slide


HELP = "Delivery-specific ROI extraction and comparison workflows."

app = typer.Typer(add_completion=False, no_args_is_help=True, help=HELP)
app.add_typer(expression.app, name="expression")
app.add_typer(binding.app, name="binding")
app.add_typer(slide.app, name="slide")


def main(argv: Sequence[str] | None = None) -> None:
    app(args=list(argv) if argv is not None else None, prog_name="delivery")
