# Tests

## Setup

Install dev dependencies:

```bash
pip install ".[dev]"
```

## Run the test suite

```bash
pytest
```

## Run by marker

```bash
pytest -m unit
pytest -m contract
pytest -m e2e
```

## Notes

All tests use pytest-provided `tmp_path` and do not write outputs into the repository `artifacts/` or `tmp/` directories.
