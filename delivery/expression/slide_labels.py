from __future__ import annotations

from pathlib import Path

from lisca.data.slide import load_slide_mapping

from . import paths


def infer_workspace_for_plot_csv(csv_file: Path) -> Path:
    parent = csv_file.parent.resolve()
    if parent.name == paths.RESULTS_DIRNAME:
        return parent.parent
    return parent


def infer_workspace_for_timeseries_dir(timeseries_dir: Path) -> Path:
    return timeseries_dir.parent.resolve()


def load_slide_channel_labels(workspace: Path) -> dict[int, str]:
    slide_path = workspace / "slide.json"
    if not slide_path.is_file():
        return {}
    mapping = load_slide_mapping(slide_path)
    return {slide_channel: entry.sample_name for slide_channel, entry in mapping.items()}


def boxplot_tick_labels(slide_channels: list[int], trace_counts: list[int], slide_labels: dict[int, str]) -> list[str]:
    return [
        f"{slide_labels.get(sc, str(sc))}\n(n={n})"
        for sc, n in zip(slide_channels, trace_counts, strict=True)
    ]


def boxplot_x_axis_label(slide_labels: dict[int, str]) -> str:
    return "condition" if slide_labels else "slide channel"
