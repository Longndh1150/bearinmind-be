#!bin/bash

python -m scripts.seed_units

# API (dev)
uvicorn app.main:app --host 0.0.0.0 --port $PORT