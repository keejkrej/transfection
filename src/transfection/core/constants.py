from __future__ import annotations

import matplotlib as mpl

HELP = "Microscopy ROI pipelines: slide mapping, segmentation masks, and timeseries metrics."
PROG_NAME = "transfection"
TIMESERIES_DIRNAME = "timeseries"
RESULTS_DIRNAME = "results"
DEFAULT_QUARTILES = "0.10,0.25,0.50,0.75,0.90"
FIGURE_DPI = 100
FIGURE_SIZE_IN = (12.0, 8.0)

_DEFAULT_RCPARAMS: dict[str, float] = {
    "font.size": 18.0,
    "axes.titlesize": 18.0,
    "axes.labelsize": 18.0,
    "xtick.labelsize": 17.0,
    "ytick.labelsize": 17.0,
    "legend.fontsize": 17.0,
}

mpl.rcParams.update(_DEFAULT_RCPARAMS)
