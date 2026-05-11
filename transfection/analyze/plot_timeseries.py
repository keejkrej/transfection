from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import typer

from transfection.analysis.roi import load_timeseries_csv

from . import auc, paths
from .slide_labels import infer_workspace_for_timeseries_dir, load_slide_channel_labels

HELP = (
    f"Plot every metrics CSV in a {paths.TIMESERIES_DIRNAME}/ folder as subplots in two PNGs "
    f"(default: sibling {paths.RESULTS_DIRNAME}/overview.png and overview_shared_y.png). "
    "Y limits use 1–99% percentiles of corrected intensity per panel; the second figure uses one "
    "y range (min of panel 1% values, max of panel 99% values)."
)


def run_plot_timeseries(
    timeseries_csvs: list[Path],
    *,
    output: Path | None,
    results_dir: Path | None,
    columns: int,
    alpha: float,
    linewidth: float,
    color: str,
    title: str | None,
    slide_channel_names: dict[int, str],
) -> tuple[Path, Path]:
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
        ylim_fn=lambda i: panel_ylims[i],
        alpha=alpha,
        linewidth=linewidth,
        color=color,
        title=title,
        columns=columns,
        slide_channel_names=slide_channel_names,
    )
    write_subplot_grid(
        panels,
        resolved_shared_y_plot,
        ylim_fn=lambda _i: (unified_low, unified_high),
        alpha=alpha,
        linewidth=linewidth,
        color=color,
        title=title,
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
    stem = auc.aggregate_output_stem(timeseries_csvs)
    base = auc.results_plot_grid_basename(stem)
    if results_dir is not None:
        return (results_dir.resolve() / f"{base}.png").resolve()
    return timeseries_csvs[0].with_name(f"{base}.png").resolve()


def unified_y_output_path(primary_plot: Path) -> Path:
    return primary_plot.with_name(f"{primary_plot.stem}_shared_y{primary_plot.suffix}")


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


def write_subplot_grid(
    panels: list[tuple[Path, pd.DataFrame]],
    output_plot: Path,
    *,
    ylim_fn: Callable[[int], tuple[float, float]],
    alpha: float,
    linewidth: float,
    color: str,
    title: str | None,
    columns: int,
    slide_channel_names: dict[int, str],
) -> None:
    rows = math.ceil(len(panels) / columns)
    fig, axes = plt.subplots(rows, columns, figsize=(6.0 * columns, 4.8 * rows), squeeze=False)
    axes_flat = axes.flatten()

    for index, (ax, (csv_path, df)) in enumerate(zip(axes_flat, panels)):
        trace_groups = df.groupby(trace_group_columns(df), sort=True, dropna=False)
        for _, roi_df in trace_groups:
            ax.plot(
                roi_df["t"],
                roi_df["corrected"],
                color=color,
                alpha=alpha,
                linewidth=linewidth,
            )
        ax.set_title(subplot_title(csv_path, trace_groups.ngroups, slide_channel_names=slide_channel_names))
        ax.set_xlabel("frame")
        ax.set_ylabel("corrected intensity")
        y_low, y_high = ylim_fn(index)
        ax.set_ylim(y_low, y_high)

    for ax in axes_flat[len(panels):]:
        ax.axis("off")

    if title is not None:
        fig.suptitle(title)
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.97))
    else:
        fig.tight_layout()

    output_plot.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_plot, dpi=150, bbox_inches="tight")
    plt.close(fig)


def format_written_timeseries_plot_message(output_plot: Path) -> str:
    return f"Wrote plot: {output_plot}"


def cli(
    metrics_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        metavar="TIMESERIES_DIR",
        help=(
            f"Directory of per-channel metrics CSVs (typically <workspace>/{paths.TIMESERIES_DIRNAME}). "
            f"Default PNG is written alongside AUC/fit outputs under <workspace>/{paths.RESULTS_DIRNAME}/."
        ),
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help=(
            f"Primary output PNG path. Default: <workspace>/{paths.RESULTS_DIRNAME}/overview.png "
            "with a companion overview_shared_y.png for unified y limits."
        ),
    ),
    columns: int = typer.Option(
        3,
        "--columns",
        min=1,
        help="Number of subplot columns in the output grid.",
    ),
    alpha: float = typer.Option(
        0.12,
        "--alpha",
        min=0.0,
        max=1.0,
        help="Per-trace opacity.",
    ),
    linewidth: float = typer.Option(
        1.0,
        "--linewidth",
        min=0.1,
        help="Per-trace line width.",
    ),
    color: str = typer.Option(
        "#c03a2b",
        "--color",
        help="Matplotlib color for all traces.",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        help="Optional figure title.",
    ),
) -> None:
    timeseries_csvs = paths.discover_timeseries_csvs(metrics_dir)
    results_dir = paths.workspace_results_dir(metrics_dir.parent)
    workspace = infer_workspace_for_timeseries_dir(metrics_dir)
    slide_channel_names = load_slide_channel_labels(workspace)
    resolved_output_plot, resolved_shared_y_plot = run_plot_timeseries(
        timeseries_csvs,
        output=output,
        results_dir=None if output is not None else results_dir,
        columns=columns,
        alpha=alpha,
        linewidth=linewidth,
        color=color,
        title=title,
        slide_channel_names=slide_channel_names,
    )
    print(format_written_timeseries_plot_message(resolved_output_plot))
    print(format_written_timeseries_plot_message(resolved_shared_y_plot))


def main(argv: list[str] | None = None, *, prog_name: str = "transfection analyze plot-timeseries") -> None:
    from transfection.analyze.cli import run_subcommand

    run_subcommand(cli, argv, prog_name=prog_name)


if __name__ == "__main__":
    main()
