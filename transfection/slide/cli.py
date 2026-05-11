"""Typer application for slide subcommands."""

from __future__ import annotations

from pathlib import Path

import typer
from transfection.data.slide import (
    SlideMapping,
    parse_slide_mapping_spec,
    write_slide_mapping,
)

HELP = "Write slide.json from a compact slide mapping string."

app = typer.Typer(add_completion=False, no_args_is_help=True, help=HELP)


@app.command(help=HELP)
def config(
    sample: str = typer.Option(
        ...,
        "--sample",
        help=(
            'Pipe-separated segments "positions@image_channel#sample_name" in entry order '
            '(slide_channel keys in slide.json are 0, 1, 2, …). '
            'Example: --sample "10,11@2#condA|20@1#condB". Positions use commas and slices; '
            "each segment requires #sample_name."
        ),
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        file_okay=True,
        dir_okay=False,
        help="Path for the slide.json file to write.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite the output file if it already exists.",
    ),
) -> None:
    output_path = output.expanduser().resolve()

    try:
        mapping = parse_slide_mapping_spec(sample)
    except ValueError as error:
        typer.echo(f"Invalid --sample mapping: {error}", err=True)
        raise typer.Exit(code=1) from None

    if output_path.exists() and not force:
        typer.echo(
            f"{output_path} already exists. Pass --force to overwrite.",
            err=True,
        )
        raise typer.Exit(code=1)

    written_path = write_slide_mapping(mapping, output_path)
    typer.echo(f"Wrote slide mapping: {written_path}")
    _print_mapping(mapping)


def _print_mapping(mapping: SlideMapping) -> None:
    for slide_channel in sorted(mapping):
        entry = mapping[slide_channel]
        positions = ", ".join(str(pos) for pos in entry.positions)
        typer.echo(
            f"  slide_channel={slide_channel} sample_name={entry.sample_name!r} "
            f"image_channel={entry.image_channel} positions={positions}"
        )
