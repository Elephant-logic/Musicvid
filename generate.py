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
    parser.add_argument("--image-url", required=True)
    parser.add_argument("--audio-url", required=True)
    parser.add_argument("--poll-seconds", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()
    key = os.environ.get("PIAPI_KEY")
    if not key:
        sys.exit("Missing PIAPI_KEY environment variable")
    for url in (args.image_url, args.audio_url):
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
    result = wait(lip_id)
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
