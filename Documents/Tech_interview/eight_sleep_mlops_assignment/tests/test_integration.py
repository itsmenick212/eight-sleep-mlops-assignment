import subprocess
import time
import random
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure project root is on sys.path so `from main import app` works when pytest
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient
import importlib


def ensure_model():
    subprocess.check_call(["python", "create_model.py"])


def post_batch(client: TestClient, batch):
    r = client.post("/ingest", json={"events": batch})
    return r


def make_event(uid):
    ts = int(time.time())
    features = [random.random(), random.random(), random.random()]
    return {"user_id": f"user-{uid}", "timestamp": ts, "features": features}


def test_concurrent_ingest_and_endpoints():
    # Ensure model exists before importing main so model loads on module import
    ensure_model()
    import main
    importlib.reload(main)
    client = TestClient(main.app)

    batch_size = 10
    num_batches = 50
    users = 50

    futures = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for _ in range(num_batches):
            batch = [make_event(random.randint(0, users - 1)) for _ in range(batch_size)]
            futures.append(ex.submit(post_batch, client, batch))

        processed = 0
        for fut in as_completed(futures):
            r = fut.result()
            assert r is not None
            assert r.status_code == 200
            processed += r.json().get("processed", 0)

    expected = batch_size * num_batches
    deadline = time.time() + 5
    while time.time() < deadline:
        s = client.get("/stats").json()
        if s.get("events_processed", 0) >= expected:
            break
        time.sleep(0.1)

    s = client.get("/stats").json()
    assert s.get("events_processed", 0) >= expected

    m = client.get("/users/user-0/median")
    assert m.status_code == 200
import subprocess
import time
import random
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure project root is on sys.path so `from main import app` works when pytest
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient
import importlib


def ensure_model():
    # Ensure a model file exists for tests. This calls the project script which
    # deterministically writes `inefficient_model.pt`.
    subprocess.check_call(["python", "create_model.py"])


def post_batch(client: TestClient, batch):
    r = client.post("/ingest", json={"events": batch})
    return r


def make_event(uid):
    ts = int(time.time())
    features = [random.random(), random.random(), random.random()]
    return {"user_id": f"user-{uid}", "timestamp": ts, "features": features}


def test_concurrent_ingest_and_endpoints():
    # Ensure a model file exists *before* importing/reloading `main` so the
    # module's startup model load happens successfully.
    ensure_model()
    import main
    importlib.reload(main)
    client = TestClient(main.app)

    # Simulate concurrent ingestion: 50 batches of 10 events (500 events)
    batch_size = 10
    num_batches = 50
    users = 50

    futures = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for _ in range(num_batches):
            batch = [make_event(random.randint(0, users - 1)) for _ in range(batch_size)]
            futures.append(ex.submit(post_batch, client, batch))

        processed = 0
        for fut in as_completed(futures):
            r = fut.result()
            assert r is not None
            assert r.status_code == 200
            processed += r.json().get("processed", 0)

    # Poll stats until events_processed reaches expected (small wait for race conditions)
    expected = batch_size * num_batches
    deadline = time.time() + 5
    while time.time() < deadline:
        s = client.get("/stats").json()
        if s.get("events_processed", 0) >= expected:
            break
        time.sleep(0.1)

    s = client.get("/stats").json()
    assert s.get("events_processed", 0) >= expected

    # Check a sample user median exists (may be None if no events for that user)
    # Pick any user we know we used (user-0)
    m = client.get("/users/user-0/median")
    assert m.status_code == 200
