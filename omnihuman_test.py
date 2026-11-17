"""OmniHuman 1.5 Thai singing test through PiAPI."""
import argparse
import json
import os
import time
from pathlib import Path
import requests

API = "https://api.piapi.ai/api/v1/task"
DEFAULT_IMAGE = "https://raw.githubusercontent.com/Elephant-logic/Musicvid/main/fictional_singer%281%29.jpg"
DEFAULT_AUDIO = "https://raw.githubusercontent.com/Elephant-logic/Musicvid/main/thai_test_8s.mp3"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-url", default=DEFAULT_IMAGE)
    parser.add_argument("--audio-url", default=DEFAULT_AUDIO)
    parser.add_argument("--task-id", default="", help="Resume existing task without spending credits")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    key = os.getenv("PIAPI_KEY")
    if not key:
        raise SystemExit("Missing PIAPI_KEY secret")
    session = requests.Session()
    session.headers.update({"x-api-key": key, "Content-Type": "application/json"})

    if args.task_id:
        task_id = args.task_id.strip()
        print("Checking existing OmniHuman task:", task_id, flush=True)
    else:
        for url in (args.image_url, args.audio_url):
            if not url.startswith("https://"):
                raise SystemExit("Media URLs must use HTTPS")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            if not response.content:
                raise SystemExit("Empty media file: " + url)
        payload = {
            "model": "omni-human",
            "task_type": "omni-human-1.5",
            "input": {
                "image_url": args.image_url,
                "audio_url": args.audio_url,
                "prompt": "A fictional adult Thai female singer with short dark bob haircut and round glasses performs an intimate Thai pop song in a warm recording studio. Sing naturally and expressively, face visible, gentle head movement, realistic mouth movements matched to the supplied audio, steady camera.",
                "fast_mode": True
            }
        }
        print("Submitting paid OmniHuman task (8 seconds, estimated $1.04)", flush=True)
        response = session.post(API, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        task_id = (result.get("data") or {}).get("task_id")
        if not task_id:
            raise RuntimeError("Task submission failed: " + json.dumps(result))
        print("OmniHuman task ID:", task_id, flush=True)
    Path("task_id.txt").write_text(task_id + "\n")
    deadline = time.monotonic() + args.timeout
    last = None
    while time.monotonic() < deadline:
        try:
            response = session.get(f"{API}/{task_id}", timeout=(15, 45))
            response.raise_for_status()
            last = response.json()
            Path("result.json").write_text(json.dumps(last, indent=2, ensure_ascii=False))
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            print("Transient polling error:", type(exc).__name__, flush=True)
            time.sleep(10)
            continue
        data = last.get("data") or {}
        status = str(data.get("status", "")).lower()
        print("Task status:", status, flush=True)
        if status in ("failed", "error", "cancelled", "canceled"):
            raise RuntimeError("OmniHuman task failed; see result.json artifact")
        if status in ("completed", "success", "succeeded"):
            output = data.get("output") or {}
            video_url = output.get("video") or output.get("video_url") or output.get("url")
            if isinstance(video_url, dict):
                video_url = video_url.get("url")
            if not video_url:
                raise RuntimeError("Completed without recognized video URL; inspect result.json")
            download = requests.get(video_url, timeout=180)
            download.raise_for_status()
            Path("omnihuman_thai_test.mp4").write_bytes(download.content)
            print("Saved omnihuman_thai_test.mp4", flush=True)
            return
        time.sleep(10)
    raise TimeoutError("Task still processing; rerun with --task-id " + task_id)

if __name__ == "__main__":
    main()
