"""Simple Ollama client wrapper with error handling."""

from __future__ import annotations

from typing import Dict, Iterable, List

import ollama
import requests


class OllamaClient:
    """Wrapper around the ``ollama`` package used by the UI."""

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url
        self.client = ollama.Client(host=base_url, timeout=30)

    # ------------------------------------------------------------------
    def get_models(self) -> List[Dict[str, str]]:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("models", [])
        except Exception:
            pass

        response = self.client.list()
        if hasattr(response, "models"):
            return response.models
        return response.get("models", [])

    # ------------------------------------------------------------------
    def chat_stream(self, model: str, messages: List[Dict[str, str]]) -> Iterable[str]:
        if not model or not messages:
            raise ValueError("model and messages are required")

        response = self.client.chat(model=model, messages=messages, stream=True)
        for chunk in response:
            if "message" in chunk and "content" in chunk["message"]:
                yield chunk["message"]["content"]

