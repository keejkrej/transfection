"""Default figure geometry and typography for analyze plot PNGs."""

from __future__ import annotations

import matplotlib as mpl

# Output rasterization for saved PNGs.
FIGURE_DPI = 100

# Fixed figure size (inches) for trace grids and box plots.
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
