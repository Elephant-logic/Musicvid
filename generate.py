import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

API = "https://api.piapi.ai/api/v1/task"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-url")
    parser.add_argument("--origin-task-id", help="Reuse completed Kling video task; skip video generation")
    parser.add_argument("--audio-url", required=True)
    parser.add_argument("--poll-seconds", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()
    key = os.environ.get("PIAPI_KEY")
    if not key:
        sys.exit("Missing PIAPI_KEY environment variable")
    if not args.origin_task_id and not args.image_url:
        sys.exit("Provide --origin-task-id or --image-url")
    for url in (args.audio_url, args.image_url):
        if url is None:
            continue
        if not url.startswith("https://"):
            sys.exit("Use direct HTTPS media URLs")
    session = requests.Session()
    session.headers.update({"x-api-key": key, "Content-Type": "application/json"})

    def submit(payload):
        r = session.post(API, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        if not data.get("data", {}).get("task_id"):
            raise RuntimeError("Task submission failed: " + json.dumps(data, ensure_ascii=False))
        return data["data"]["task_id"]

    def wait(task_id):
        deadline = time.monotonic() + args.timeout_seconds
        while time.monotonic() < deadline:
            r = session.get(f"{API}/{task_id}", timeout=60)
            r.raise_for_status()
            data = r.json().get("data", {})
            status = str(data.get("status", "")).lower()
            print("Task status:", status, flush=True)
            if status in ("completed", "success", "succeeded"):
                return data
            if status in ("failed", "error", "cancelled", "canceled"):
                raise RuntimeError("PiAPI task failed: " + json.dumps(data, ensure_ascii=False))
            time.sleep(args.poll_seconds)
        raise TimeoutError(f"Timed out waiting for task {task_id}")

    if args.origin_task_id:
        video_id = args.origin_task_id.strip()
        print("Reusing existing video task:", video_id, flush=True)
    else:
        video_id = submit({
            "model": "kling",
            "task_type": "video_generation",
            "input": {
                "version": "2.6",
                "mode": "std",
                "duration": 10,
                "image_url": args.image_url,
                "prompt": "Static medium close-up of a fictional adult Thai female singer with short dark bob, round glasses and black top in a warm recording studio. Natural gentle performance, clear unobstructed face, minimal head movement, no scene cuts."
            },
            "config": {"service_mode": "public"}
        })
        print("Video task:", video_id, flush=True)
        wait(video_id)

    lip_id = submit({
        "model": "kling",
        "task_type": "lip_sync",
        "input": {"origin_task_id": video_id, "local_dubbing_url": args.audio_url},
        "config": {"service_mode": "public"}
    })
    print("Lip-sync task:", lip_id, flush=True)
    try:
        result = wait(lip_id)
    except Exception:
        try:
            response = session.get(f"{API}/{lip_id}", timeout=60)
            Path("result.json").write_text(json.dumps(response.json(), ensure_ascii=False, indent=2))
        except Exception as diagnostic_error:
            print("Could not save failure diagnostics:", diagnostic_error)
        raise
    Path("result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    output = result.get("output", {})
    url = output.get("video_url") or output.get("video") or output.get("url")
    if isinstance(url, dict):
        url = url.get("url")
    if not url:
        print("Completed, but output URL schema differs; inspect result.json")
        return
    response = requests.get(url, timeout=180)
    response.raise_for_status()
    Path("thai_singer_test.mp4").write_bytes(response.content)
    print("Saved thai_singer_test.mp4")

if __name__ == "__main__":
    main()
