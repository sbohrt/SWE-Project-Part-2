from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Dict, Optional


@dataclass(frozen=True)
class Triplet:
    model: str
    code: Optional[str] = None
    dataset: Optional[str] = None


_MODEL_TO_CTX: Dict[str, Triplet] = {}
_LOCK = RLock()


def clear() -> None:
    with _LOCK:
        _MODEL_TO_CTX.clear()


def set_context(
    model_url: str, code_url: Optional[str], dataset_url: Optional[str]
) -> None:
    with _LOCK:
        _MODEL_TO_CTX[model_url] = Triplet(
            model=model_url,
            code=(code_url or None),
            dataset=(dataset_url or None),
        )


def get_code_url(model_url: str) -> Optional[str]:
    with _LOCK:
        t = _MODEL_TO_CTX.get(model_url)
        return t.code if t else None


def get_dataset_url(model_url: str) -> Optional[str]:
    with _LOCK:
        t = _MODEL_TO_CTX.get(model_url)
        return t.dataset if t else None
