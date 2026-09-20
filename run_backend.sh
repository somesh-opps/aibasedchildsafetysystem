#!/bin/bash
source .venv/bin/activate
export HARDWARE_MODE=mock
uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
