#!/usr/bin/env python3
"""
Minimal script to read a text script and synthesize it to an audio file
via the MiniMax Text-to-Audio v2 HTTP API (non-streaming).

Usage:
  python scripts/minimax_tts.py path/to/script.txt --out out.mp3
  python scripts/minimax_tts.py path/to/script.txt --config config.json

Environment:
  MINIMAX_API_KEY must be set to your API token.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional

import requests


# Default endpoint from https://platform.minimax.io/docs/api-reference/speech-t2a-http
DEFAULT_BASE_URL = "https://api.minimax.io/v1/t2a_v2"
TTFA_BASE_URL = "https://api-uw.minimax.io/v1/t2a_v2"

DEFAULT_MODEL = "speech-2.6-hd"
DEFAULT_VOICE_ID = "Japanese_DecisivePrincess"
DEFAULT_SPEED = 1.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a text script into an audio file using Minimax Audio API.",
    )
    parser.add_argument(
        "script_path",
        help="Path to the text file that contains the script to read.",
    )
    parser.add_argument(
        "--out",
        dest="output_path",
        default=None,
        help="Output audio path (extension sets desired format). Defaults to script path with .mp3.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to JSON config with payload overrides (voice_setting, audio_setting, voice_modify, etc.).",
    )
    parser.add_argument(
        "--voice-id",
        default=None,
        help="voice_id to use (see MiniMax system voice list or your cloned voices).",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=None,
        help="Playback speed multiplier (0.5-2.0).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name (e.g., speech-2.6-turbo, speech-2.6-hd, speech-02-hd, speech-01-turbo, etc.).",
    )
    parser.add_argument(
        "--audio-format",
        default=None,
        choices=["mp3", "pcm", "flac", "wav"],
        help="Override audio format sent in audio_setting. If omitted, inferred from output extension or defaults to mp3.",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=None,
        help="Optional sample_rate for audio_setting (e.g., 32000).",
    )
    parser.add_argument(
        "--output-format",
        choices=["hex", "url"],
        default=None,
        help="API output_format (hex writes decoded bytes locally, url downloads the returned URL).",
    )
    parser.add_argument(
        "--ttfa-endpoint",
        action="store_true",
        help="Use the low-TTFA endpoint https://api-uw.minimax.io/v1/t2a_v2",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override TTS endpoint. Default uses main or TTFA endpoint based on flags.",
    )
    return parser


def load_script_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError as exc:
        raise SystemExit(f"Failed to read script file: {exc}") from exc


def guess_format_from_path(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in {".mp3", ".wav", ".ogg", ".flac", ".pcm"}:
        return ext.lstrip(".")
    return "mp3"


def deep_update(target: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively update target dict with updates dict."""
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_update(target[key], value)
        else:
            target[key] = value
    return target


def load_json_config(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        raise SystemExit(f"Failed to read config file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Config file is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit("Config file must contain a JSON object.")
    return data


def synthesize(
    *,
    text: str,
    output_path: str,
    voice_id: str,
    speed: float,
    base_url: str,
    model: str,
    audio_format: Optional[str],
    sample_rate: Optional[int],
    output_format: str,
    config_payload: Optional[Dict[str, Any]],
    api_key: str,
    timeout: int = 60,
) -> None:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    inferred_format = audio_format or guess_format_from_path(output_path)
    base_payload: Dict[str, Any] = {
        "model": model,
        "text": text,
        "stream": False,
        "output_format": output_format,
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed,
        },
        "audio_setting": {
            "format": inferred_format,
        },
    }

    if config_payload:
        deep_update(base_payload, config_payload)

    # Enforce non-streaming and required fields; CLI/defaults override config.
    voice_setting = base_payload.get("voice_setting") if isinstance(base_payload.get("voice_setting"), dict) else {}
    audio_setting = base_payload.get("audio_setting") if isinstance(base_payload.get("audio_setting"), dict) else {}

    base_payload["model"] = model
    base_payload["text"] = text
    base_payload["stream"] = False
    base_payload["output_format"] = output_format

    voice_setting["voice_id"] = voice_id
    voice_setting["speed"] = speed
    audio_setting["format"] = inferred_format
    if sample_rate:
        audio_setting["sample_rate"] = sample_rate

    # Remove empty/None string fields to avoid API invalid params (e.g., emotion="").
    voice_setting = {
        k: v for k, v in voice_setting.items() if not (v is None or (isinstance(v, str) and v.strip() == ""))
    }
    audio_setting = {
        k: v for k, v in audio_setting.items() if not (v is None or (isinstance(v, str) and v.strip() == ""))
    }

    base_payload["voice_setting"] = voice_setting
    base_payload["audio_setting"] = audio_setting

    try:
        response = requests.post(base_url, headers=headers, json=base_payload, timeout=timeout)
    except requests.RequestException as exc:
        raise SystemExit(f"Request failed: {exc}") from exc

    try:
        resp_json = response.json()
    except ValueError as exc:
        raise SystemExit(f"Failed to parse JSON response: {exc}") from exc

    if response.status_code >= 400:
        raise SystemExit(f"API error {response.status_code}: {resp_json}")

    base_resp = (resp_json.get("base_resp") or {})
    if base_resp.get("status_code") not in (0, None):
        raise SystemExit(f"API returned error: {base_resp}")

    data = resp_json.get("data") or {}
    audio_field = data.get("audio")
    if not audio_field:
        raise SystemExit("No audio field in response.")

    if output_format == "url":
        try:
            audio_response = requests.get(audio_field, timeout=timeout)
            audio_response.raise_for_status()
            audio_bytes = audio_response.content
        except requests.RequestException as exc:
            raise SystemExit(f"Failed to download audio from URL: {exc}") from exc
    else:
        try:
            audio_bytes = bytes.fromhex(audio_field)
        except ValueError as exc:
            raise SystemExit(f"Failed to decode hex audio: {exc}") from exc

    try:
        with open(output_path, "wb") as audio_file:
            audio_file.write(audio_bytes)
    except OSError as exc:
        raise SystemExit(f"Failed to write audio file: {exc}") from exc


def main(argv: list[str]) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        raise SystemExit("MINIMAX_API_KEY is not set.")

    text = load_script_text(args.script_path)
    if not text:
        raise SystemExit("Script file is empty.")

    output_path = args.output_path
    if not output_path:
        base, _ = os.path.splitext(args.script_path)
        output_path = f"{base}.mp3"

    config_payload = load_json_config(args.config) if args.config else {}

    voice_setting_cfg = config_payload.get("voice_setting") if isinstance(config_payload.get("voice_setting"), dict) else {}
    audio_setting_cfg = config_payload.get("audio_setting") if isinstance(config_payload.get("audio_setting"), dict) else {}

    model = args.model or config_payload.get("model") or DEFAULT_MODEL
    voice_id = args.voice_id or voice_setting_cfg.get("voice_id") or DEFAULT_VOICE_ID
    speed = args.speed if args.speed is not None else voice_setting_cfg.get("speed", DEFAULT_SPEED)
    output_format = args.output_format or config_payload.get("output_format") or "hex"
    audio_format = args.audio_format or audio_setting_cfg.get("format")
    sample_rate = args.sample_rate or audio_setting_cfg.get("sample_rate")

    base_url = args.base_url or config_payload.get("base_url")
    if not base_url:
        base_url = TTFA_BASE_URL if args.ttfa_endpoint else DEFAULT_BASE_URL

    synthesize(
        text=text,
        output_path=output_path,
        voice_id=voice_id,
        speed=speed,
        base_url=base_url,
        model=model,
        audio_format=audio_format,
        sample_rate=sample_rate,
        output_format=output_format,
        config_payload=config_payload,
        api_key=api_key,
    )

    print(f"Audio saved to {output_path}")


if __name__ == "__main__":
    main(sys.argv[1:])
