from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd
import tifffile

HELP = "Microscopy ROI pipelines: slide mapping and timeseries metrics."
PROG_NAME = "transfection"
TIMESERIES_DIRNAME = "timeseries"
RESULTS_DIRNAME = "results"
DEFAULT_QUARTILES = "0.10,0.25,0.50,0.75,0.90"
FIGURE_DPI = 100
FIGURE_SIZE_IN = (12.0, 8.0)

_TRACE_ALPHA = 0.1
_WORKSPACE_METRICS_STEM = re.compile(r"^sc\d+_ch\d+$")
_DEFAULT_RCPARAMS: dict[str, float] = {
    "font.size": 18.0,
    "axes.titlesize": 18.0,
    "axes.labelsize": 18.0,
    "xtick.labelsize": 17.0,
    "ytick.labelsize": 17.0,
    "legend.fontsize": 17.0,
}

mpl.rcParams.update(_DEFAULT_RCPARAMS)


@dataclass(frozen=True)
class SlideChannelMapping:
    positions: list[int]
    image_channel: int
    sample_name: str


type SlideMapping = dict[int, SlideChannelMapping]


@dataclass(frozen=True)
class RoiCrop:
    roi: int
    file_name: str
    shape: tuple[int, ...]
    x: int | None
    y: int | None
    w: int | None
    h: int | None


@dataclass(frozen=True)
class PositionIndex:
    position: int
    axis_order: str
    time_count: int
    channel_count: int
    z_count: int
    rois: tuple[RoiCrop, ...]


def normalize_argv(argv: Sequence[str] | None) -> list[str] | None:
    return list(argv) if argv is not None else None


def resolve_slide_path(dataset_root: Path, output: Path | None = None) -> Path:
    if output is None:
        return (dataset_root / "slide.json").resolve()
    return output.expanduser().resolve()


def parse_position_token(token: str) -> list[int]:
    raw = token.strip()
    if not raw:
        raise ValueError("Empty position token")

    if ":" not in raw:
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"Invalid position token: {raw!r}") from exc
        if value < 0:
            raise ValueError(f"Positions must be non-negative, got {value}")
        return [value]

    parts = [part.strip() for part in raw.split(":")]
    if len(parts) not in {2, 3}:
        raise ValueError(f"Invalid slice token: {raw!r}")
    if any(part == "" for part in parts[:2]):
        raise ValueError(f"Slices must include explicit start and stop: {raw!r}")

    try:
        start = int(parts[0])
        stop = int(parts[1])
        step = int(parts[2]) if len(parts) == 3 else 1
    except ValueError as exc:
        raise ValueError(f"Invalid slice token: {raw!r}") from exc

    if start < 0 or stop < 0:
        raise ValueError(f"Positions must be non-negative in slice {raw!r}")
    if step <= 0:
        raise ValueError(f"Slice step must be > 0 in {raw!r}")

    values = list(range(start, stop, step))
    if not values:
        raise ValueError(f"Slice produced no positions: {raw!r}")
    return values


def parse_position_spec(spec: str) -> list[int]:
    tokens = [token.strip() for token in spec.split(",")]
    if not any(tokens):
        raise ValueError("Position spec is empty")

    positions: list[int] = []
    for token in tokens:
        if not token:
            raise ValueError("Position spec contains an empty token")
        positions.extend(parse_position_token(token))

    return sorted(set(positions))


def parse_slide_mapping_spec(
    spec: str,
    *,
    source_label: str = "--sample mapping",
) -> SlideMapping:
    trimmed = spec.strip()
    if not trimmed:
        raise ValueError(f"{source_label}: empty")

    segments = [segment.strip() for segment in trimmed.split("|") if segment.strip()]
    if not segments:
        raise ValueError(f"{source_label}: empty")

    raw_mapping: SlideMapping = {}
    for slide_channel, segment in enumerate(segments):
        if "@" not in segment or "#" not in segment:
            raise ValueError(
                f"{source_label}: expected 'positions@image_channel#sample_name', got {segment!r}"
            )

        before_hash, sample_name = segment.rsplit("#", 1)
        sample_name = sample_name.strip()
        if not sample_name:
            raise ValueError(f"{source_label}: sample_name after # must be non-empty ({segment!r})")

        before_hash = before_hash.strip()
        if "@" not in before_hash:
            raise ValueError(
                f"{source_label}: expected 'positions@image_channel' before '#' ({segment!r})"
            )
        positions_str, image_ch_str = before_hash.rsplit("@", 1)
        positions_str, image_ch_str = positions_str.strip(), image_ch_str.strip()

        try:
            image_channel = int(image_ch_str)
        except ValueError as exc:
            raise ValueError(
                f"{source_label}: image channel must be an integer for slide channel {slide_channel}"
            ) from exc

        try:
            positions = parse_position_spec(positions_str)
        except ValueError as exc:
            raise ValueError(f"{source_label}: {exc}") from exc

        raw_mapping[slide_channel] = SlideChannelMapping(
            positions=positions,
            image_channel=image_channel,
            sample_name=sample_name,
        )

    return validate_slide_mapping(raw_mapping)


def validate_slide_mapping(raw: object, *, source: Path | None = None) -> SlideMapping:
    source_label = str(source) if source is not None else "slide mapping"
    if not isinstance(raw, dict):
        raise ValueError(f"Slide mapping must be a JSON object: {source_label}")

    slide_positions: SlideMapping = {}
    for raw_channel, raw_entry in raw.items():
        try:
            slide_channel = int(raw_channel)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Slide channel keys must be non-negative integers, got {raw_channel!r}"
            ) from exc
        if slide_channel < 0:
            raise ValueError(f"Slide channel keys must be non-negative integers, got {raw_channel!r}")

        if isinstance(raw_entry, SlideChannelMapping):
            raw_positions = raw_entry.positions
            raw_image_channel = raw_entry.image_channel
            raw_sample_name = raw_entry.sample_name
        else:
            if not isinstance(raw_entry, dict):
                raise ValueError(
                    f"Slide channel entries must be objects, got {type(raw_entry).__name__} for {slide_channel}"
                )
            if "positions" not in raw_entry:
                raise ValueError(f"Slide channel {slide_channel} is missing required field 'positions'")
            if "image_channel" not in raw_entry:
                raise ValueError(
                    f"Slide channel {slide_channel} is missing required field 'image_channel'"
                )
            if "sample_name" not in raw_entry:
                raise ValueError(
                    f"Slide channel {slide_channel} is missing required field 'sample_name'"
                )
            raw_positions = raw_entry["positions"]
            raw_image_channel = raw_entry["image_channel"]
            raw_sample_name = raw_entry["sample_name"]

        if not isinstance(raw_positions, list):
            raise ValueError(
                f"Slide channel positions must be lists, got {type(raw_positions).__name__} for {slide_channel}"
            )
        if not isinstance(raw_image_channel, int) or isinstance(raw_image_channel, bool):
            raise ValueError(
                f"Slide image_channel for channel {slide_channel} must be an integer, got {raw_image_channel!r}"
            )
        if raw_image_channel < 0:
            raise ValueError(f"Slide image_channel must be non-negative, got {raw_image_channel}")
        if not isinstance(raw_sample_name, str):
            raise ValueError(
                f"sample_name for slide channel {slide_channel} must be a string, got {raw_sample_name!r}"
            )
        sample_name = raw_sample_name.strip()
        if not sample_name:
            raise ValueError(f"sample_name for slide channel {slide_channel} must be non-empty")

        positions_list: list[int] = []
        for entry in raw_positions:
            if not isinstance(entry, int) or isinstance(entry, bool):
                raise ValueError(
                    f"Slide positions for channel {slide_channel} must be integers, got {entry!r}"
                )
            if entry < 0:
                raise ValueError(f"Slide positions must be non-negative, got {entry}")
            positions_list.append(entry)
        if not positions_list:
            raise ValueError(f"{source_label} defines no positions for slide channel {slide_channel}")
        slide_positions[slide_channel] = SlideChannelMapping(
            positions=sorted(set(positions_list)),
            image_channel=raw_image_channel,
            sample_name=sample_name,
        )

    if not slide_positions:
        raise ValueError(f"{source_label} defines no slide channels")
    return dict(sorted(slide_positions.items()))


def load_slide_mapping(slide_path: Path) -> SlideMapping:
    raw = json.loads(slide_path.read_text(encoding="utf-8"))
    return validate_slide_mapping(raw, source=slide_path)


def serialize_slide_mapping(mapping: SlideMapping) -> str:
    validated_mapping = validate_slide_mapping(mapping)
    ordered = {
        str(channel): {
            "positions": validated_mapping[channel].positions,
            "image_channel": validated_mapping[channel].image_channel,
            "sample_name": validated_mapping[channel].sample_name,
        }
        for channel in sorted(validated_mapping)
    }
    return json.dumps(ordered, indent=2) + "\n"


def write_slide_mapping(mapping: SlideMapping, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(serialize_slide_mapping(mapping), encoding="utf-8")
    return output_path.resolve()


def position_dir(dataset_root: Path, pos: int) -> Path:
    pos_dir = (dataset_root / "roi" / f"Pos{pos}").resolve()
    if not pos_dir.is_dir():
        raise ValueError(f"No ROI directory found for --pos={pos}: {pos_dir}")
    return pos_dir


def _coerce_optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def read_position_index(pos_dir: Path) -> PositionIndex:
    index_path = pos_dir / "index.json"
    if not index_path.is_file():
        raise ValueError(f"Missing ROI index: {index_path}")

    raw = json.loads(index_path.read_text(encoding="utf-8"))
    axis_order = str(raw.get("axisOrder", "")).upper()
    if not axis_order:
        raise ValueError(f"{index_path} is missing axisOrder")

    rois: list[RoiCrop] = []
    for roi_entry in raw.get("rois", []):
        file_name = str(roi_entry["fileName"])
        shape = tuple(int(value) for value in roi_entry["shape"])
        bbox = roi_entry.get("bbox") or {}
        rois.append(
            RoiCrop(
                roi=int(roi_entry["roi"]),
                file_name=file_name,
                shape=shape,
                x=_coerce_optional_int(bbox.get("x")),
                y=_coerce_optional_int(bbox.get("y")),
                w=_coerce_optional_int(bbox.get("w")),
                h=_coerce_optional_int(bbox.get("h")),
            )
        )

    if not rois:
        raise ValueError(f"No ROI entries found in {index_path}")

    return PositionIndex(
        position=int(raw.get("position", 0)),
        axis_order=axis_order,
        time_count=int(raw.get("timeCount", 1)),
        channel_count=int(raw.get("channelCount", 1)),
        z_count=int(raw.get("zCount", 1)),
        rois=tuple(rois),
    )


def validate_channel_index(index: PositionIndex, channel: int) -> None:
    if channel < 0 or channel >= index.channel_count:
        raise ValueError(f"--channel must be between 0 and {index.channel_count - 1}, got {channel}")


def read_roi_stack(roi_path: Path, expected_shape: tuple[int, ...]) -> np.ndarray:
    stack = np.asarray(tifffile.imread(roi_path))
    if stack.shape != expected_shape:
        expected_size = int(np.prod(expected_shape, dtype=np.int64))
        if stack.size != expected_size:
            raise ValueError(f"{roi_path} shape mismatch: expected {expected_shape}, got {stack.shape}")
        stack = stack.reshape(expected_shape)
    return stack


def roi_frame_2d(
    stack: np.ndarray, axis_order: str, *, timepoint: int, channel: int, z_index: int = 0
) -> np.ndarray:
    if len(axis_order) != stack.ndim:
        raise ValueError(f"Axis order {axis_order!r} does not match ROI stack ndim={stack.ndim}")

    slicer: list[int | slice] = []
    for axis, size in zip(axis_order, stack.shape):
        if axis == "T":
            if timepoint >= size:
                raise ValueError(f"Time index {timepoint} out of range for axis size {size}")
            slicer.append(timepoint)
        elif axis == "C":
            if channel >= size:
                raise ValueError(f"Channel index {channel} out of range for axis size {size}")
            slicer.append(channel)
        elif axis == "Z":
            if z_index >= size:
                raise ValueError(f"Z index {z_index} out of range for axis size {size}")
            slicer.append(z_index)
        elif axis in {"Y", "X"}:
            slicer.append(slice(None))
        else:
            if size != 1:
                raise ValueError(
                    f"Unsupported non-singleton axis {axis!r} in ROI stack with shape {stack.shape}"
                )
            slicer.append(0)

    frame = np.asarray(stack[tuple(slicer)])
    if frame.ndim != 2:
        raise ValueError(f"Expected a 2D ROI frame, got shape={frame.shape}")
    return frame


def quantile_column_name(quartile: float) -> str:
    quartile_pct = quartile * 100.0
    if abs(quartile_pct - round(quartile_pct)) > 1e-9:
        raise ValueError(f"Quartiles must map to integer percentage column names, got {quartile}")
    return f"q{int(round(quartile_pct))}"


def parse_quartiles(quartiles: str) -> list[float]:
    values: list[float] = []
    for raw_value in quartiles.split(","):
        value = float(raw_value.strip())
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"Quartiles must be between 0 and 1, got {value}")
        quantile_column_name(value)
        values.append(value)
    if not values:
        raise ValueError("At least one quartile is required")
    unique_values = sorted(set(values))
    if len(unique_values) != len(values):
        raise ValueError(f"Quartiles must be unique, got {quartiles}")
    return unique_values


def compute_roi_metrics(
    pos_dir: Path,
    index: PositionIndex,
    *,
    channel: int,
    quartiles: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, int | float | None]] = []
    for roi in index.rois:
        roi_path = pos_dir / roi.file_name
        if not roi_path.is_file():
            raise ValueError(f"Missing ROI TIFF referenced by index.json: {roi_path}")

        stack = read_roi_stack(roi_path, roi.shape)
        for timepoint in range(index.time_count):
            patch = np.asarray(
                roi_frame_2d(stack, index.axis_order, timepoint=timepoint, channel=channel),
                dtype=np.uint64,
            )
            quantile_values = np.quantile(patch, quartiles, method="linear")
            metrics = {
                quantile_column_name(quartile): float(quantile_value)
                for quartile, quantile_value in zip(quartiles, np.atleast_1d(quantile_values))
            }
            sum_value = int(patch.sum(dtype=np.uint64))
            rows.append(
                {
                    "pos": index.position,
                    "channel": channel,
                    "t": timepoint,
                    "roi": roi.roi,
                    "x": roi.x,
                    "y": roi.y,
                    "w": roi.w,
                    "h": roi.h,
                    "area": int(patch.size),
                    "sum": sum_value,
                    **metrics,
                }
            )

    if not rows:
        raise ValueError("No rows produced")
    return pd.DataFrame(rows).sort_values(["roi", "t"]).reset_index(drop=True)


def write_metrics_csv(df: pd.DataFrame, output_csv: Path) -> None:
    if df.empty:
        raise ValueError("No rows to write")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)


def load_timeseries_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    required = {"roi", "t", "corrected"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(
            f"{csv_path} is missing required columns for timeseries metrics: {sorted(missing)}"
        )
    sort_columns = ["roi", "t"]
    if "pos" in df.columns:
        sort_columns = ["pos", *sort_columns]
    return df.sort_values(sort_columns).reset_index(drop=True)


def trace_color_alpha_from_fluor_name(name: str) -> tuple[str, float]:
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


def is_workspace_metrics_timeseries_csv(path: Path) -> bool:
    return bool(_WORKSPACE_METRICS_STEM.fullmatch(path.stem))


def workspace_timeseries_dir(workspace: Path) -> Path:
    return workspace.resolve() / TIMESERIES_DIRNAME


def workspace_results_dir(workspace: Path) -> Path:
    return workspace.resolve() / RESULTS_DIRNAME


def discover_timeseries_csvs(timeseries_dir: Path) -> list[Path]:
    if not timeseries_dir.is_dir():
        raise ValueError(
            f"Expected {TIMESERIES_DIRNAME}/ directory at {timeseries_dir}. "
            "Run transfection timeseries first."
        )
    csvs = sorted(timeseries_dir.glob("*.csv"), key=lambda path: path.name)
    if not csvs:
        raise ValueError(f"No CSV metrics files in {timeseries_dir}")
    metrics = [path for path in csvs if is_workspace_metrics_timeseries_csv(path)]
    if not metrics:
        raise ValueError(
            f"No workspace metrics CSV files (expected stem sc{{slide}}_ch{{channel}}.csv) in {timeseries_dir}"
        )
    return metrics


def infer_workspace_for_plot_csv(csv_file: Path) -> Path:
    parent = csv_file.parent.resolve()
    if parent.name == RESULTS_DIRNAME:
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


def boxplot_tick_labels(
    slide_channels: list[int], trace_counts: list[int], slide_labels: dict[int, str]
) -> list[str]:
    return [
        f"{slide_labels.get(sc, str(sc))}\n(n={n})"
        for sc, n in zip(slide_channels, trace_counts, strict=True)
    ]


def boxplot_x_axis_label(slide_labels: dict[int, str]) -> str:
    return "condition" if slide_labels else "slide channel"
