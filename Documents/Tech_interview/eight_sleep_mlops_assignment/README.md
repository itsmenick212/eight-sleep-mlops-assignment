# Eight Sleep MLOps Take‑Home Assignment

This repository contains a lightweight service and supporting scripts for the Eight Sleep MLOps take‑home assignment. The goal of the assignment is to build a service that ingests a high‑rate stream of JSON events, serves a PyTorch model for scoring each event, maintains a per‑user rolling median over the last five minutes, and exposes the results via an HTTP API. A synthetic event generator and a model creation script are included for testing.

## Contents

- `main.py` – FastAPI application implementing the ingestion API,
  per‑user state, rolling median calculation and statistics endpoints.
- `event_generator.py` – Script to generate a high‑throughput stream of synthetic events and post them to the ingestion endpoint.
- `create_model.py` – Script to create and save a small deterministic PyTorch model used for scoring events.
- `requirements.txt` – List of Python dependencies.
- `Dockerfile` – Definition for containerising the service.

## Quick Start (local)

The service requires Python 3.9+ and a few pip dependencies. The
following steps will get you up and running on a local machine:

```bash
# Create a virtual environment and activate it
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Generate the model file (inefficient_model.pt)
python create_model.py

# Start the service on port 8000
uvicorn main:app --host 0.0.0.0 --port 8000

> Note: the service expects an on-disk model file `inefficient_model.pt` containing a
> PyTorch **state_dict** (not a pickled model object). Run `python create_model.py`
> before starting the service or running the test suite to generate `inefficient_model.pt`.
```

Once running, you can access the service at `http://localhost:8000/`.

FastAPI automatically serves an OpenAPI specification and an
interactive Swagger UI at `/docs`.

### Endpoints

| Method | Path                       | Description                                                 |
|-------:|----------------------------|-------------------------------------------------------------|
| `POST` | `/ingest`                  | Accepts a JSON body with a list of events.  Each event
                                       should contain `user_id`, `timestamp` (UNIX epoch
                                       seconds) and `features` (a list of floats).  The
                                       endpoint runs the model on each event, updates the
                                       per‑user rolling window and returns the count of
                                       processed events.  Malformed events are skipped. |
| `GET`  | `/users/{user_id}/median`  | Returns the current rolling median of scores for the
                                       specified user.  If the user has no recent scores the
                                       median will be `null`. |
| `GET`  | `/stats`                   | Returns aggregate service statistics such as the number of
                                       ingestion requests, events processed, median requests and
                                       average ingestion latency. |

### Testing the Service

To simulate a realistic ingestion workload, run the synthetic event generator in another terminal:

```bash
python event_generator.py --help  # shows available options

# Example: send 5 000 events per second for 30 seconds
python event_generator.py
```

By default the generator posts to `http://localhost:8000/ingest` at 5,000 events per second for one minute.  You can adjust the target URL, rate, duration and number of users by passing arguments to the `run` function (see code in `event_generator.py`).  While the generator is running you can query medians and statistics via the service API.

## Docker Usage

The repository includes a simple `Dockerfile` for containerising the service. To build and run the service in Docker:

```bash
# From within the mlops_assignment directory
docker build -t mlops-service .

# Generate the model locally (inside the container at runtime or on the host)
python create_model.py

# Run the service container and expose port 8000
docker run --rm -p 8000:8000 mlops-service
```

Note: the `create_model.py` script must be executed (either on the host or during the image build) to ensure `inefficient_model.pt` is present in the container at runtime.  For simplicity this Dockerfile copies any existing model file from the build context.  See comments in `Dockerfile` for details.

## Design Overview

This implementation uses [FastAPI](https://fastapi.tiangolo.com/)
to provide asynchronous endpoints. The model is loaded once at
startup and executed in a thread pool for each event to avoid
blocking the event loop. Per‑user scores are stored in memory using
Python `deque` objects keyed by user ID.  Each time a new score is added the service prunes entries older than five minutes. When requesting a median the service extracts the current scores and
computes the median using Python's `statistics.median` function. A simple statistics dictionary tracks request counts and ingestion
latencies.

This design prioritises clarity and correctness over raw throughput.

Possible extensions are discussed in the accompanying write‑up.