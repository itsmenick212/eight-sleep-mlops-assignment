"""Lightweight load testing script for the ingestion endpoint.

Usage:
    python scripts/load_test.py --url http://localhost:8000/ingest --rps 200 --duration 30 --users 100

This script is intentionally small and easy to run locally. It mimics a subset of the behavior in `event_generator.py` but has smaller default values which are friendlier for local development.
"""
import time
import argparse
import random
from concurrent.futures import ThreadPoolExecutor
import requests


def make_event(uid):
    ts = int(time.time())
    features = [random.random(), random.random(), random.random()]
    return {"user_id": f"user-{uid}", "timestamp": ts, "features": features}


def post_batch(url, batch):
    try:
        r = requests.post(url, json={"events": batch}, timeout=5)
        return r.status_code
    except Exception as e:
        print("post error", e)
        return None


def run(target_url="http://localhost:8000/ingest", rps=200, duration_sec=30, users=100):
    batch_size = 10
    batches_per_sec = max(1, rps // batch_size)
    interval = 1.0 / batches_per_sec
    end = time.time() + duration_sec
    sent = 0
    with ThreadPoolExecutor(max_workers=20) as ex:
        next_send = time.time()
        while time.time() < end:
            batch = [make_event(random.randint(0, users - 1)) for _ in range(batch_size)]
            ex.submit(post_batch, target_url, batch)
            sent += batch_size
            next_send += interval
            sleep_time = next_send - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
    print(f"Sent approximately {sent} events at target RPS={rps}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000/ingest")
    parser.add_argument("--rps", type=int, default=200)
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--users", type=int, default=100)
    args = parser.parse_args()
    run(target_url=args.url, rps=args.rps, duration_sec=args.duration, users=args.users)
