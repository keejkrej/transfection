from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import numpy as np


DEFAULT_FRAMES_PER_CHANNEL = 145
DEFAULT_CHANNEL = 0
DEFAULT_PRETRAINED_MODEL = "synth_3d"
DEFAULT_VIZ_MIN_INTENSITY = 20.0
CSV_COLUMNS = (
    "source_tif",
    "channel",
    "z",
    "y",
    "x",
    "probability",
    "intensity",
)


@dataclass(frozen=True)
class SpotDetectionResult:
    source_tif: Path
    output_csv: Path
    channel: int
    frames_per_channel: int
    spot_count: int


@dataclass(frozen=True)
class PlotSpotsResult:
    spots_csv: Path
    source_tif: Path
    raw_viz_html: Path
    result_viz_html: Path
    histogram_png: Path
    spot_count: int
    plotted_spot_count: int
    min_intensity: float


def parse_tiles(tiles: str | None) -> tuple[int, int, int] | None:
    if tiles is None or not tiles.strip():
        return None
    parts = [part.strip() for part in tiles.split(",")]
    if len(parts) != 3:
        raise ValueError("--tiles must contain exactly three comma-separated integers: Z,Y,X")
    parsed = tuple(int(part) for part in parts)
    if any(value < 1 for value in parsed):
        raise ValueError("--tiles values must be positive integers")
    return parsed


def tiff_inputs(input_path: Path) -> list[Path]:
    resolved_path = input_path.resolve()
    if resolved_path.is_file():
        return [resolved_path]
    if not resolved_path.is_dir():
        raise FileNotFoundError(f"Input path does not exist: {resolved_path}")

    paths = sorted(
        {
            path.resolve(): path.resolve()
            for pattern in ("*.tif", "*.tiff", "*.TIF", "*.TIFF")
            for path in resolved_path.glob(pattern)
            if path.is_file()
        }.values()
    )
    if not paths:
        raise ValueError(f"No TIFF files found in {resolved_path}")
    return paths


def default_output_csv_path(
    source_tif: Path,
    output: Path | None,
    *,
    channel: int,
    multiple_inputs: bool = False,
) -> Path:
    if output is None:
        return (source_tif.parent / "spotiflow_results" / f"{source_tif.stem}_ch{channel}_spots.csv").resolve()

    resolved_output = output.resolve()
    if multiple_inputs:
        if resolved_output.suffix:
            raise ValueError("--output must be a directory when detecting spots for multiple TIFFs")
        return (resolved_output / f"{source_tif.stem}_spots.csv").resolve()

    if resolved_output.suffix:
        return resolved_output
    return (resolved_output / f"{source_tif.stem}_spots.csv").resolve()


def channel_output_csv_path(output_csv: Path, channel: int) -> Path:
    if f"_ch{channel}_" in output_csv.stem:
        return output_csv
    return output_csv.with_name(f"{output_csv.stem}_ch{channel}{output_csv.suffix}")


def default_viz_paths(output_csv: Path) -> tuple[Path, Path]:
    return (
        output_csv.with_name(f"{output_csv.stem}_raw_3d.html"),
        output_csv.with_name(f"{output_csv.stem}_result_3d.html"),
    )


def output_viz_paths(spots_csv: Path, output_dir: Path | None) -> tuple[Path, Path]:
    if output_dir is None:
        return default_viz_paths(spots_csv)
    resolved_output_dir = output_dir.resolve()
    return (
        resolved_output_dir / f"{spots_csv.stem}_raw_3d.html",
        resolved_output_dir / f"{spots_csv.stem}_result_3d.html",
    )


def output_histogram_path(spots_csv: Path, output_dir: Path | None) -> Path:
    if output_dir is None:
        return spots_csv.with_name(f"{spots_csv.stem}_intensity_histogram.png")
    return output_dir.resolve() / f"{spots_csv.stem}_intensity_histogram.png"


def read_channel_volume(tif_path: Path, *, channel: int, frames_per_channel: int) -> Any:
    if channel < 0:
        raise ValueError("channel must be non-negative")
    if frames_per_channel < 1:
        raise ValueError("frames_per_channel must be positive")

    import tifffile

    with tifffile.TiffFile(tif_path) as tif:
        page_count = len(tif.pages)
        start = channel * frames_per_channel
        stop = start + frames_per_channel
        if page_count >= stop:
            return tif.asarray(key=range(start, stop))

        series = tif.series[0] if tif.series else None
        if series is not None and len(series.shape) >= 3 and series.shape[0] >= stop:
            return series.asarray()[start:stop]

    raise ValueError(
        f"{tif_path} has {page_count} TIFF pages, cannot read channel {channel} "
        f"as pages {start}..{stop - 1}"
    )


def load_spotiflow_model(model: str, *, cache_dir: Path | None = None) -> Any:
    try:
        from spotiflow.model import Spotiflow
    except ImportError as error:
        raise RuntimeError(
            "Spotiflow is required for binding spot detection. Install lisca with "
            "binding dependencies, then rerun this command."
        ) from error

    model_path = Path(model).expanduser()
    if model_path.exists():
        return Spotiflow.from_folder(model_path)
    if cache_dir is None:
        return Spotiflow.from_pretrained(model)
    return Spotiflow.from_pretrained(model, cache_dir=cache_dir)


def array_values(values: Any, count: int) -> list[Any | None]:
    if values is None:
        return [None] * count
    try:
        sequence = list(values)
    except TypeError:
        return [None] * count
    if len(sequence) != count:
        return [None] * count
    return sequence


def csv_scalar(value: Any) -> Any:
    if value is None:
        return ""
    array = np.asarray(value)
    if array.ndim == 0:
        return array.item()
    if array.size == 1:
        return array.reshape(-1)[0].item()
    return value


def scalar_array(values: Any, count: int) -> np.ndarray | None:
    if values is None:
        return None
    array = np.asarray(values, dtype=float)
    if array.size != count:
        return None
    return array.reshape(count, -1)[:, 0]


def filter_points_by_min_intensity(
    points: Any,
    intensities: Any,
    *,
    min_intensity: float,
) -> np.ndarray:
    points_array = np.asarray(points)
    if points_array.size == 0:
        return points_array.reshape(0, 3)
    if min_intensity <= 0:
        return points_array

    intensity_array = scalar_array(intensities, len(points_array))
    if intensity_array is None:
        return points_array

    return points_array[intensity_array >= min_intensity]


def plotted_point_count(points: Any, intensities: Any, *, min_intensity: float) -> int:
    return len(filter_points_by_min_intensity(points, intensities, min_intensity=min_intensity))


def spot_rows(
    source_tif: Path,
    *,
    channel: int,
    points: Any,
    details: SimpleNamespace,
) -> list[dict[str, object]]:
    probabilities = array_values(getattr(details, "prob", None), len(points))
    intensities = array_values(getattr(details, "intens", None), len(points))
    rows: list[dict[str, object]] = []

    for point, probability, intensity in zip(points, probabilities, intensities):
        coordinates = list(point)
        if len(coordinates) < 3:
            raise ValueError(f"Spotiflow returned a point with fewer than 3 coordinates: {coordinates}")
        z, y, x = coordinates[-3:]
        rows.append(
            {
                "source_tif": str(source_tif),
                "channel": channel,
                "z": z,
                "y": y,
                "x": x,
                "probability": csv_scalar(probability),
                "intensity": csv_scalar(intensity),
            }
        )
    return rows


def write_spots_csv(rows: list[dict[str, object]], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def read_spots_csv(spots_csv: Path) -> tuple[Path, int, np.ndarray, np.ndarray]:
    resolved_csv = spots_csv.resolve()
    with resolved_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = set(CSV_COLUMNS) - fieldnames
        if missing:
            raise ValueError(f"{resolved_csv} is missing required columns: {sorted(missing)}")
        rows = list(reader)

    if not rows:
        raise ValueError(f"{resolved_csv} contains no spot rows")

    source_tifs = {row["source_tif"] for row in rows}
    channels = {row["channel"] for row in rows}
    if len(source_tifs) != 1:
        raise ValueError(f"{resolved_csv} must contain spots from exactly one source_tif")
    if len(channels) != 1:
        raise ValueError(f"{resolved_csv} must contain spots from exactly one channel")

    points = np.asarray([[float(row["z"]), float(row["y"]), float(row["x"])] for row in rows], dtype=float)
    intensities = np.asarray([float(row["intensity"]) if row["intensity"] else np.nan for row in rows], dtype=float)
    return Path(next(iter(source_tifs))).expanduser().resolve(), int(next(iter(channels))), points, intensities


def normalize_volume_for_render(volume: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(volume, (1.0, 99.8))
    if hi <= lo:
        return np.zeros(volume.shape, dtype=np.float32)
    normalized = (volume.astype(np.float32, copy=False) - lo) / (hi - lo)
    return np.clip(normalized, 0, 1)


def downsample_volume_for_render(
    volume: np.ndarray,
    *,
    max_voxels: int,
) -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    if volume.ndim != 3:
        raise ValueError(f"3D visualization requires a ZYX volume, got shape {volume.shape}")
    if max_voxels < 1:
        raise ValueError("max_voxels must be positive")

    if volume.size <= max_voxels:
        z = np.arange(volume.shape[0], dtype=np.float32)
        y = np.arange(volume.shape[1], dtype=np.float32)
        x = np.arange(volume.shape[2], dtype=np.float32)
        return volume, (z, y, x)

    scale = (max_voxels / float(volume.size)) ** (1.0 / volume.ndim)
    target_shape = tuple(max(2, min(size, int(np.floor(size * scale)))) for size in volume.shape)
    while np.prod(target_shape) > max_voxels:
        axis = int(np.argmax(target_shape))
        target_shape = tuple(max(2, size - 1) if index == axis else size for index, size in enumerate(target_shape))

    z_idx = np.linspace(0, volume.shape[0] - 1, target_shape[0]).round().astype(np.intp)
    y_idx = np.linspace(0, volume.shape[1] - 1, target_shape[1]).round().astype(np.intp)
    x_idx = np.linspace(0, volume.shape[2] - 1, target_shape[2]).round().astype(np.intp)
    sampled = volume[np.ix_(z_idx, y_idx, x_idx)]
    return sampled, (
        z_idx.astype(np.float32),
        y_idx.astype(np.float32),
        x_idx.astype(np.float32),
    )


def build_volume_figure(
    volume: np.ndarray,
    *,
    title: str,
    colorscale: Any,
    opacity: float,
    isomin: float,
    surface_count: int,
    max_voxels: int,
) -> Any:
    import plotly.graph_objects as go

    sampled, axes = downsample_volume_for_render(volume, max_voxels=max_voxels)
    sampled = normalize_volume_for_render(sampled)
    z_axis, y_axis, x_axis = np.meshgrid(*axes, indexing="ij")
    fig = go.Figure()
    fig.add_trace(
        go.Volume(
            x=x_axis.flatten(),
            y=y_axis.flatten(),
            z=z_axis.flatten(),
            value=sampled.flatten(),
            isomin=isomin,
            isomax=max(float(sampled.max()), isomin),
            opacity=opacity,
            surface_count=surface_count,
            colorscale=colorscale,
            showscale=False,
            name=title,
        )
    )
    fig.update_layout(
        title=title,
        scene=dict(
            xaxis_title="X",
            yaxis_title="Y",
            zaxis_title="Z",
            aspectmode="data",
            bgcolor="black",
            xaxis=dict(backgroundcolor="black", gridcolor="gray", showbackground=True),
            yaxis=dict(backgroundcolor="black", gridcolor="gray", showbackground=True),
            zaxis=dict(backgroundcolor="black", gridcolor="gray", showbackground=True),
        ),
        paper_bgcolor="black",
        font_color="white",
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


def write_figure_html(fig: Any, path: Path) -> None:
    import plotly.io as pio

    figure_html = pio.to_html(
        fig,
        include_plotlyjs=True,
        full_html=False,
        default_width="100vw",
        default_height="100vh",
        config={"displaylogo": False, "responsive": True},
    )
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    html, body {{
      margin: 0;
      width: 100%;
      height: 100%;
      background: black;
      color: white;
      overflow: hidden;
    }}
    body > div {{
      width: 100vw;
      height: 100vh;
    }}
  </style>
</head>
<body>
{figure_html}
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def write_intensity_histogram(
    intensities: np.ndarray,
    *,
    output_png: Path,
    min_intensity: float,
    title: str,
) -> Path:
    import matplotlib.pyplot as plt

    finite_intensities = intensities[np.isfinite(intensities)]
    clipped_intensities = finite_intensities[finite_intensities >= min_intensity]

    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.hist(clipped_intensities, bins=80, color="#2c7fb8", alpha=0.82, edgecolor="white", linewidth=0.35)
    ax.set_title(
        f"{title} intensity histogram\n"
        f"{len(clipped_intensities)} of {len(finite_intensities)} spots shown, threshold >= {min_intensity:g}"
    )
    ax.set_xlabel("Spotiflow intensity")
    ax.set_ylabel("Spot count")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=160)
    plt.close(fig)
    return output_png


def write_3d_visualizations(
    volume: np.ndarray,
    points: Any,
    intensities: Any,
    *,
    raw_html: Path,
    result_html: Path,
    title_prefix: str,
    max_voxels: int,
    min_intensity: float,
) -> tuple[Path, Path]:
    import plotly.graph_objects as go

    input_colorscale = (
        (0.0, "rgb(0,0,0)"),
        (0.2, "rgb(24,24,24)"),
        (0.5, "rgb(96,96,96)"),
        (0.8, "rgb(192,192,192)"),
        (1.0, "rgb(255,255,255)"),
    )
    plotted_points = filter_points_by_min_intensity(
        points,
        intensities,
        min_intensity=min_intensity,
    )
    result_title = f"{title_prefix} Spotiflow result - {len(plotted_points)} of {len(points)} spots"
    if min_intensity > 0:
        result_title += f" (intensity >= {min_intensity:g})"

    raw_fig = build_volume_figure(
        volume,
        title=f"{title_prefix} raw channel volume",
        colorscale=input_colorscale,
        opacity=0.06,
        isomin=0.12,
        surface_count=18,
        max_voxels=max_voxels,
    )
    result_fig = build_volume_figure(
        volume,
        title=result_title,
        colorscale=input_colorscale,
        opacity=0.04,
        isomin=0.12,
        surface_count=12,
        max_voxels=max_voxels,
    )
    points_array = np.asarray(plotted_points)
    if points_array.size:
        result_fig.add_trace(
            go.Scatter3d(
                x=points_array[:, 2],
                y=points_array[:, 1],
                z=points_array[:, 0],
                mode="markers",
                marker=dict(size=3, color="deepskyblue", opacity=0.9, line=dict(width=0)),
                name="Spots",
            )
        )

    write_figure_html(raw_fig, raw_html)
    write_figure_html(result_fig, result_html)
    return raw_html, result_html


def detect_spots_in_tif(
    tif_path: Path,
    *,
    output_csv: Path,
    model: Any,
    channel: int = DEFAULT_CHANNEL,
    frames_per_channel: int = DEFAULT_FRAMES_PER_CHANNEL,
    prob_thresh: float | None = None,
    tiles: tuple[int, int, int] | None = None,
    max_tile_size: int | None = None,
    min_distance: int = 1,
    exclude_border: bool = False,
    peak_mode: Literal["fast", "skimage"] = "fast",
    device: str | None = "auto",
) -> SpotDetectionResult:
    resolved_tif = tif_path.resolve()
    volume = read_channel_volume(resolved_tif, channel=channel, frames_per_channel=frames_per_channel)
    points, details = model.predict(
        volume,
        prob_thresh=prob_thresh,
        n_tiles=tiles,
        max_tile_size=max_tile_size,
        min_distance=min_distance,
        exclude_border=exclude_border,
        peak_mode=peak_mode,
        device=device,
    )
    rows = spot_rows(resolved_tif, channel=channel, points=points, details=details)
    write_spots_csv(rows, output_csv)
    return SpotDetectionResult(
        source_tif=resolved_tif,
        output_csv=output_csv,
        channel=channel,
        frames_per_channel=frames_per_channel,
        spot_count=len(rows),
    )


def run_plot_spots(
    spots_csv: Path,
    *,
    output_dir: Path | None,
    source_tif: Path | None = None,
    frames_per_channel: int = DEFAULT_FRAMES_PER_CHANNEL,
    min_intensity: float = DEFAULT_VIZ_MIN_INTENSITY,
    max_voxels: int = 120_000,
) -> PlotSpotsResult:
    resolved_csv = spots_csv.resolve()
    csv_source_tif, channel, points, intensities = read_spots_csv(resolved_csv)
    resolved_source_tif = source_tif.expanduser().resolve() if source_tif is not None else csv_source_tif
    volume = read_channel_volume(resolved_source_tif, channel=channel, frames_per_channel=frames_per_channel)
    raw_html, result_html = output_viz_paths(resolved_csv, output_dir)
    histogram_png = output_histogram_path(resolved_csv, output_dir)
    title_prefix = f"{resolved_source_tif.name} channel {channel}"
    write_3d_visualizations(
        np.asarray(volume),
        points,
        intensities,
        raw_html=raw_html,
        result_html=result_html,
        title_prefix=title_prefix,
        max_voxels=max_voxels,
        min_intensity=min_intensity,
    )
    write_intensity_histogram(
        intensities,
        output_png=histogram_png,
        min_intensity=min_intensity,
        title=title_prefix,
    )
    return PlotSpotsResult(
        spots_csv=resolved_csv,
        source_tif=resolved_source_tif,
        raw_viz_html=raw_html,
        result_viz_html=result_html,
        histogram_png=histogram_png,
        spot_count=len(points),
        plotted_spot_count=plotted_point_count(points, intensities, min_intensity=min_intensity),
        min_intensity=min_intensity,
    )


def run_detection(
    input_path: Path,
    *,
    output: Path | None,
    model_name: str = DEFAULT_PRETRAINED_MODEL,
    cache_dir: Path | None = None,
    channel: int = DEFAULT_CHANNEL,
    frames_per_channel: int = DEFAULT_FRAMES_PER_CHANNEL,
    prob_thresh: float | None = None,
    tiles: tuple[int, int, int] | None = None,
    max_tile_size: int | None = None,
    min_distance: int = 1,
    exclude_border: bool = False,
    peak_mode: Literal["fast", "skimage"] = "fast",
    device: str | None = "auto",
) -> list[SpotDetectionResult]:
    inputs = tiff_inputs(input_path)
    multiple_inputs = len(inputs) > 1
    if multiple_inputs and output is not None and output.resolve().suffix:
        raise ValueError("--output must be a directory when detecting spots for multiple TIFFs")

    model = load_spotiflow_model(model_name, cache_dir=cache_dir.resolve() if cache_dir is not None else None)
    results: list[SpotDetectionResult] = []
    for tif_path in inputs:
        output_csv = default_output_csv_path(tif_path, output, channel=channel, multiple_inputs=multiple_inputs)
        output_csv = channel_output_csv_path(output_csv, channel)
        results.append(
            detect_spots_in_tif(
                tif_path,
                output_csv=output_csv,
                model=model,
                channel=channel,
                frames_per_channel=frames_per_channel,
                prob_thresh=prob_thresh,
                tiles=tiles,
                max_tile_size=max_tile_size,
                min_distance=min_distance,
                exclude_border=exclude_border,
                peak_mode=peak_mode,
                device=device,
            )
        )
    return results
