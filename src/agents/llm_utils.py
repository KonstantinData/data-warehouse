"""Utilities for calling the OpenAI LLM and parsing markdown output."""

from __future__ import annotations

import os
from typing import Iterable, List

from dotenv import load_dotenv
from openai import OpenAI

DEFAULT_MODEL_NAME = "gpt-4.1-mini"


def build_openai_client() -> OpenAI:
    load_dotenv()

    api_key = os.getenv("OPEN_AI_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No OPEN_AI_KEY or OPENAI_API_KEY found in environment/.env "
            "- cannot call OpenAI LLM."
        )

    return OpenAI(api_key=api_key)


def resolve_model_name() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL_NAME)


def call_openai(client: OpenAI, messages: Iterable[dict], model_name: str | None = None) -> str:
    model = model_name or resolve_model_name()
    response = client.chat.completions.create(
        model=model,
        messages=list(messages),
    )
    return response.choices[0].message.content or ""


def extract_section_items(markdown: str, heading: str) -> List[str]:
    target = heading.strip().lower()
    items: List[str] = []
    in_section = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped[3:].strip().lower() == target
            continue
        if in_section and stripped.startswith(("-", "*")):
            item = stripped.lstrip("-* ").strip()
            if item:
                items.append(item)
    return items
