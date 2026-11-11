import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sam3_semantic import (  # noqa: E402
    load_classes,
    merge_prompt_masks,
    write_cvat_export,
    zip_export,
)


class FakeTensor:
    def __init__(self, value):
        self.value = np.asarray(value)

    def cpu(self):
        return self

    def numpy(self):
        return self.value


def fake_result(mask, confidence):
    return SimpleNamespace(
        masks=SimpleNamespace(data=FakeTensor([mask])),
        boxes=SimpleNamespace(conf=FakeTensor([confidence])),
    )


class Sam3SemanticTests(unittest.TestCase):
    def test_merge_uses_highest_confidence_on_overlap(self):
        first = np.array([[1, 1], [0, 0]], dtype=np.float32)
        second = np.array([[1, 0], [1, 0]], dtype=np.float32)
        merged = merge_prompt_masks([fake_result(first, 0.4), fake_result(second, 0.8)], ["road", "sky"], (2, 2))
        np.testing.assert_array_equal(merged, [[1, 0], [1, 255]])

    def test_writes_cvat_color_png_and_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            classes_file = base / "classes.json"
            classes_file.write_text(json.dumps({"classes": ["road", "sky"], "colors": {"road": [1, 2, 3], "sky": [4, 5, 6]}}), encoding="utf-8")
            classes, colors = load_classes(classes_file)
            export = base / "export"
            write_cvat_export(export, {"scene.jpg": np.array([[0, 1], [255, 0]], dtype=np.uint8)}, classes, colors)
            pixels = np.asarray(Image.open(export / "SegmentationClass" / "scene.png"))
            np.testing.assert_array_equal(pixels[0, 0], [1, 2, 3])
            np.testing.assert_array_equal(pixels[0, 1], [4, 5, 6])
            self.assertIn("road:1,2,3::", (export / "labelmap.txt").read_text(encoding="utf-8"))
            archive_path = base / "scene.zip"
            zip_export(export, archive_path)
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(set(archive.namelist()), {"labelmap.txt", "SegmentationClass/scene.png"})


if __name__ == "__main__":
    unittest.main()
