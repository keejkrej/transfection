from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile

def workspace_mask_dir(workspace: Path) -> Path:
    return workspace.resolve() / "mask"


def position_mask_dir(workspace: Path, pos: int) -> Path:
    return workspace_mask_dir(workspace) / f"Pos{pos}"


def default_mask_path(
    workspace: Path,
    *,
    position: int,
    slide_channel: int,
    mask_channel: int,
    roi_file_name: str,
) -> Path:
    return (position_mask_dir(workspace, position) / Path(roi_file_name).name).resolve()


def read_mask_stack(mask_path: Path, *, time_count: int, frame_shape: tuple[int, int]) -> np.ndarray:
    if not mask_path.is_file():
        raise ValueError(f"Missing mask TIFF: {mask_path}. Run transfection segment first.")

    raw_mask = np.asarray(tifffile.imread(mask_path))
    if raw_mask.ndim == 2 and time_count == 1:
        raw_mask = raw_mask[np.newaxis, :, :]
    if raw_mask.shape != (time_count, *frame_shape):
        raise ValueError(
            f"{mask_path} shape mismatch: expected {(time_count, *frame_shape)}, got {raw_mask.shape}"
        )
    return raw_mask > 0

