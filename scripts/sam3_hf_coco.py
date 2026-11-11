"""Run Hugging Face SAM3 and create a CVAT-compatible COCO ZIP.

The model is downloaded by Transformers into the Hugging Face cache. In
Colab, set HF_HOME/HF_HUB_CACHE to a mounted Google Drive before running this
script so the checkpoint survives runtime resets.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def load_task(path: Path) -> tuple[str, list[str], list[str], dict[str, list[int]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    classes = data["classes"]
    task_type = data.get("type", "instance")
    stuff = data.get("stuff", [])
    colors = data.get("colors", {})
    if not isinstance(classes, list) or not classes:
        raise ValueError("classes.json phải có classes không rỗng")
    if any(not isinstance(name, str) or not name for name in classes):
        raise ValueError("class name không hợp lệ")
    return task_type, classes, stuff, colors


def image_files(directory: Path) -> list[Path]:
    files = sorted(p for p in directory.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not files:
        raise ValueError(f"Không có ảnh trong {directory}")
    return files


def rle_encode(mask: np.ndarray) -> dict[str, Any]:
    from pycocotools import mask as mask_utils

    encoded = mask_utils.encode(np.asfortranarray(mask.astype(np.uint8)))
    encoded["counts"] = encoded["counts"].decode("ascii")
    return encoded


def mask_area(mask: np.ndarray) -> int:
    return int(mask.astype(np.uint8).sum())


def run_prediction(model: Any, processor: Any, image: Image.Image, prompt: str, device: str, threshold: float) -> list[tuple[np.ndarray, float]]:
    import torch

    inputs = processor(images=image, text=prompt, return_tensors="pt").to(device)
    with torch.inference_mode():
        outputs = model(**inputs)
    result = processor.post_process_instance_segmentation(
        outputs,
        threshold=threshold,
        mask_threshold=0.5,
        target_sizes=inputs["original_sizes"].tolist(),
    )[0]
    masks = result.get("masks", [])
    scores = result.get("scores", [])
    if hasattr(masks, "detach"):
        masks = masks.detach().cpu().numpy()
    else:
        masks = np.asarray(masks)
    if hasattr(scores, "detach"):
        scores = scores.detach().cpu().numpy()
    else:
        scores = np.asarray(scores)
    return [(mask.astype(bool), float(score)) for mask, score in zip(masks, scores)]


def build_coco(images: list[Path], classes: list[str], stuff: list[str], model: Any, processor: Any, device: str, threshold: float, panoptic: bool) -> dict[str, Any]:
    categories = [{"id": index + 1, "name": name} for index, name in enumerate(classes)]
    category_id = {name: index + 1 for index, name in enumerate(classes)}
    coco_images, annotations = [], []
    annotation_id = 1

    for image_id, image_path in enumerate(images, start=1):
        with Image.open(image_path) as opened:
            image = opened.convert("RGB")
            width, height = image.size
        coco_images.append({"id": image_id, "file_name": image_path.name, "width": width, "height": height})

        # Keep all thing masks as separate COCO annotations. For stuff, merge
        # overlapping predictions into one highest-score-per-pixel mask.
        stuff_best = {name: np.full((height, width), -np.inf, dtype=np.float32) for name in stuff}
        stuff_masks = {name: np.zeros((height, width), dtype=bool) for name in stuff}
        for class_name in classes:
            predictions = run_prediction(model, processor, image, class_name, device, threshold)
            if class_name in stuff and panoptic:
                for mask, score in predictions:
                    update = mask & (score > stuff_best[class_name])
                    stuff_masks[class_name][update] = True
                    stuff_best[class_name][update] = score
                continue
            for mask, score in predictions:
                area = mask_area(mask)
                if area == 0:
                    continue
                ys, xs = np.where(mask)
                annotations.append({
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": category_id[class_name],
                    "segmentation": rle_encode(mask),
                    "area": area,
                    "bbox": [int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)],
                    "iscrowd": 0,
                    "score": score,
                })
                annotation_id += 1
        if panoptic:
            for class_name, mask in stuff_masks.items():
                area = mask_area(mask)
                if area == 0:
                    continue
                ys, xs = np.where(mask)
                annotations.append({
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": category_id[class_name],
                    "segmentation": rle_encode(mask),
                    "area": area,
                    "bbox": [int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)],
                    "iscrowd": 0,
                })
                annotation_id += 1
    return {"info": {"description": "SAM3 Hugging Face suggestions"}, "images": coco_images, "categories": categories, "annotations": annotations}


def write_semantic_zip(output: Path, images: list[Path], classes: list[str], colors: dict[str, list[int]], model: Any, processor: Any, device: str, threshold: float) -> None:
    """Create CVAT Segmentation mask 1.1 from HF instance predictions."""
    labels_by_image = {}
    for image_path in images:
        with Image.open(image_path) as opened:
            image = opened.convert("RGB")
            width, height = image.size
        labels = np.full((height, width), 255, dtype=np.uint8)
        best = np.full((height, width), -np.inf, dtype=np.float32)
        for class_id, class_name in enumerate(classes):
            for mask, score in run_prediction(model, processor, image, class_name, device, threshold):
                update = mask & (score > best)
                labels[update] = class_id
                best[update] = score
        labels_by_image[image_path] = labels

    with tempfile.TemporaryDirectory(prefix="sam3-hf-semantic-") as temp:
        root = Path(temp)
        seg_dir = root / "SegmentationClass"
        seg_dir.mkdir()
        labelmap = "".join(f"{name}:{','.join(map(str, colors[name]))}::\n" for name in classes)
        (root / "labelmap.txt").write_text(labelmap, encoding="utf-8")
        palette = np.array([colors[name] for name in classes], dtype=np.uint8)
        for image_path, labels in labels_by_image.items():
            rgb = np.zeros((*labels.shape, 3), dtype=np.uint8)
            valid = labels < len(classes)
            rgb[valid] = palette[labels[valid]]
            Image.fromarray(rgb, mode="RGB").save(seg_dir / f"{image_path.stem}.png")
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", default="facebook/sam3")
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--classes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--threshold", type=float, default=0.25)
    parser.add_argument("--panoptic", action="store_true")
    parser.add_argument("--format", choices=("auto", "semantic", "coco"), default="auto")
    args = parser.parse_args()
    if not 0 <= args.threshold <= 1:
        parser.error("--threshold phải trong khoảng 0..1")

    import torch
    from transformers import Sam3Model, Sam3Processor

    device = args.device if args.device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.float16 if device.startswith("cuda") else torch.float32
    processor = Sam3Processor.from_pretrained(args.model_id)
    model = Sam3Model.from_pretrained(args.model_id, torch_dtype=dtype).to(device)
    task_type, classes, stuff, colors = load_task(args.classes)
    images = image_files(args.images)
    output_format = task_type if args.format == "auto" else args.format
    if output_format == "semantic":
        if not colors or any(name not in colors for name in classes):
            raise ValueError("semantic classes.json phải có colors cho mọi class")
        write_semantic_zip(args.output, images, classes, colors, model, processor, device, args.threshold)
        print(f"Đã tạo {len(images)} semantic mask: {args.output}")
        return 0
    coco = build_coco(images, classes, stuff, model, processor, device, args.threshold, args.panoptic)

    with tempfile.TemporaryDirectory(prefix="sam3-hf-cvat-") as temp:
        root = Path(temp)
        annotation_dir = root / "annotations"
        annotation_dir.mkdir()
        (annotation_dir / "instances_default.json").write_text(json.dumps(coco, ensure_ascii=False), encoding="utf-8")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(annotation_dir / "instances_default.json", "annotations/instances_default.json")
    print(f"Đã tạo {len(coco['annotations'])} annotation: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
