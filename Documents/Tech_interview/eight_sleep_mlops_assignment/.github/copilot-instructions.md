<!-- Copilot / AI contributor guidance for the Eight Sleep MLOps assignment -->
# Copilot instructions — Eight Sleep MLOps Assignment

This project is a compact FastAPI service that ingests JSON event batches, runs a PyTorch model per event, maintains a per-user rolling median (last 5 minutes), and exposes simple HTTP endpoints for querying medians and service stats.

Key files
- `main.py` — service implementation (endpoints, in-memory state, model loading).  See constants: `ROLLING_WINDOW_SECONDS = 300`, `_predict_sync` (runs model), `ingest` (`POST /ingest`), `GET /users/{user_id}/median`, `GET /stats`.
- `create_model.py` — produces `inefficient_model.pt` (CPU PyTorch model expected by `main.py`).
- `event_generator.py` — synthetic load generator that posts batches to `/ingest` (default: 5000 RPS, batch_size=10).
- `Dockerfile` — builds container; note `create_model.py` is executed at build time in this Dockerfile.
- `requirements.txt` — `fastapi`, `uvicorn[standard]`, `torch`, `requests`.

Important architecture & conventions (actionable)
- Model lifecycle: loaded at startup via `torch.load("inefficient_model.pt")`; if missing the app starts but inference raises `RuntimeError`. Ensure `inefficient_model.pt` exists for local runs and CI. Prefer `create_model.py` to regenerate the model.
- Inference pattern: CPU synchronous predict helper `_predict_sync` is dispatched using `loop.run_in_executor()` from the async endpoints. When changing inference behaviour (batching, GPU, async inference), update this pattern and ensure the event loop is not blocked.
- State & rolling window: per-user `collections.deque` stores `(timestamp, score)` pairs keyed by `user_id` in `user_scores`. The service prunes entries with `timestamp < current_ts - ROLLING_WINDOW_SECONDS`. Keep this in-memory assumption in mind when adding persistence/sharding.
- Error handling & inputs: malformed events (missing `user_id`, `timestamp`, or `features`) are silently skipped. Tests and changes that alter this behaviour should update `README.md` and document rationale.
- Metrics: `stats` dictionary (protected by `asyncio.Lock`) tracks `ingest_requests`, `events_processed`, `median_requests`, and `ingest_latencies` (list). The `/stats` endpoint returns the average ingestion latency under `avg_ingest_latency_seconds`.

Testing & common commands
- Local dev: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` then `python create_model.py` and `uvicorn main:app --host 0.0.0.0 --port 8000`.
- Exercise ingestion: run `python event_generator.py` (adjust `run` args in file for custom RPS, duration, users) and query `GET /users/<user>/median` and `GET /stats` while generator runs.
- Docker: `docker build -t mlops-service .` then `docker run --rm -p 8000:8000 mlops-service` (note Dockerfile already runs `create_model.py`).

Advice for code changes (concise, specific)
- Adding batching: implement a batch inference path in `_predict_sync` (or create `_predict_batch`) and change `ingest` to group events before dispatching to the executor. Update `stats` to include batch sizes and throughput.
- Handling out-of-order events: update `_update_user_scores` to insert events in timestamp order or buffer/reconcile; document how late events are handled and add tests using non-monotonic timestamps.
- Persisting state: replace `user_scores` with a Redis/ZK-backed store or a background flusher; ensure median computation remains consistent (consider using approximate medians for large cardinalities).
- Tests: add unit tests around `ingest` (valid vs malformed events), `_predict_sync` (requires test fixture for `inefficient_model.pt`), rolling window pruning and `/users/{user_id}/median` behaviour.

Do not change without noting in PR
- API shapes (`/ingest` payload and `/users/{user_id}/median` response) are small, explicit, and used by `event_generator.py`; preserve their contracts or include migration notes in the PR description and update `README.md`.

If you need more context
- Look at `README.md` and `writeup.md` for design rationale and scaling notes. Use them as the source of truth for expected behaviours.

Questions / suggestions welcome — I'll iterate this guidance with any missing specifics you want included.

Examples
- Unit test (pytest) example to validate `POST /ingest` and basic endpoints. Put this in `tests/test_api.py`.

```python
from fastapi.testclient import TestClient
import subprocess
import json

from main import app

client = TestClient(app)

def ensure_model():
	# Ensure a model file exists for tests. This calls the project script which
	# deterministically writes `inefficient_model.pt`.
	subprocess.check_call(["python", "create_model.py"])

def test_ingest_and_endpoints(tmp_path):
	ensure_model()
	events = [{"user_id": "user-1", "timestamp": 1700000000, "features": [0.1, 0.2, 0.3]}]
	r = client.post("/ingest", json={"events": events})
	assert r.status_code == 200
	assert r.json()["processed"] == 1

	m = client.get("/users/user-1/median")
	assert m.status_code == 200
	assert m.json()["median"] is not None

	s = client.get("/stats")
	assert s.status_code == 200
	assert s.json()["events_processed"] >= 1
```

PR checklist
- **Run tests:** Ensure `pytest` passes locally. Include new tests in `tests/`.
- **Model artifact:** If your change depends on a model file, ensure `create_model.py` is invoked in CI or the test fixture creates a model; do not assume the model exists in the runner's workspace.
- **API contract:** If you change `/ingest` or `/users/{user_id}/median` shapes, update `README.md`, `event_generator.py` and `.github/copilot-instructions.md` and add tests covering the new contract.
- **Performance-sensitive changes:** If you modify inference (batching, async or GPU), add a small integration or load test and document expected throughput/latency impact in the PR description.
- **Documentation:** Update `README.md` and `writeup.md` if design or behaviour changes are user-observable.

