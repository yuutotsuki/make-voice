#!/usr/bin/env python3
"""
Batch synthesize speech from a CSV file using MiniMax TTS.

Usage:
  python scripts/minimax_from_csv.py data/lines.csv --config configs/tts.json --out-dir voice/

CSV columns (header names must match):
  no (optional): management number; used for default filename if filename is empty
  filename (optional): base name for output file (without extension)
  text (required): content to synthesize; empty rows are skipped
  voice_id (optional): per-row override
  speed (optional): per-row override (float)
  pitch (optional): per-row override (float)
  emotion (optional): per-row override
  notes (optional): ignored

Filename rules:
  - If filename is provided, use it.
  - Else if no is provided, use line_{no}.
  - Else use line_{row_index} (1-based, excluding header).
  - .mp3 extension is always appended (audio format is controlled by configs/tts.json).
"""

import argparse
import copy
import csv
import os
import sys
from typing import Any, Dict, Optional

from minimax_tts import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_SPEED,
    DEFAULT_VOICE_ID,
    TTFA_BASE_URL,
    load_json_config,
    synthesize,
)


def parse_float(value: str) -> Optional[float]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        raise SystemExit(f"Invalid float value: {value}")


def parse_row_overrides(row: Dict[str, str]) -> Dict[str, Any]:
    """Extract per-row overrides for voice_setting from CSV row."""
    voice_id = (row.get("voice_id") or "").strip()
    speed = parse_float(row.get("speed") or "")
    pitch = parse_float(row.get("pitch") or "")
    emotion = (row.get("emotion") or "").strip()

    overrides: Dict[str, Any] = {"voice_setting": {}}
    if voice_id:
        overrides["voice_setting"]["voice_id"] = voice_id
    if speed is not None:
        overrides["voice_setting"]["speed"] = speed
    if pitch is not None:
        overrides["voice_setting"]["pitch"] = pitch
    if emotion:
        overrides["voice_setting"]["emotion"] = emotion

    return overrides


def derive_filename(row: Dict[str, str], row_idx: int) -> str:
    fname = (row.get("filename") or "").strip()
    if fname:
        return fname
    no_val = (row.get("no") or "").strip()
    if no_val:
        return f"line_{no_val}"
    return f"line_{row_idx}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate audio files from a CSV of lines using MiniMax TTS.",
    )
    parser.add_argument("csv_path", help="Path to CSV file with lines.")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to JSON config (same format as configs/tts.json).",
    )
    parser.add_argument(
        "--out-dir",
        default="voice",
        help="Output directory (created if missing).",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override TTS endpoint. Default uses main or TTFA endpoint based on flags/config.",
    )
    parser.add_argument(
        "--ttfa-endpoint",
        action="store_true",
        help="Use the low-TTFA endpoint https://api-uw.minimax.io/v1/t2a_v2",
    )
    return parser


def load_csv(path: str) -> list[Dict[str, str]]:
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if not reader.fieldnames:
                raise SystemExit("CSVヘッダーが見つかりません。")
            if "text" not in reader.fieldnames:
                raise SystemExit(f"CSVヘッダーに text 列がありません: {reader.fieldnames}")
            return rows
    except OSError as exc:
        raise SystemExit(f"Failed to read CSV file: {exc}") from exc


def main(argv: list[str]) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        raise SystemExit("MINIMAX_API_KEY is not set.")

    rows = load_csv(args.csv_path)
    config_payload = load_json_config(args.config)

    voice_setting_cfg = config_payload.get("voice_setting") if isinstance(config_payload.get("voice_setting"), dict) else {}
    model = config_payload.get("model") or DEFAULT_MODEL

    base_url = args.base_url or config_payload.get("base_url")
    if not base_url:
        base_url = TTFA_BASE_URL if args.ttfa_endpoint else DEFAULT_BASE_URL

    os.makedirs(args.out_dir, exist_ok=True)

    row_index = 0
    for row in rows:
        row_index += 1
        text = (row.get("text") or "").strip()
        if not text:
            continue

        overrides = parse_row_overrides(row)

        # Prepare per-row payload by copying config and applying overrides.
        per_row_config = copy.deepcopy(config_payload)
        voice_setting = per_row_config.get("voice_setting") if isinstance(per_row_config.get("voice_setting"), dict) else {}

        # Resolve final voice parameters with fallback to config defaults.
        voice_id = overrides["voice_setting"].get("voice_id") or voice_setting.get("voice_id") or DEFAULT_VOICE_ID
        speed = overrides["voice_setting"].get("speed")
        if speed is None:
            speed = voice_setting.get("speed", DEFAULT_SPEED)
        pitch = overrides["voice_setting"].get("pitch")
        if pitch is None:
            pitch = voice_setting.get("pitch")
        emotion = overrides["voice_setting"].get("emotion") or voice_setting.get("emotion")

        if "voice_setting" not in per_row_config or not isinstance(per_row_config["voice_setting"], dict):
            per_row_config["voice_setting"] = {}
        if pitch is not None:
            per_row_config["voice_setting"]["pitch"] = pitch
        if emotion:
            per_row_config["voice_setting"]["emotion"] = emotion

        filename_base = derive_filename(row, row_index)
        output_path = os.path.join(args.out_dir, f"{filename_base}.mp3")

        synthesize(
            text=text,
            output_path=output_path,
            voice_id=voice_id,
            speed=speed,
            base_url=base_url,
            model=model,
            audio_format=None,
            sample_rate=None,
            output_format=per_row_config.get("output_format") or "hex",
            config_payload=per_row_config,
            api_key=api_key,
        )

        print(f"[ok] {output_path}")


if __name__ == "__main__":
    main(sys.argv[1:])
