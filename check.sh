#!/usr/bin/env bash
# Installs the test dependencies and runs the full suite with the coverage gate.
set -euo pipefail

pip install -q pytest pytest-cov
python -m pytest -q --cov=boltons --cov-fail-under=85 "$@"
