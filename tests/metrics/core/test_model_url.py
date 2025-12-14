from __future__ import annotations

import pytest
from core.model_url import is_hf_model_url, to_repo_id

# ---------- to_repo_id ----------


def test_to_repo_id_parses_branch_tree():
    rid, br = to_repo_id("https://huggingface.co/org/name/tree/main")
    assert rid == "org/name" and br == "main"


def test_to_repo_id_parses_branch_resolve():
    rid, br = to_repo_id(
        "https://huggingface.co/org/name/resolve/dev/pytorch_model.bin"
    )
    assert rid == "org/name" and br == "dev"


def test_to_repo_id_plain_org_name():
    rid, br = to_repo_id("https://huggingface.co/org/name")
    assert rid == "org/name" and br is None


def test_to_repo_id_root_level_repo():
    rid, br = to_repo_id("https://huggingface.co/gpt2")
    assert rid == "gpt2" and br is None


def test_to_repo_id_accepts_bare_path():
    rid, br = to_repo_id("huggingface.co/org/name")
    assert rid == "org/name" and br is None


def test_to_repo_id_subdomain_enterprise_ok():
    rid, br = to_repo_id("https://aca.huggingface.co/org/name?foo=1")
    assert rid == "org/name" and br is None


def test_to_repo_id_non_hf_returns_original():
    url = "https://example.com/foo/bar"
    rid, br = to_repo_id(url)
    assert rid == url and br is None


def test_to_repo_id_empty_string_roundtrips():
    rid, br = to_repo_id("")
    assert rid == "" and br is None


# ---------- is_hf_model_url ----------


@pytest.mark.parametrize(
    "u",
    [
        "https://huggingface.co/gpt2",  # root-level model
        "https://huggingface.co/org/name",  # org/name
        "huggingface.co/org/name",  # bare path
        "https://sub.huggingface.co/org/name",  # enterprise subdomain
    ],
)
def test_is_hf_model_url_true(u):
    assert is_hf_model_url(u) is True


@pytest.mark.parametrize(
    "u",
    [
        "",  # empty
        "https://example.com/x",  # other host
        "https://huggingface.co/datasets/myds",  # blocked sections
        "https://huggingface.co/spaces/user/app",
        "https://huggingface.co/docs/transformers",
        "https://huggingface.co/models",
    ],
)
def test_is_hf_model_url_false(u):
    assert is_hf_model_url(u) is False
