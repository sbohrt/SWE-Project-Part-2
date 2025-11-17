# src/swe_project/lineage_extract.py
from __future__ import annotations

from typing import Dict, List


def extract_parent_models(config: Dict) -> List[str]:
    """
    Extract parent model repo IDs from a Hugging Face config.json dict.

    This only uses structured fields, as required by the assignment.
    We do NOT try to parse free-form text like 'model_description'.

    Common patterns:
      - base_model_name_or_path: "bert-base-uncased" or "org/model-name"
      - (optional) model_base: some libraries use this

    Returns:
        A list of repo_id strings as they appear in config, e.g.:
          ["bert-base-uncased", "organization/model-name"]
    """
    parents: list[str] = []

    # 1) Most common HF lineage field (used widely in PEFT / fine-tunes)
    base = config.get("base_model_name_or_path")
    if isinstance(base, str) and base.strip():
        parents.append(base.strip())

    # 2) Optional alternative key some configs may use
    alt = config.get("model_base")
    if isinstance(alt, str) and alt.strip() and alt.strip() not in parents:
        parents.append(alt.strip())

    # You can extend this if you discover more structured lineage fields.
    # e.g.:
    # other = config.get("parent_model_name")
    # ...

    return parents
