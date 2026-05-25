from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

from transfection.core import (
    RoiCrop,
    SlideChannelMapping,
    default_mask_path,
    load_slide_mapping,
    position_dir,
    read_mask_stack,
    read_position_index,
    read_roi_stack,
    roi_frame_2d,
    validate_channel_index,
)


REVIEW_FRAME_SIZE = 512


@dataclass(frozen=True)
class CheckSegmentVideo:
    output_path: Path
    frame_count: int


def default_output_dir(workspace: Path) -> Path:
    return (workspace.resolve() / "check-segment").resolve()


def default_video_path(output_dir: Path, *, position: int, roi: RoiCrop, channel: int) -> Path:
    return (output_dir / f"Pos{position}" / f"{Path(roi.file_name).stem}_ch{channel}.mp4").resolve()


def _normalization_bounds(frames: np.ndarray) -> tuple[float, float]:
    values = frames[np.isfinite(frames)].astype(np.float64, copy=False)
    if values.size == 0:
        return (0.0, 1.0)
    low, high = np.percentile(values, [1.0, 99.0])
    low_f, high_f = float(low), float(high)
    if low_f < high_f:
        return (low_f, high_f)
    return (low_f, low_f + 1.0)


def normalize_frame_to_rgb8(frame: np.ndarray, *, low: float, high: float) -> np.ndarray:
    scaled = (frame.astype(np.float64, copy=False) - low) / (high - low)
    gray = np.clip(scaled * 255.0, 0.0, 255.0).astype(np.uint8)
    return np.repeat(gray[:, :, np.newaxis], 3, axis=2)


def resize_nearest(image: np.ndarray, *, height: int, width: int) -> np.ndarray:
    if height < 1 or width < 1:
        raise ValueError(f"Resize target must be positive, got {height}x{width}")
    source_height, source_width = image.shape[:2]
    y_index = np.rint(np.linspace(0, source_height - 1, height)).astype(np.intp)
    x_index = np.rint(np.linspace(0, source_width - 1, width)).astype(np.intp)
    return image[y_index[:, np.newaxis], x_index]


def fit_to_square_canvas(image: np.ndarray, *, size: int = REVIEW_FRAME_SIZE) -> np.ndarray:
    source_height, source_width = image.shape[:2]
    scale = min(size / float(source_height), size / float(source_width))
    target_height = max(1, int(round(source_height * scale)))
    target_width = max(1, int(round(source_width * scale)))
    resized = resize_nearest(image, height=target_height, width=target_width)

    if image.ndim == 2:
        canvas = np.zeros((size, size), dtype=image.dtype)
        y0 = (size - target_height) // 2
        x0 = (size - target_width) // 2
        canvas[y0 : y0 + target_height, x0 : x0 + target_width] = resized
        return canvas

    canvas = np.zeros((size, size, image.shape[2]), dtype=image.dtype)
    y0 = (size - target_height) // 2
    x0 = (size - target_width) // 2
    canvas[y0 : y0 + target_height, x0 : x0 + target_width, :] = resized
    return canvas


def mask_contour(mask: np.ndarray) -> np.ndarray:
    mask_bool = np.asarray(mask, dtype=bool)
    if mask_bool.ndim != 2:
        raise ValueError(f"Expected a 2D mask, got shape={mask_bool.shape}")

    interior = mask_bool.copy()
    interior[1:, :] &= mask_bool[:-1, :]
    interior[:-1, :] &= mask_bool[1:, :]
    interior[:, 1:] &= mask_bool[:, :-1]
    interior[:, :-1] &= mask_bool[:, 1:]
    return mask_bool & ~interior


def dilate_2d(mask: np.ndarray) -> np.ndarray:
    mask_bool = np.asarray(mask, dtype=bool)
    dilated = mask_bool.copy()
    dilated[1:, :] |= mask_bool[:-1, :]
    dilated[:-1, :] |= mask_bool[1:, :]
    dilated[:, 1:] |= mask_bool[:, :-1]
    dilated[:, :-1] |= mask_bool[:, 1:]
    return dilated


def overlay_contour(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    frame = rgb.copy()
    contour = dilate_2d(mask_contour(mask))
    frame[contour] = np.array([255, 0, 0], dtype=np.uint8)
    return frame


def pad_to_even_dimensions(rgb: np.ndarray) -> np.ndarray:
    height, width = rgb.shape[:2]
    pad_height = height % 2
    pad_width = width % 2
    if pad_height == 0 and pad_width == 0:
        return rgb
    return np.pad(rgb, ((0, pad_height), (0, pad_width), (0, 0)), mode="edge")


def review_frame(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    fitted_rgb = fit_to_square_canvas(rgb, size=REVIEW_FRAME_SIZE)
    fitted_mask = fit_to_square_canvas(mask.astype(np.uint8), size=REVIEW_FRAME_SIZE) > 0
    return overlay_contour(fitted_rgb, fitted_mask)


def roi_channel_frames(pos_dir: Path, index, roi: RoiCrop, *, channel: int) -> np.ndarray:
    stack = read_roi_stack(pos_dir / roi.file_name, roi.shape)
    frames = [
        np.asarray(
            roi_frame_2d(stack, index.axis_order, timepoint=timepoint, channel=channel),
            dtype=np.float64,
        )
        for timepoint in range(index.time_count)
    ]
    return np.stack(frames, axis=0)


def write_check_segment_video(
    *,
    output_dir: Path,
    position: int,
    pos_dir: Path,
    index,
    roi: RoiCrop,
    source_channel: int,
    mask_stack: np.ndarray,
    fps: float,
    force: bool,
) -> CheckSegmentVideo:
    validate_channel_index(index, source_channel)
    frames = roi_channel_frames(pos_dir, index, roi, channel=source_channel)

    output_path = default_video_path(output_dir, position=position, roi=roi, channel=source_channel)
    if output_path.exists() and not force:
        return CheckSegmentVideo(output_path=output_path, frame_count=index.time_count)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    low, high = _normalization_bounds(frames)
    with imageio.get_writer(output_path, fps=fps, codec="libx264", macro_block_size=1) as writer:
        for frame, mask in zip(frames, mask_stack, strict=True):
            rgb = normalize_frame_to_rgb8(frame, low=low, high=high)
            writer.append_data(pad_to_even_dimensions(review_frame(rgb, mask)))

    return CheckSegmentVideo(output_path=output_path, frame_count=index.time_count)


def _review_channels(mapping: SlideChannelMapping) -> list[int]:
    return sorted({mapping.mask_channel, mapping.signal_channel})


def run_check_segment(
    workspace: Path,
    *,
    sample: Path,
    output: Path | None = None,
    fps: float = 6.0,
    force: bool = False,
) -> list[CheckSegmentVideo]:
    if fps <= 0:
        raise ValueError(f"--fps must be > 0, got {fps}")

    workspace = workspace.resolve()
    output_dir = default_output_dir(workspace) if output is None else output.resolve()
    slide_mapping = load_slide_mapping(sample.resolve())
    videos: list[CheckSegmentVideo] = []
    for slide_channel, mapping in slide_mapping.items():
        for position in mapping.positions:
            pos_dir = position_dir(workspace, position)
            index = read_position_index(pos_dir)
            validate_channel_index(index, mapping.mask_channel)
            review_channels = _review_channels(mapping)
            for roi in index.rois:
                mask_reference_frames = roi_channel_frames(pos_dir, index, roi, channel=mapping.mask_channel)
                mask_path = default_mask_path(
                    workspace,
                    position=index.position,
                    slide_channel=slide_channel,
                    mask_channel=mapping.mask_channel,
                    roi_file_name=roi.file_name,
                )
                mask_stack = read_mask_stack(
                    mask_path,
                    time_count=index.time_count,
                    frame_shape=tuple(int(value) for value in mask_reference_frames[0].shape),
                )
                for channel in review_channels:
                    videos.append(
                        write_check_segment_video(
                            output_dir=output_dir,
                            position=position,
                            pos_dir=pos_dir,
                            index=index,
                            roi=roi,
                            source_channel=channel,
                            mask_stack=mask_stack,
                            fps=fps,
                            force=force,
                        )
                    )
    if not videos:
        raise ValueError("No check-segment videos produced")
    return videos
