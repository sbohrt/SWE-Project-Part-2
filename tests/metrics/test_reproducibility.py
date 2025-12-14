"""
Tests for the reproducibility metric.

The reproducibility metric evaluates whether a model can be run using
demonstration code in the model card.

Scoring:
- 1.0: Has runnable code examples with dependencies
- 0.5: Has code examples but may need debugging
- 0.0: No code examples or insufficient information
"""
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def mock_download_snapshot():
    """Mock download_snapshot to return a temp directory with test files."""
    with patch('metrics.reproducibility.download_snapshot') as mock:
        yield mock


@pytest.fixture
def mock_model_info():
    """Mock model_info to return test model metadata."""
    with patch('metrics.reproducibility.model_info') as mock:
        yield mock


def test_reproducibility_perfect_score(mock_download_snapshot):
    """Test model with complete runnable example and dependencies."""
    from metrics.reproducibility import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create README with complete example
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("""
# My Model

## Usage

```python
from transformers import AutoModel, AutoTokenizer
import torch

model = AutoModel.from_pretrained("bert-base-uncased")
tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")

inputs = tokenizer("Hello, world!", return_tensors="pt")
outputs = model(**inputs)
```
""")

        # Create requirements.txt
        req_path = os.path.join(tmpdir, "requirements.txt")
        with open(req_path, "w") as f:
            f.write("transformers>=4.0.0\ntorch>=1.9.0\n")

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/bert-base-uncased")

        assert result["value"] == 1.0
        assert "latency_ms" in result
        assert result["latency_ms"] >= 0


def test_reproducibility_partial_score(mock_download_snapshot):
    """Test model with code but no dependencies."""
    from metrics.reproducibility import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create README with code but no dependencies
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("""
# My Model

Some model description.

```python
from transformers import AutoModel
model = AutoModel.from_pretrained("model-name")
```
""")

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        assert result["value"] == 0.5
        assert "latency_ms" in result


def test_reproducibility_incomplete_code(mock_download_snapshot):
    """Test model with incomplete code snippets."""
    from metrics.reproducibility import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("""
# My Model

Just some basic imports:

```python
import torch
```
""")

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        # Incomplete example should get 0.0 or 0.5
        assert result["value"] in [0.0, 0.5]


def test_reproducibility_no_code(mock_download_snapshot):
    """Test model with no code examples."""
    from metrics.reproducibility import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("""
# My Model

This is a great model for NLP tasks.

## Details

- Architecture: Transformer
- Parameters: 110M
""")

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        assert result["value"] == 0.0


def test_reproducibility_no_readme(mock_download_snapshot):
    """Test model with no README file."""
    from metrics.reproducibility import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        # No README created
        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        assert result["value"] == 0.0


def test_reproducibility_with_setup_py(mock_download_snapshot):
    """Test model with setup.py instead of requirements.txt."""
    from metrics.reproducibility import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("""
```python
from transformers import pipeline
model = pipeline("text-classification", model="my-model")
result = model("This is great!")
```
""")

        # Create setup.py
        setup_path = os.path.join(tmpdir, "setup.py")
        with open(setup_path, "w") as f:
            f.write("from setuptools import setup\nsetup(name='my-model')")

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        assert result["value"] == 1.0


def test_reproducibility_with_pyproject_toml(mock_download_snapshot):
    """Test model with pyproject.toml."""
    from metrics.reproducibility import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("""
```python
import torch
from transformers import AutoModel

model = AutoModel.from_pretrained("bert-base")
output = model(torch.randn(1, 512))
```
""")

        # Create pyproject.toml
        pyproject_path = os.path.join(tmpdir, "pyproject.toml")
        with open(pyproject_path, "w") as f:
            f.write("[tool.poetry]\nname = 'my-model'\n")

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        assert result["value"] == 1.0


def test_reproducibility_error_handling(mock_download_snapshot):
    """Test error handling when download fails."""
    from metrics.reproducibility import compute

    # Make download_snapshot raise an exception
    mock_download_snapshot.side_effect = Exception("Download failed")

    result = compute("https://huggingface.co/my-model")

    # Should return 0.0 on error
    assert result["value"] == 0.0
    assert "latency_ms" in result


def test_reproducibility_py_code_block(mock_download_snapshot):
    """Test detection of ```py code blocks."""
    from metrics.reproducibility import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("""
```py
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
```
""")

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        # Should detect code even with ```py
        assert result["value"] >= 0.5


def test_reproducibility_latency_measurement(mock_download_snapshot):
    """Test that latency is properly measured."""
    from metrics.reproducibility import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("# Model with no code")

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        assert "latency_ms" in result
        assert isinstance(result["latency_ms"], int)
        assert result["latency_ms"] >= 0
