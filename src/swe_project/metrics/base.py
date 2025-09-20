from __future__ import annotations
from typing import Any, Callable, List, Tuple, TypedDict

class MetricResult(TypedDict):
    value: Any                # float | dict[str, float]
    latency_ms: int

# (name, output_field, compute)
_REGISTRY: List[Tuple[str, str, Callable[[str], MetricResult]]] = []

def register(name: str, output_field: str, compute: Callable[[str], MetricResult]) -> None:
    _REGISTRY.append((name, output_field, compute))

def registered() -> List[Tuple[str, str, Callable[[str], MetricResult]]]:
    return list(_REGISTRY)
