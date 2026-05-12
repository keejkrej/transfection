from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from transfection.analysis.roi import load_timeseries_csv
from transfection.analysis.trace_fluor import trace_color_alpha_from_fluor_name

from . import auc, paths, plot_layout
from .slide_labels import infer_workspace_for_timeseries_dir, load_slide_channel_labels

HELP = (
    f"Plot every metrics CSV in a {paths.TIMESERIES_DIRNAME}/ folder as subplots in two PNGs "
    f"(default: sibling {paths.RESULTS_DIRNAME}/traces.png and traces_shared_y.png). "
    "X axis is frame index times --interval (minutes per frame). "
    "Y limits use 1–99% percentiles of corrected intensity per panel; the second figure uses one "
    "y range (min of panel 1% values, max of panel 99% values)."
)


def run_plot_timeseries(
    timeseries_csvs: list[Path],
    *,
    interval: float,
    output: Path | None,
    results_dir: Path | None,
    columns: int,
    slide_channel_names: dict[int, str],
) -> tuple[Path, Path]:
    if interval <= 0:
        raise ValueError(f"--interval must be > 0, got {interval}")

    resolved_csvs = sorted((csv_path.resolve() for csv_path in timeseries_csvs), key=lambda path: path.name)
    resolved_output_plot = default_output_plot_path(resolved_csvs, output, results_dir=results_dir)
    resolved_shared_y_plot = unified_y_output_path(resolved_output_plot)
    panels = [(csv_path, load_timeseries_csv(csv_path)) for csv_path in resolved_csvs]
    panel_ylims = [corrected_percentile_ylim(panel_corrected_values(df)) for _, df in panels]
    unified_low = min(lo for lo, _ in panel_ylims)
    unified_high = max(hi for _, hi in panel_ylims)
    unified_low, unified_high = expand_degenerate_ylim(unified_low, unified_high)

    write_subplot_grid(
        panels,
        resolved_output_plot,
        interval=interval,
        ylim_fn=lambda i: panel_ylims[i],
        columns=columns,
        slide_channel_names=slide_channel_names,
    )
    write_subplot_grid(
        panels,
        resolved_shared_y_plot,
        interval=interval,
        ylim_fn=lambda _i: (unified_low, unified_high),
        columns=columns,
        slide_channel_names=slide_channel_names,
    )
    return resolved_output_plot, resolved_shared_y_plot


def default_output_plot_path(
    timeseries_csvs: list[Path],
    output: Path | None,
    *,
    results_dir: Path | None = None,
) -> Path:
    if output is not None:
        return output.resolve()
    if results_dir is not None:
        return (results_dir.resolve() / "traces.png").resolve()
    return timeseries_csvs[0].with_name("traces.png").resolve()


def unified_y_output_path(primary_plot: Path) -> Path:
    return primary_plot.with_name("traces_shared_y.png")


def panel_corrected_values(df: pd.DataFrame) -> np.ndarray:
    return df["corrected"].astype(float).to_numpy(dtype=float)


def corrected_percentile_ylim(values: np.ndarray) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return (0.0, 1.0)
    low, high = np.percentile(arr, [1.0, 99.0])
    low_f, high_f = float(low), float(high)
    return expand_degenerate_ylim(low_f, high_f)


def expand_degenerate_ylim(low: float, high: float) -> tuple[float, float]:
    if not math.isfinite(low) or not math.isfinite(high):
        return (0.0, 1.0)
    if low < high:
        return (low, high)
    pad = 1.0 if low == 0 else abs(low) * 0.05
    return (low - pad, high + pad)


def subplot_title(
    csv_path: Path,
    trace_count: int | None = None,
    *,
    slide_channel_names: dict[int, str] | None = None,
) -> str:
    names = slide_channel_names or {}
    sc = auc.parse_slide_channel(csv_path)
    if sc is not None and sc in names:
        label = names[sc]
    elif sc is not None:
        label = f"slide channel {sc}"
    else:
        label = csv_path.stem
    if trace_count is None:
        return label
    return f"{label} ({trace_count} traces)"


def trace_group_columns(df) -> list[str]:
    columns = ["roi"]
    if "pos" in df.columns:
        columns.insert(0, "pos")
    return columns


def trace_naming_haystack(csv_path: Path, slide_channel_names: dict[int, str]) -> str:
    """Text used to infer fluor colors (filename, stem, optional slide channel label)."""
    parts = [csv_path.name, csv_path.stem]
    sc = auc.parse_slide_channel(csv_path)
    if sc is not None and sc in slide_channel_names:
        parts.append(slide_channel_names[sc])
    return " ".join(parts)


def write_subplot_grid(
    panels: list[tuple[Path, pd.DataFrame]],
    output_plot: Path,
    *,
    interval: float,
    ylim_fn: Callable[[int], tuple[float, float]],
    columns: int,
    slide_channel_names: dict[int, str],
) -> None:
    rows = math.ceil(len(panels) / columns)
    fig, axes = plt.subplots(rows, columns, squeeze=False, figsize=plot_layout.FIGURE_SIZE_IN)
    axes_flat = axes.flatten()

    for index, (ax, (csv_path, df)) in enumerate(zip(axes_flat, panels)):
        trace_color, trace_alpha = trace_color_alpha_from_fluor_name(
            trace_naming_haystack(csv_path, slide_channel_names)
        )
        trace_groups = df.groupby(trace_group_columns(df), sort=True, dropna=False)
        for _, roi_df in trace_groups:
            t_minutes = roi_df["t"].astype(float).to_numpy(dtype=float) * interval
            ax.plot(t_minutes, roi_df["corrected"], color=trace_color, alpha=trace_alpha)
        ax.set_title(subplot_title(csv_path, trace_groups.ngroups, slide_channel_names=slide_channel_names))
        ax.set_xlabel("minutes")
        ax.set_ylabel("corrected intensity")
        y_low, y_high = ylim_fn(index)
        ax.set_ylim(y_low, y_high)

    for ax in axes_flat[len(panels):]:
        ax.axis("off")

    fig.tight_layout()

    output_plot.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_plot, dpi=plot_layout.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)


def format_written_timeseries_plot_message(output_plot: Path) -> str:
    return f"Wrote plot: {output_plot}"


def run_command(
    metrics_dir: Path,
    *,
    output: Path | None = None,
    columns: int = 3,
    interval: float,
) -> None:
    timeseries_csvs = paths.discover_timeseries_csvs(metrics_dir)
    results_dir = paths.workspace_results_dir(metrics_dir.parent)
    workspace = infer_workspace_for_timeseries_dir(metrics_dir)
    slide_channel_names = load_slide_channel_labels(workspace)
    resolved_output_plot, resolved_shared_y_plot = run_plot_timeseries(
        timeseries_csvs,
        interval=interval,
        output=output,
        results_dir=None if output is not None else results_dir,
        columns=columns,
        slide_channel_names=slide_channel_names,
    )
    print(format_written_timeseries_plot_message(resolved_output_plot))
    print(format_written_timeseries_plot_message(resolved_shared_y_plot))
