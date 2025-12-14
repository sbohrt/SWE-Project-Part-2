from __future__ import annotations

import os
from typing import Iterable

_DEFAULT_EXTS = (".safetensors", ".bin", ".onnx", ".tflite", ".h5", ".pt")


def total_weight_bytes(root: str, exts: Iterable[str] = _DEFAULT_EXTS) -> int:
    exts = tuple(e.lower() for e in exts)
    total = 0
    for d, _, files in os.walk(root):
        for f in files:
            if f.lower().endswith(exts):
                total += os.path.getsize(os.path.join(d, f))
    return total
