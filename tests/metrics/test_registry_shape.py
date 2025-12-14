"""
Ensure every metric module under metrics self-registers.
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import Set

import metrics as metrics_pkg
from metrics.base import clear_registry_for_tests, registered


def _discover_metric_modules() -> Set[str]:
    """Find all top-level metric modules (skip private and 'base')."""
    names: Set[str] = set()
    for mod in pkgutil.iter_modules(metrics_pkg.__path__):
        if mod.name == "base" or mod.name.startswith("_"):
            continue
        names.add(mod.name)  # e.g., "bus_factor", "ramp_up_time"
    return names


def test_all_metrics_are_registered() -> None:
    """Every metric module must call register() at import time."""
    # Start clean so other tests can't mask missing registrations
    clear_registry_for_tests()

    # 1) discover metric modules
    metric_modules = _discover_metric_modules()
    assert metric_modules, "No metric modules found under swe_project.metrics/"

    # 2) import each module → triggers self-registration
    for name in sorted(metric_modules):
        importlib.import_module(f"{metrics_pkg.__name__}.{name}")

    # 3) collect registered output_field names
    registered_fields = {field for _, field, _ in registered()}

    # 4) require module name == NDJSON field (convention)
    missing = sorted(metric_modules - registered_fields)
    assert not missing, f"Unregistered metric modules: {missing}"
