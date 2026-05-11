"""Fluorophore hints in file or channel names -> matplotlib trace color and alpha."""

from __future__ import annotations


_TRACE_ALPHA = 0.1


def trace_color_alpha_from_fluor_name(name: str) -> tuple[str, float]:
    """Return (matplotlib color, alpha) for traces from a free-text name (path stem, labels, etc.).

    Alpha is always 0.1. Substrings are matched case-insensitively. ``egfp`` is
    checked before ``gfp`` because ``egfp`` contains ``gfp`` as a substring.
    """
    haystack = name.lower()
    if "egfp" in haystack:
        color = "green"
    elif "mcherry" in haystack:
        color = "red"
    elif "gfp" in haystack:
        color = "green"
    elif "yfp" in haystack:
        color = "yellow"
    elif "bfp" in haystack:
        color = "blue"
    else:
        color = "gray"
    return (color, _TRACE_ALPHA)
