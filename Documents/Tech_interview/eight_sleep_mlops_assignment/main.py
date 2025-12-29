"""
Eight Sleep MLOps Take‑Home Assignment Service
================================================

This module implements a lightweight HTTP service capable of ingesting high‑rate streams of JSON events, running a PyTorch model to produce per‑event scores, maintaining a rolling median per user, and exposing results via a simple API. The service is implemented using FastAPI and is designed to be easy to understand and extend rather than optimized for maximum throughput. See the accompanying README for instructions on how to run the service and exercise it with the provided event generator.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from statistics import median
from typing import Any, Dict, List

import torch
from fastapi import FastAPI, HTTPException

# Initialize the FastAPI application
app = FastAPI(title="Eight Sleep MLOps Assignment Service")

# Attempt to load the provided PyTorch model state dict once at startup.
# We instantiate the same model class defined in `create_model.py` and
# load the saved `state_dict`. If the model file is missing the service
# will still start, but inference requests will raise an error.
try:
    from create_model import InefficientModel  # local model definition

    MODEL_PATH = "inefficient_model.pt"
    state = torch.load(MODEL_PATH)
    _loaded_model = InefficientModel()
    _loaded_model.load_state_dict(state)
    _loaded_model.eval()
except Exception as exc:
    # Model could not be loaded.  Log the exception to stderr and
    # proceed.  Inference will fail until the model file is present.
    print(f"Warning: could not load model from {MODEL_PATH}: {exc}")
    _loaded_model = None

# Per‑user data structure.  Each user ID maps to a deque of
# (timestamp, score) tuples.  A deque is used so that outdated
# entries can be removed efficiently from the left side.
user_scores: Dict[str, deque] = defaultdict(deque)

# Statistics for monitoring.  A simple dictionary protected by an
# asyncio.Lock allows concurrent update without race conditions.
stats: Dict[str, Any] = {
    "ingest_requests": 0,
    "events_processed": 0,
    "median_requests": 0,
    "ingest_latencies": [],  # List of floats in seconds
}
stats_lock = asyncio.Lock()

# Rolling window length in seconds (5 minutes)
ROLLING_WINDOW_SECONDS = 300


def _predict_sync(features: List[float]) -> float:
    """Synchronous helper to run the model inference for one feature vector.

    FastAPI will dispatch this function into a thread pool via
    loop.run_in_executor.  Using a synchronous helper avoids
    interfering with the asynchronous event loop while still
    benefiting from the Python GIL releasing during I/O and tensor
    operations.  If the model is not loaded, raises RuntimeError.

    Args:
        features: A list of floats representing the model input.

    Returns:
        A Python float containing the predicted score.
    """
    if _loaded_model is None:
        raise RuntimeError(
            "Model not loaded. Ensure inefficient_model.pt is present in the working directory."
        )
    # Convert to a 2D tensor of shape (1, len(features))
    x = torch.tensor([features], dtype=torch.float32)
    with torch.no_grad():
        output = _loaded_model(x).squeeze().item()
    return float(output)


async def _update_user_scores(user_id: str, timestamp: int, score: float) -> None:
    """Add a new score for the user and drop any entries older than the rolling window.

    Args:
        user_id: The unique identifier of the user.
        timestamp: The integer UNIX timestamp associated with the event.
        score: The score computed by the model for this event.
    """
    dq = user_scores[user_id]
    dq.append((timestamp, score))
    cutoff = timestamp - ROLLING_WINDOW_SECONDS
    # Prune outdated entries
    while dq and dq[0][0] < cutoff:
        dq.popleft()


@app.post("/ingest")
async def ingest(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ingest a batch of events and run inference.

    The endpoint accepts a JSON body containing an "events" key
    mapping to a list of event objects.  Each event should contain
    "user_id", "timestamp", and "features" fields.  The service
    computes a score for each event using the provided PyTorch model,
    updates the per‑user rolling window, and returns the number of
    events processed.  Malformed events (missing fields) are skipped.

    Example request body:

        {
          "events": [
            {"user_id": "user-1", "timestamp": 1700000000, "features": [0.1, 0.2, 0.3]},
            ...
          ]
        }

    Returns:
        A dictionary with a single key "processed" indicating how many
        events were successfully processed.
    """
    start_time = time.perf_counter()

    events = payload.get("events")
    if events is None:
        raise HTTPException(status_code=400, detail="Missing 'events' in request body")

    async with stats_lock:
        stats["ingest_requests"] += 1

    loop = asyncio.get_event_loop()
    processed_count = 0
    for event in events:
        user_id = event.get("user_id")
        ts = event.get("timestamp")
        features = event.get("features")
        if user_id is None or ts is None or features is None:
            # Skip invalid events
            continue
        # Dispatch synchronous model inference to a worker thread
        try:
            score = await loop.run_in_executor(None, _predict_sync, features)
        except Exception as exc:
            # Log or handle inference errors.  For this assignment we skip on failure.
            continue
        # Update per‑user rolling data
        await _update_user_scores(user_id, int(ts), float(score))
        processed_count += 1

    duration = time.perf_counter() - start_time
    async with stats_lock:
        stats["events_processed"] += processed_count
        stats["ingest_latencies"].append(duration)
    return {"processed": processed_count}


@app.get("/users/{user_id}/median")
async def get_user_median(user_id: str) -> Dict[str, Any]:
    """Return the current rolling median score for the specified user.

    If the user has no recorded scores within the rolling window the
    returned median will be null (None in Python).  The median is
    computed using Python's statistics.median on the list of current
    scores.
    """
    async with stats_lock:
        stats["median_requests"] += 1
    dq = user_scores.get(user_id)
    if not dq:
        return {"median": None}
    scores = [val for _, val in dq]
    return {"median": median(scores)}


@app.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """Return aggregate service statistics.

    The returned dictionary contains counts of ingestion and median
    requests, the total number of events processed, and the average
    latency per ingestion request.
    """
    async with stats_lock:
        latencies = stats["ingest_latencies"]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        return {
            "ingest_requests": stats["ingest_requests"],
            "events_processed": stats["events_processed"],
            "median_requests": stats["median_requests"],
            "avg_ingest_latency_seconds": avg_latency,
        }


@app.get("/")
async def root() -> Dict[str, str]:
    """Health check endpoint for convenience."""
    return {"message": "Eight Sleep MLOps Assignment Service is running"}