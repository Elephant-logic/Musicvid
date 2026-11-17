"""Split a song into consecutively timed clips for audio-driven video generation.

Uses sample-accurate ffmpeg trim filters. The final short clip is padded with
silence for a uniform generation window, while the manifest retains its real
duration so final video can be trimmed back to the song's true ending.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import zipfile
from pathlib import Path


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def run(input_path: Path, output_dir: Path, window_s: int = 8) -> Path:
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    duration = probe_duration(input_path)
    count = math.ceil(duration / window_s)
    segments = []
    for index in range(count):
        start = index * window_s
        end = min((index + 1) * window_s, duration)
        actual = end - start
        filename = f"clip_{index + 1:03d}_{start:04d}s.mp3"
        target = output_dir / filename
        # Keep the final section at the same length as the others so the
        # generation API receives a normal 8 s input, with silence padding.
        flt = (
            f"atrim=start={start}:end={end},asetpts=PTS-STARTPTS,"
            f"aresample=48000,apad=whole_dur={window_s},atrim=duration={window_s}"
        )
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(input_path),
             "-vn", "-af", flt, "-ar", "48000", "-ac", "2", "-codec:a", "libmp3lame",
             "-b:a", "192k", str(target)], check=True,
        )
        segments.append({
            "index": index + 1,
            "file": filename,
            "start_seconds": start,
            "end_seconds": round(end, 6),
            "song_audio_seconds": round(actual, 6),
            "generated_audio_seconds": window_s,
            "last_segment_padded": actual < window_s - 0.001,
        })
    manifest = {
        "source_name": input_path.name,
        "source_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "source_duration_seconds": round(duration, 6),
        "window_seconds": window_s,
        "clip_count": count,
        "notes": [
            "Clips are consecutive 8-second audio windows with no gaps in the source timeline.",
            "The last clip has silence padding; trim its corresponding video to song_audio_seconds.",
            "For the final edit, use the original full song as the soundtrack to avoid MP3 re-encode drift.",
            "No image continuity is guaranteed by OmniHuman; pass each accepted final frame as the next clip's image input and inspect each result.",
        ],
        "segments": segments,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    archive = output_dir.parent / "thai_song_8_second_clips.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(output_dir.iterdir()):
            zipped.write(path, arcname=path.name)
    print(f"Source duration: {duration:.3f} seconds")
    print(f"Created {count} audio clips, {window_s} seconds each")
    print(f"Last clip contains {segments[-1]['song_audio_seconds']:.3f} seconds of song plus silence")
    print(f"Archive: {archive}")
    return archive


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("input", type=Path)
    p.add_argument("--output", type=Path, default=Path("thai_song_clips"))
    p.add_argument("--seconds", type=int, default=8)
    opts = p.parse_args()
    if not (1 <= opts.seconds < 35):
        p.error("--seconds must be 1–34")
    run(opts.input, opts.output, opts.seconds)
