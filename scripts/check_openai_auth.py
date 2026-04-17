#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if k and k not in os.environ:
            os.environ[k] = v.strip().strip("\"").strip("'")


def mask(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:6]}...{value[-4:]}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check OpenAI API key/project/org auth")
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()

    load_env_file(Path(args.env_file))

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    project_id = os.getenv("OPENAI_PROJECT_ID", "").strip()
    organization = os.getenv("OPENAI_ORGANIZATION", "").strip()

    if not api_key:
        print("OPENAI_API_KEY missing")
        return 2

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if project_id:
        headers["OpenAI-Project"] = project_id
    if organization:
        headers["OpenAI-Organization"] = organization

    print(f"Testing key: {mask(api_key)}")
    print(f"Project header: {project_id or '(none)'}")
    print(f"Organization header: {organization or '(none)'}")

    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "messages": [{"role": "user", "content": "Return JSON exactly: {\"ok\": true}"}],
        "response_format": {"type": "json_object"},
    }

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"Network error: {exc}")
        return 3

    print(f"HTTP {resp.status_code}")
    body = resp.text
    if len(body) > 800:
        body = body[:800] + "..."
    print(body)

    return 0 if resp.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
