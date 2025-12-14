"""
Reproducibility Metric

Evaluates whether the model can be run using only the demonstration code
included in the model card.

Scoring:
- 0.0: No code/doesn't run
- 0.5: Runs with debugging
- 1.0: Runs with no changes/debugging
"""
import os
import re
import time
from typing import Optional

from core.hf_client import download_snapshot, model_info
from metrics.base import register


def _check_code_in_readme(readme_content: str) -> bool:
    """Check if README contains code snippets."""
    # Look for common code block patterns
    code_patterns = [
        r'```python',
        r'```py',
        r'from transformers import',
        r'import torch',
        r'model = ',
        r'tokenizer = ',
    ]

    for pattern in code_patterns:
        if re.search(pattern, readme_content, re.IGNORECASE):
            return True
    return False


def _check_runnable_example(readme_content: str) -> bool:
    """Check if README has a complete runnable example."""
    # Look for more complete example patterns
    has_import = bool(re.search(r'(from|import)\s+\w+', readme_content))
    has_model_load = bool(re.search(r'(model|tokenizer)\s*=', readme_content, re.IGNORECASE))
    has_inference = bool(re.search(r'(predict|generate|forward|\(.*\))', readme_content))

    # Consider it runnable if it has imports, model loading, and some inference
    return has_import and has_model_load and has_inference


def _check_dependencies(local_path: str) -> bool:
    """Check if the model has dependency files."""
    dependency_files = [
        'requirements.txt',
        'setup.py',
        'pyproject.toml',
        'environment.yml',
        'Pipfile',
    ]

    for dep_file in dependency_files:
        if os.path.exists(os.path.join(local_path, dep_file)):
            return True
    return False


def compute(model_url: str) -> dict:
    """
    Compute reproducibility metric.

    Evaluates if demonstration code in the model card is runnable:
    - 1.0: Has runnable code examples with dependencies
    - 0.5: Has code examples but may need debugging
    - 0.0: No code examples or insufficient information

    Args:
        model_url: HuggingFace model URL

    Returns:
        dict: {"value": float, "latency_ms": int}
    """
    t0 = time.perf_counter()

    repo_id = model_url.replace("https://huggingface.co/", "").strip("/")
    score = 0.0

    try:
        # Download README and check for code examples
        local_path = download_snapshot(repo_id, allow_patterns=["README.md", "requirements.txt", "setup.py"])
        readme_file = os.path.join(local_path, "README.md")

        if os.path.exists(readme_file):
            with open(readme_file, "r", encoding="utf-8", errors="ignore") as f:
                readme_content = f.read()

            has_code = _check_code_in_readme(readme_content)
            has_runnable = _check_runnable_example(readme_content)
            has_deps = _check_dependencies(local_path)

            if has_runnable and has_deps:
                # Likely to run with minimal changes
                score = 1.0
            elif has_code or has_runnable:
                # Has code but may need debugging
                score = 0.5
            else:
                # No useful code examples
                score = 0.0
        else:
            # No README found
            score = 0.0

    except Exception:
        # If we can't download or analyze, assume not reproducible
        score = 0.0

    return {
        "value": score,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


# Register in the metrics registry
register("reproducibility", "reproducibility", compute)
