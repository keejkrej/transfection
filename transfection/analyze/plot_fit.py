from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import typer

from transfection.analysis.roi import load_timeseries_csv

from . import auc, plot_auc, plot_timeseries, paths
from .slide_labels import (
    boxplot_tick_labels,
    boxplot_x_axis_label,
    infer_workspace_for_plot_csv,
    load_slide_channel_labels,
)

PLOTTED_PARAMETERS = (
    ("intensity_offset", "intensity offset"),
    ("protein_lifetime", "protein lifetime"),
    ("mrna_lifetime", "mRNA lifetime"),
    ("expression_onset", "expression onset"),
    ("expression_slope", "expression slope"),
)
FIT_TRACE_PARAMETERS = (
    "intensity_offset",
    "protein_decay_rate",
    "mrna_decay_rate",
    "expression_onset",
    "expression_amplitude",
)

HELP = (
    "Plot fit summaries as one box plot per slide channel for each semantic fit parameter, "
    "and render fitted trace grids from the sibling timeseries CSVs."
)

def run_plot_fit(
    fit_csv: Path,
    *,
    output: Path | None,
    color: str,
    interval: float,
    columns: int,
    alpha: float,
    linewidth: float,
) -> list[Path]:
    resolved_fit_csv = fit_csv.resolve()
    df = load_fit_csv(resolved_fit_csv)
    output_paths = default_output_plot_paths(resolved_fit_csv, output)
    slide_channel_names = load_slide_channel_labels(infer_workspace_for_plot_csv(fit_csv))
    axis_scope = boxplot_x_axis_label(slide_channel_names)
    written_paths: list[Path] = []
    for parameter, label in PLOTTED_PARAMETERS:
        write_fit_boxplot(
            df,
            parameter=parameter,
            ylabel=label,
            output_plot=output_paths[parameter],
            color=color,
            title=f"{label} by {axis_scope}",
            slide_channel_names=slide_channel_names,
        )
        written_paths.append(output_paths[parameter])
    resolved_timeseries_csvs = infer_timeseries_csvs(resolved_fit_csv)
    fit_trace_plot = default_trace_plot_path(resolved_fit_csv, output)
    write_fitted_trace_grid(
        df,
        resolved_timeseries_csvs,
        fit_trace_plot,
        interval=interval,
        columns=columns,
        alpha=alpha,
        linewidth=linewidth,
        color=color,
        slide_channel_names=slide_channel_names,
    )
    written_paths.append(fit_trace_plot)
    return written_paths


def load_fit_csv(fit_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(fit_csv)
    required = {"slide_channel", "pos", "roi", "success", *FIT_TRACE_PARAMETERS}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"{fit_csv} is missing required columns for fit plotting: {sorted(missing)}")

    keep_columns = ["slide_channel", "pos", "roi", "success", *FIT_TRACE_PARAMETERS]
    df = df.loc[:, keep_columns].copy()
    df = df.dropna(subset=["slide_channel"])
    if df.empty:
        raise ValueError(f"{fit_csv} has no fit rows with slide_channel values")

    df["slide_channel"] = df["slide_channel"].astype(int)
    df["pos"] = pd.to_numeric(df["pos"], errors="coerce").astype("Int64")
    df["roi"] = pd.to_numeric(df["roi"], errors="coerce").astype("Int64")
    df["success"] = df["success"].astype(str).str.lower().eq("true")
    for parameter in FIT_TRACE_PARAMETERS:
        df[parameter] = pd.to_numeric(df[parameter], errors="coerce")
    if "protein_lifetime" not in df.columns:
        df["protein_lifetime"] = 1.0 / df["protein_decay_rate"]
    if "mrna_lifetime" not in df.columns:
        df["mrna_lifetime"] = 1.0 / df["mrna_decay_rate"]
    df["expression_slope"] = df["expression_amplitude"] * (df["mrna_decay_rate"] - df["protein_decay_rate"])
    return df.sort_values(["slide_channel", "pos", "roi"]).reset_index(drop=True)


def fit_bundle_plot_prefix(fit_csv: Path) -> str:
    raw = fit_csv.stem.removesuffix("_fit")
    if raw == "fit" or auc.is_compact_channel_bundle_stem(raw) or raw == "timeseries":
        return ""
    return raw


def default_output_plot_paths(fit_csv: Path, output: Path | None) -> dict[str, Path]:
    destination_dir = fit_csv.parent if output is None else output.resolve()
    prefix = fit_bundle_plot_prefix(fit_csv)
    return {
        parameter: destination_dir / (f"{prefix}_{parameter}.png" if prefix else f"{parameter}.png")
        for parameter, _ in PLOTTED_PARAMETERS
    }


def default_trace_plot_path(fit_csv: Path, output: Path | None) -> Path:
    destination_dir = fit_csv.parent if output is None else output.resolve()
    prefix = fit_bundle_plot_prefix(fit_csv)
    name = f"{prefix}_traces.png" if prefix else "traces.png"
    return destination_dir / name


def infer_timeseries_csvs(fit_csv: Path) -> list[Path]:
    search_dirs: list[Path] = []
    parent = fit_csv.parent.resolve()
    if parent.name == paths.RESULTS_DIRNAME:
        workspace = parent.parent
        candidate = workspace / paths.TIMESERIES_DIRNAME
        if candidate.is_dir():
            search_dirs.append(candidate)
    search_dirs.append(parent)

    fit_stem = fit_csv.stem.removesuffix("_fit")

    if fit_csv.name == "fit.csv" or fit_stem == "timeseries":
        matches: list[Path] = []
        seen: set[Path] = set()
        for directory in search_dirs:
            if directory.name != paths.TIMESERIES_DIRNAME:
                continue
            if not directory.is_dir():
                continue
            for candidate in sorted(directory.glob("*.csv"), key=lambda path: path.name):
                if paths.is_workspace_metrics_timeseries_csv(candidate):
                    resolved = candidate.resolve()
                    if resolved not in seen:
                        seen.add(resolved)
                        matches.append(resolved)
        matches.sort(key=lambda path: path.name)
        if not matches:
            raise ValueError(f"Could not infer timeseries CSVs for {fit_csv}")
        return matches

    matches: list[Path] = []
    seen: set[Path] = set()
    for directory in search_dirs:
        if not directory.is_dir():
            continue
        for candidate in sorted(directory.glob("*.csv"), key=lambda path: path.name):
            if fit_stem not in auc.aggregate_output_stem_candidates(candidate):
                continue
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                matches.append(resolved)
    matches.sort(key=lambda path: path.name)
    if not matches:
        raise ValueError(f"Could not infer timeseries CSVs for {fit_csv}")
    return matches


def write_fit_boxplot(
    df: pd.DataFrame,
    *,
    parameter: str,
    ylabel: str,
    output_plot: Path,
    color: str,
    title: str | None,
    slide_channel_names: dict[int, str],
) -> None:
    parameter_df = df.dropna(subset=[parameter]).copy()
    use_log_scale = parameter == "expression_slope"
    if use_log_scale:
        parameter_df = parameter_df.loc[parameter_df[parameter] > 0].copy()
    if parameter_df.empty:
        raise ValueError(f"No finite rows available to plot parameter {parameter!r}")

    slide_channels = sorted(parameter_df["slide_channel"].unique().tolist())
    trace_counts = [
        int(parameter_df.loc[parameter_df["slide_channel"] == slide_channel, parameter].shape[0])
        for slide_channel in slide_channels
    ]
    grouped_values = [
        parameter_df.loc[parameter_df["slide_channel"] == slide_channel, parameter].to_numpy(dtype=float)
        for slide_channel in slide_channels
    ]
    if not use_log_scale:
        upper_limit = plot_auc.quartile_axis_upper(grouped_values)

    fig, ax = plt.subplots(figsize=(10, 6))
    boxplot = ax.boxplot(
        grouped_values,
        patch_artist=True,
        showfliers=False,
        tick_labels=boxplot_tick_labels(slide_channels, trace_counts, slide_channel_names),
        medianprops={"color": "black", "linewidth": 1.2},
    )
    for patch in boxplot["boxes"]:
        patch.set_facecolor(color)
        patch.set_alpha(0.65)

    ax.set_xlabel(boxplot_x_axis_label(slide_channel_names))
    ax.set_ylabel(ylabel)
    if use_log_scale:
        ax.set_yscale("log")
    else:
        ax.set_ylim(0.0, upper_limit)
    ax.grid(axis="y", alpha=0.2, linewidth=0.5)
    if title is not None:
        ax.set_title(title)

    output_plot.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_plot, dpi=150, bbox_inches="tight")
    plt.close(fig)


def fitted_trace_values(times_minutes: np.ndarray, fit_row: pd.Series) -> np.ndarray:
    intensity_offset = float(fit_row["intensity_offset"])
    protein_decay_rate = float(fit_row["protein_decay_rate"])
    mrna_decay_rate = float(fit_row["mrna_decay_rate"])
    expression_onset = float(fit_row["expression_onset"])
    expression_amplitude = float(fit_row["expression_amplitude"])
    dt = np.maximum(times_minutes - expression_onset, 0.0)
    predicted = intensity_offset + expression_amplitude * (
        np.exp(-protein_decay_rate * dt) - np.exp(-mrna_decay_rate * dt)
    )
    predicted[times_minutes < expression_onset] = intensity_offset
    return predicted


def write_fitted_trace_grid(
    fit_df: pd.DataFrame,
    timeseries_csvs: list[Path],
    output_plot: Path,
    *,
    interval: float,
    columns: int,
    alpha: float,
    linewidth: float,
    color: str,
    slide_channel_names: dict[int, str],
) -> None:
    rows = math.ceil(len(timeseries_csvs) / columns)
    fig, axes = plt.subplots(rows, columns, figsize=(6.0 * columns, 4.8 * rows), squeeze=False)
    axes_flat = axes.flatten()
    fit_lookup = (
        fit_df.loc[fit_df["success"]]
        .set_index(["slide_channel", "pos", "roi"], drop=False)
        .sort_index()
    )
    plotted_trace_count = 0

    for ax, csv_path in zip(axes_flat, timeseries_csvs):
        df = load_timeseries_csv(csv_path)
        slide_channel = auc.parse_slide_channel(csv_path)
        matched_traces = 0
        trace_groups = df.groupby(plot_timeseries.trace_group_columns(df), sort=True, dropna=False)
        for group_key, trace_df in trace_groups:
            if not isinstance(group_key, tuple):
                group_key = (group_key,)
            group_values = dict(zip(plot_timeseries.trace_group_columns(df), group_key, strict=True))
            pos = int(group_values.get("pos", 0))
            roi = int(group_values["roi"])
            lookup_key = (slide_channel, pos, roi)
            if lookup_key not in fit_lookup.index:
                continue

            fit_row = fit_lookup.loc[lookup_key]
            times_minutes = trace_df["t"].astype(float).to_numpy(dtype=float) * interval
            predicted = fitted_trace_values(times_minutes, fit_row)
            ax.plot(
                times_minutes,
                predicted,
                color=color,
                alpha=alpha,
                linewidth=linewidth,
            )
            matched_traces += 1
            plotted_trace_count += 1

        ax.set_title(
            plot_timeseries.subplot_title(csv_path, matched_traces, slide_channel_names=slide_channel_names)
        )
        ax.set_xlabel("minutes")
        ax.set_ylabel("corrected intensity")

    for ax in axes_flat[len(timeseries_csvs):]:
        ax.axis("off")

    if plotted_trace_count == 0:
        plt.close(fig)
        raise ValueError("No successful fit rows matched the inferred timeseries CSVs")

    fig.suptitle("Fitted traces by slide channel")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.97))
    output_plot.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_plot, dpi=150, bbox_inches="tight")
    plt.close(fig)


def format_written_fit_plot_messages(output_plots: list[Path]) -> list[str]:
    return [f"Wrote plot: {output_plot}" for output_plot in output_plots]


def cli(
    fit_csv: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        metavar="FIT_CSV",
        help="Fit summary CSV generated by transfection analyze fit.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        file_okay=False,
        dir_okay=True,
        help="Directory for output PNGs. Default: same directory as the fit CSV.",
    ),
    interval: float = typer.Option(
        ...,
        "--interval",
        min=0.0,
        help="Frame interval in minutes used to reconstruct fitted traces against the sibling timeseries CSVs.",
    ),
    color: str = typer.Option(
        "#c03a2b",
        "--color",
        help="Matplotlib color for fitted curves and box fills.",
    ),
    columns: int = typer.Option(
        3,
        "--columns",
        min=1,
        help="Number of subplot columns in the fitted-trace grid.",
    ),
    alpha: float = typer.Option(
        0.12,
        "--alpha",
        min=0.0,
        max=1.0,
        help="Per-trace opacity for fitted traces in the fitted-trace grid.",
    ),
    linewidth: float = typer.Option(
        1.0,
        "--linewidth",
        min=0.1,
        help="Per-trace line width for fitted traces in the fitted-trace grid.",
    ),
) -> None:
    output_plots = run_plot_fit(
        fit_csv,
        output=output,
        color=color,
        interval=interval,
        columns=columns,
        alpha=alpha,
        linewidth=linewidth,
    )
    for message in format_written_fit_plot_messages(output_plots):
        print(message)


def main(argv: list[str] | None = None, *, prog_name: str = "transfection analyze plot-fit") -> None:
    from transfection.analyze.cli import run_subcommand

    run_subcommand(cli, argv, prog_name=prog_name)


if __name__ == "__main__":
    main()
