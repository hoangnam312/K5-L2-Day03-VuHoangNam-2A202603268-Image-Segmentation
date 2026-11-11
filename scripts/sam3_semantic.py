"""Run local SAM 3 text prompts and write a CVAT semantic-mask export.

The SAM 3 dependency is imported lazily so the repository's normal scoring
tools remain usable without installing the model runtime or downloading a
checkpoint.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image

IGNORE = 255
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def load_classes(path: Path) -> tuple[list[str], dict[str, tuple[int, int, int]]]:
    """Load class order and CVAT colors from a task ``classes.json`` file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    classes = data.get("classes")
    colors = data.get("colors", {})
    if not isinstance(classes, list) or not classes or not all(isinstance(x, str) and x for x in classes):
        raise ValueError("classes.json phải có danh sách classes không rỗng")
    if len(set(classes)) != len(classes):
        raise ValueError("classes.json có class bị trùng")

    parsed: dict[str, tuple[int, int, int]] = {}
    for name in classes:
        rgb = colors.get(name)
        if not isinstance(rgb, list) or len(rgb) != 3 or any(not isinstance(v, int) or not 0 <= v <= 255 for v in rgb):
            raise ValueError(f"class {name!r} thiếu màu RGB hợp lệ trong classes.json")
        parsed[name] = tuple(rgb)
    return classes, parsed


def image_files(directory: Path) -> list[Path]:
    """Return supported images in deterministic filename order."""
    if not directory.is_dir():
        raise ValueError(f"không tìm thấy thư mục ảnh: {directory}")
    files = sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)
    if not files:
        raise ValueError(f"không có ảnh JPG/PNG phù hợp trong: {directory}")
    return files


def _numpy(value: Any) -> np.ndarray:
    """Convert torch/numpy-like values returned by Ultralytics to numpy."""
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    return np.asarray(value)


def _first_result(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def extract_masks(result: Any, image_shape: tuple[int, int]) -> list[tuple[np.ndarray, float]]:
    """Extract binary masks and confidence scores from one Ultralytics result."""
    result = _first_result(result)
    masks_obj = getattr(result, "masks", None)
    if result is None or masks_obj is None or getattr(masks_obj, "data", None) is None:
        return []
    masks = _numpy(masks_obj.data)
    if masks.ndim == 2:
        masks = masks[None, ...]
    if masks.ndim != 3:
        raise ValueError(f"SAM 3 trả về masks có shape không hỗ trợ: {masks.shape}")

    boxes = getattr(result, "boxes", None)
    confidence = _numpy(getattr(boxes, "conf", np.ones(len(masks), dtype=np.float32))).reshape(-1) if boxes is not None else np.ones(len(masks), dtype=np.float32)
    if len(confidence) == 1 and len(masks) > 1:
        confidence = np.repeat(confidence, len(masks))
    if len(confidence) != len(masks):
        confidence = np.ones(len(masks), dtype=np.float32)

    height, width = image_shape
    extracted = []
    for mask, score in zip(masks, confidence):
        if mask.shape != (height, width):
            mask = np.asarray(Image.fromarray(mask.astype(np.float32)).resize((width, height), Image.Resampling.NEAREST))
        extracted.append((mask > 0.5, float(score)))
    return extracted


def merge_prompt_masks(prompt_results: Iterable[Any], classes: list[str], image_shape: tuple[int, int]) -> np.ndarray:
    """Merge per-class SAM results; the highest-confidence mask wins per pixel."""
    height, width = image_shape
    labels = np.full((height, width), IGNORE, dtype=np.uint8)
    best_score = np.full((height, width), -np.inf, dtype=np.float32)
    for class_id, result in enumerate(prompt_results):
        for mask, score in extract_masks(result, image_shape):
            update = mask & (score > best_score)
            labels[update] = class_id
            best_score[update] = score
    return labels


def write_cvat_export(output_dir: Path, labels_by_image: dict[str, np.ndarray], classes: list[str], colors: dict[str, tuple[int, int, int]]) -> None:
    """Write the CVAT Segmentation mask 1.1 directory layout."""
    segmentation_dir = output_dir / "SegmentationClass"
    segmentation_dir.mkdir(parents=True, exist_ok=True)
    labelmap = "".join(f"{name}:{','.join(map(str, colors[name]))}::\n" for name in classes)
    (output_dir / "labelmap.txt").write_text(labelmap, encoding="utf-8")

    palette = np.zeros((len(classes), 3), dtype=np.uint8)
    for index, name in enumerate(classes):
        palette[index] = colors[name]
    for filename, labels in labels_by_image.items():
        if labels.ndim != 2:
            raise ValueError(f"label map của {filename} phải là ma trận 2D")
        rgb = np.zeros((*labels.shape, 3), dtype=np.uint8)
        valid = labels < len(classes)
        rgb[valid] = palette[labels[valid]]
        Image.fromarray(rgb, mode="RGB").save(segmentation_dir / f"{Path(filename).stem}.png")


def zip_export(source_dir: Path, output_zip: Path) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir).as_posix())


def build_predictor(model: Path, conf: float, device: str):
    try:
        from ultralytics.models.sam import SAM3SemanticPredictor
    except ImportError as exc:
        raise RuntimeError("chưa cài SAM 3 runtime; chạy: python -m pip install -r requirements-sam3.txt") from exc
    overrides = {"model": str(model), "task": "segment", "mode": "predict", "conf": conf, "save": False}
    if device != "auto":
        overrides["device"] = device
    return SAM3SemanticPredictor(overrides=overrides)


def run(images: list[Path], classes: list[str], predictor: Any) -> dict[str, np.ndarray]:
    labels_by_image: dict[str, np.ndarray] = {}
    for image in images:
        with Image.open(image) as opened:
            shape = (opened.height, opened.width)
        predictor.set_image(str(image))
        results = [predictor(text=[class_name]) for class_name in classes]
        labels_by_image[image.name] = merge_prompt_masks(results, classes, shape)
    return labels_by_image


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True, help="đường dẫn checkpoint sam3.pt")
    parser.add_argument("--images", type=Path, required=True, help="thư mục ảnh input")
    parser.add_argument("--classes", type=Path, required=True, help="classes.json của task semantic")
    parser.add_argument("--output", type=Path, required=True, help="thư mục output hoặc file .zip")
    parser.add_argument("--device", default="auto", help="auto, cpu hoặc CUDA device (ví dụ 0)")
    parser.add_argument("--conf", type=float, default=0.25, help="confidence threshold (mặc định: 0.25)")
    args = parser.parse_args(argv)
    if not args.model.is_file():
        parser.error(f"không tìm thấy checkpoint: {args.model}")
    if not 0 <= args.conf <= 1:
        parser.error("--conf phải nằm trong khoảng 0..1")

    classes, colors = load_classes(args.classes)
    images = image_files(args.images)
    predictor = build_predictor(args.model, args.conf, args.device)
    labels = run(images, classes, predictor)

    if args.output.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory(prefix="sam3-cvat-") as temporary:
            directory = Path(temporary)
            write_cvat_export(directory, labels, classes, colors)
            zip_export(directory, args.output)
    else:
        write_cvat_export(args.output, labels, classes, colors)
    print(f"Đã tạo {len(labels)} semantic mask: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
