import marimo

__generated_with = "0.23.9"
app = marimo.App()


@app.cell
def _():
    import math
    from pathlib import Path

    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    from transfection.core import (
        boxplot_tick_labels,
        boxplot_x_axis_label,
        discover_timeseries_csvs,
        load_slide_channel_labels,
        load_timeseries_csv,
        trace_color_alpha_from_fluor_name,
    )
    from transfection.core.constants import FIGURE_SIZE_IN
    from transfection.services import auc, plot_auc, plot_fit, plot_timeseries

    WORKSPACE = Path(r"C:\Users\ctyja\data\20260603")
    INTERVAL = 10
    COLUMNS = 3

    TIMESERIES_DIR = WORKSPACE / "timeseries"
    RESULTS_DIR = WORKSPACE / "results"

    slide_channel_names = load_slide_channel_labels(WORKSPACE)
    timeseries_csvs = discover_timeseries_csvs(TIMESERIES_DIR)
    timeseries = {
        csv_path.name: load_timeseries_csv(csv_path) for csv_path in timeseries_csvs
    }
    auc_df = pd.read_csv(RESULTS_DIR / "auc.csv")
    fit_df = pd.read_csv(RESULTS_DIR / "fit.csv")

    return (
        COLUMNS,
        FIGURE_SIZE_IN,
        INTERVAL,
        auc,
        auc_df,
        boxplot_tick_labels,
        boxplot_x_axis_label,
        fit_df,
        math,
        mo,
        np,
        pd,
        plot_auc,
        plot_fit,
        plot_timeseries,
        plt,
        slide_channel_names,
        timeseries,
        timeseries_csvs,
        trace_color_alpha_from_fluor_name,
    )


@app.cell
def _(mo):
    mo.md(r"""
# Transfection CSV explorer

Load workspace CSVs with pandas, inspect the tables, then plot in-notebook.
This is meant for exploration — not a rerun of the CLI PNG pipeline.

Defaults: `C:\Users\ctyja\data\20260603`, 10 min/frame.
""")
    return


@app.cell
def _(auc_df, fit_df, mo, pd, timeseries):
    mo.vstack(
        [
            mo.md("### Timeseries files"),
            mo.ui.table(
                pd.DataFrame(
                    {
                        "file": list(timeseries),
                        "rows": [len(df) for df in timeseries.values()],
                        "rois": [df["roi"].nunique() for df in timeseries.values()],
                        "frames": [df["t"].nunique() for df in timeseries.values()],
                    }
                )
            ),
            mo.md("### AUC table"),
            mo.ui.table(auc_df),
            mo.md("### Fit table"),
            mo.ui.table(fit_df),
        ]
    )
    return


@app.cell
def _(fit_df, mo):
    fit_ok = fit_df.loc[fit_df["success"].astype(str).str.lower().eq("true")].copy()
    if "protein_lifetime" not in fit_ok.columns:
        fit_ok["protein_lifetime"] = 1.0 / fit_ok["protein_decay_rate"]
    if "mrna_lifetime" not in fit_ok.columns:
        fit_ok["mrna_lifetime"] = 1.0 / fit_ok["mrna_decay_rate"]
    mo.ui.table(
        fit_ok[
            [
                "slide_channel",
                "pos",
                "roi",
                "protein_lifetime",
                "mrna_lifetime",
                "translation_onset",
                "transfection_efficiency",
            ]
        ].sort_values(["slide_channel", "pos", "roi"])
    )
    return (fit_ok,)


@app.cell
def _(
    COLUMNS,
    FIGURE_SIZE_IN,
    INTERVAL,
    math,
    plot_timeseries,
    plt,
    slide_channel_names,
    timeseries,
    timeseries_csvs,
    trace_color_alpha_from_fluor_name,
):
    def plot_corrected_traces():
        panels = [(path, timeseries[path.name]) for path in timeseries_csvs]
        panel_ylims = [
            plot_timeseries.percentile_ylim(plot_timeseries.panel_values(df, "corrected"))
            for _, df in panels
        ]
        rows = math.ceil(len(panels) / COLUMNS)
        fig, axes = plt.subplots(rows, COLUMNS, squeeze=False, figsize=FIGURE_SIZE_IN)

        for index, (ax, (csv_path, df)) in enumerate(zip(axes.flatten(), panels)):
            color, alpha = trace_color_alpha_from_fluor_name(
                plot_timeseries.trace_naming_haystack(csv_path, slide_channel_names)
            )
            groups = df.groupby(plot_timeseries.trace_group_columns(df), sort=True)
            for _, trace in groups:
                minutes = trace["t"].to_numpy(dtype=float) * INTERVAL
                ax.plot(minutes, trace["corrected"], color=color, alpha=alpha)
            ax.set_title(
                plot_timeseries.subplot_title(
                    csv_path, groups.ngroups, slide_channel_names=slide_channel_names
                )
            )
            ax.set_xlabel("minutes")
            ax.set_ylabel("corrected intensity")
            ax.set_ylim(*panel_ylims[index])

        for ax in axes.flatten()[len(panels) :]:
            ax.axis("off")

        fig.tight_layout()
        return fig

    plot_corrected_traces()


@app.cell
def _(
    FIGURE_SIZE_IN,
    auc_df,
    boxplot_tick_labels,
    boxplot_x_axis_label,
    mo,
    np,
    plt,
    plot_timeseries,
    slide_channel_names,
):
    def draw_auc_boxplots():
        positive = auc_df.loc[auc_df["auc"] > 0].copy()
        slide_channels = sorted(positive["slide_channel"].astype(int).unique())
        grouped = [
            positive.loc[positive["slide_channel"] == sc, "auc"].to_numpy(dtype=float)
            for sc in slide_channels
        ]
        counts = [values.size for values in grouped]
        labels = boxplot_tick_labels(slide_channels, counts, slide_channel_names)
        xlabel = boxplot_x_axis_label(slide_channel_names)

        def make_figure(log_scale: bool):
            fig, ax = plt.subplots(figsize=FIGURE_SIZE_IN)
            ax.boxplot(grouped, tick_labels=labels)
            ax.set_xlabel(xlabel)
            ax.set_ylabel("AUC")
            if log_scale:
                ax.set_yscale("log")
                ax.set_title("AUC (log scale)")
            else:
                arrays = [values for values in grouped if values.size]
                y_low, y_high = plot_timeseries.percentile_ylim(
                    np.concatenate(arrays) if arrays else np.array([])
                )
                ax.set_ylim(y_low, y_high)
                ax.set_title("AUC (linear scale)")
            fig.tight_layout()
            return fig

        return mo.vstack([make_figure(False), make_figure(True)])

    draw_auc_boxplots()


@app.cell
def _(
    FIGURE_SIZE_IN,
    boxplot_tick_labels,
    boxplot_x_axis_label,
    fit_ok,
    mo,
    np,
    plot_fit,
    plot_timeseries,
    plt,
    slide_channel_names,
):
    def draw_fit_parameter_boxplots():
        figs = []
        for parameter, ylabel in plot_fit.PLOTTED_PARAMETERS:
            for log_scale in (
                (False, True) if parameter == "transfection_efficiency" else (False,)
            ):
                parameter_df = fit_ok.dropna(subset=[parameter]).copy()
                if log_scale:
                    parameter_df = parameter_df.loc[parameter_df[parameter] > 0].copy()

                slide_channels = sorted(parameter_df["slide_channel"].astype(int).unique())
                trace_counts = [
                    int(
                        parameter_df.loc[parameter_df["slide_channel"] == sc, parameter].shape[0]
                    )
                    for sc in slide_channels
                ]
                grouped = [
                    parameter_df.loc[parameter_df["slide_channel"] == sc, parameter].to_numpy(
                        dtype=float
                    )
                    for sc in slide_channels
                ]

                fig, ax = plt.subplots(figsize=FIGURE_SIZE_IN)
                ax.boxplot(
                    grouped,
                    tick_labels=boxplot_tick_labels(
                        slide_channels, trace_counts, slide_channel_names
                    ),
                )
                ax.set_xlabel(boxplot_x_axis_label(slide_channel_names))
                ax.set_ylabel(ylabel)
                if log_scale:
                    ax.set_yscale("log")
                    ax.set_title(f"{ylabel} (log scale)")
                else:
                    arrays = [values for values in grouped if values.size]
                    y_low, y_high = plot_timeseries.percentile_ylim(
                        np.concatenate(arrays) if arrays else np.array([])
                    )
                    ax.set_ylim(y_low, y_high)
                    ax.set_title(f"{ylabel} (linear scale)")
                fig.tight_layout()
                figs.append(fig)

        return mo.vstack(figs)

    draw_fit_parameter_boxplots()


@app.cell
def _(
    COLUMNS,
    FIGURE_SIZE_IN,
    INTERVAL,
    auc,
    fit_ok,
    math,
    plot_fit,
    plot_timeseries,
    plt,
    slide_channel_names,
    timeseries,
    timeseries_csvs,
    trace_color_alpha_from_fluor_name,
):
    def draw_fitted_traces():
        fit_lookup = fit_ok.set_index(["slide_channel", "pos", "roi"])
        rows = math.ceil(len(timeseries_csvs) / COLUMNS)
        fig, axes = plt.subplots(rows, COLUMNS, squeeze=False, figsize=FIGURE_SIZE_IN)

        for ax, csv_path in zip(axes.flatten(), timeseries_csvs):
            df = timeseries[csv_path.name]
            slide_channel = auc.parse_slide_channel(csv_path)
            color, alpha = trace_color_alpha_from_fluor_name(
                plot_timeseries.trace_naming_haystack(csv_path, slide_channel_names)
            )
            matched = 0
            group_cols = plot_timeseries.trace_group_columns(df)
            for key, trace in df.groupby(group_cols, sort=True):
                if not isinstance(key, tuple):
                    key = (key,)
                pos = int(key[0]) if "pos" in df.columns else 0
                roi = int(key[-1])
                lookup = (slide_channel, pos, roi)
                if lookup not in fit_lookup.index:
                    continue
                row = fit_lookup.loc[lookup]
                minutes = trace["t"].to_numpy(dtype=float) * INTERVAL
                predicted = plot_fit.fitted_trace_values(minutes, row)
                ax.plot(minutes, predicted, color=color, alpha=alpha)
                matched += 1

            ax.set_title(
                plot_timeseries.subplot_title(
                    csv_path, matched, slide_channel_names=slide_channel_names
                )
            )
            ax.set_xlabel("minutes")
            ax.set_ylabel("corrected intensity")
            ax.set_ylim(
                *plot_timeseries.percentile_ylim(
                    plot_timeseries.panel_values(df, "corrected")
                )
            )

        for ax in axes.flatten()[len(timeseries_csvs) :]:
            ax.axis("off")

        fig.tight_layout()
        return fig

    draw_fitted_traces()


if __name__ == "__main__":
    app.run()
