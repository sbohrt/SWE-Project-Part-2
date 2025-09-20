from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Tuple, Any

EXEC = ThreadPoolExecutor(max_workers=8)

def run_parallel(tasks: List[Tuple[str, Callable[[], Any]]], timeout_s: int = 60) -> Dict[str, Any]:
    """
    tasks: list of (key, fn). Returns {key: fn_result_or_default}.
    Any exception → {"value": 0.0, "latency_ms": 0}.
    """
    futs = {EXEC.submit(fn): key for key, fn in tasks}
    out: Dict[str, Any] = {}
    for fut in as_completed(futs, timeout=timeout_s):
        key = futs[fut]
        try:
            out[key] = fut.result()
        except Exception:
            out[key] = {"value": 0.0, "latency_ms": 0}
    # fill any timeouts/missed
    for key, _ in tasks:
        out.setdefault(key, {"value": 0.0, "latency_ms": 0})
    return out
