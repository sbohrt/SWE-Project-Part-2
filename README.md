# SWE Project: A CLI for Trustworthy Model Re-Use

This project is a command-line interface (CLI) developed for ACME Corporation to help service engineering teams evaluate and choose trustworthy, pre-trained AI/ML models from open-source ecosystems like Hugging Face.

The tool analyzes model repositories from various URLs (Hugging Face, GitHub) and calculates a series of quality and trustworthiness metrics. It outputs a final weighted **Net Score** for each model, allowing engineers to quickly assess suitability for re-use in ACME’s products (licensed under LGPL-2.1).

## Features & Metrics

The CLI evaluates models based on several key metrics, which are combined to produce a final **Net Score**.

- **📈 Performance Claims** — Checks the model card for a `model-index` with benchmark results and nudges scores with download/like counts.  
- **⚖️ License** — Verifies compatibility with ACME’s OSS policies (LGPL-2.1). Examples: compatible (Apache-2.0, MIT), incompatible (GPL-3.0), or unclear.  
- **⏱️ Ramp-Up Time** — Uses an LLM to score the README’s clarity/completeness to estimate effort to get started.  
- **🚌 Bus Factor** — Measures concentration of knowledge among top contributors over the last year.  
- **💻 Code Quality** — Looks for dependency files (e.g., `requirements.txt`, `pyproject.toml`) and the proportion of Python files.  
- **📦 Dataset & Code Availability** — Detects links to datasets, source code, and demos (Hugging Face Spaces).  
- **📊 Dataset Quality** — Considers dataset documentation, download counts, multiple configs, and presence of a data viewer.  
- **📏 Size Score** — Sums model weight files (`.bin`, `.safetensors`, etc.) and returns scores by device target:
  - `raspberry_pi`
  - `jetson_nano`
  - `desktop_pc`
  - `aws_server`

## How the Net Score Is Calculated

The overall Net Score is a weighted sum of the individual metrics. Weights are defined in `scoring.py` and can be adjusted.

**Default weights**

| Metric                | Weight |
|-----------------------|--------|
| Performance Claims    | 0.15   |
| Dataset & Code Score  | 0.15   |
| Dataset Quality       | 0.15   |
| Ramp-Up Time          | 0.15   |
| Bus Factor            | 0.10   |
| License               | 0.10   |
| Size Score            | 0.10   |
| Code Quality          | 0.10   |

## Getting Started

### Prerequisites

- Python 3.x  
- Environment variable `GITHUB_TOKEN` containing a valid GitHub Personal Access Token for API requests.

### Installation

From the repository root:

```bash
./run install
```

This installs all required packages into your user environment.

## Usage

### Running the Analysis

Provide a newline-delimited text file of URLs (Hugging Face models/datasets or GitHub repositories), then run:

```bash
./run /path/to/your/url_file.txt
```

The program prints NDJSON to stdout. Each line is a JSON object with the calculated scores and latencies for one model.

### Running Tests

```bash
./run test
```

The output reports tests passed and overall line coverage. The suite requires **≥ 80%** coverage to pass.

### Logging

Logging is controlled by environment variables:

```text
LOG_FILE  = absolute path to the log file
LOG_LEVEL = 0|1|2   (0 = silent [default], 1 = info, 2 = debug)
```

> **Note:** You may need to create and activate a virtual environment before running the program.
