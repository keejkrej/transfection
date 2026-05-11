"""Analysis helpers."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from lisca.analysis.events import first_sustained_threshold_crossing, first_sustained_true
from lisca.analysis.roi import (
    DEFAULT_QUARTILES,
    compute_roi_metrics,
    default_output_plot_path,
    load_timeseries_csv,
    parse_quartiles,
    quantile_column_name,
    write_metrics_csv,
    write_trace_plot,
)

_BINDING_EXPORTS = {
    "DEFAULT_CHANNEL",
    "DEFAULT_FRAMES_PER_CHANNEL",
    "DEFAULT_PRETRAINED_MODEL",
    "DEFAULT_VIZ_MIN_INTENSITY",
    "PlotSpotsResult",
    "SpotDetectionResult",
    "run_detection",
    "run_plot_spots",
}

__all__ = [
    "DEFAULT_QUARTILES",
    "DEFAULT_CHANNEL",
    "DEFAULT_FRAMES_PER_CHANNEL",
    "DEFAULT_PRETRAINED_MODEL",
    "DEFAULT_VIZ_MIN_INTENSITY",
    "PlotSpotsResult",
    "SpotDetectionResult",
    "compute_roi_metrics",
    "default_output_plot_path",
    "first_sustained_threshold_crossing",
    "first_sustained_true",
    "load_timeseries_csv",
    "parse_quartiles",
    "quantile_column_name",
    "run_detection",
    "run_plot_spots",
    "write_metrics_csv",
    "write_trace_plot",
]


def __getattr__(name: str) -> Any:
    if name == "binding":
        return import_module("lisca.analysis.binding")
    if name in _BINDING_EXPORTS:
        binding = import_module("lisca.analysis.binding")
        return getattr(binding, name)
    raise AttributeError(f"module 'lisca.analysis' has no attribute {name!r}")
