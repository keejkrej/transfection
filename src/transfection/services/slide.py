from __future__ import annotations

from pathlib import Path

from transfection.core import (
    SlideMapping,
    parse_slide_mapping_spec,
    write_slide_mapping,
)


class SlideOutputExistsError(FileExistsError):
    pass


def format_mapping_lines(mapping: SlideMapping) -> list[str]:
    lines: list[str] = []
    for slide_channel in sorted(mapping):
        entry = mapping[slide_channel]
        positions = ", ".join(str(pos) for pos in entry.positions)
        lines.append(
            f"  slide_channel={slide_channel} sample_name={entry.sample_name!r} "
            f"signal_channel={entry.signal_channel} mask_channel={entry.mask_channel} positions={positions}"
        )
    return lines


def run_slide(*, sample: str, output: Path, force: bool = False) -> tuple[Path, SlideMapping]:
    output_path = output.expanduser().resolve()
    mapping = parse_slide_mapping_spec(sample)
    if output_path.exists() and not force:
        raise SlideOutputExistsError(output_path)
    written_path = write_slide_mapping(mapping, output_path)
    return written_path, mapping
