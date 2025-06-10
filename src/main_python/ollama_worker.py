"""Worker thread used to call the Ollama API without blocking the UI."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from .ollama_client import OllamaClient


class OllamaWorker(QThread):
    response_received = pyqtSignal(str)
    response_complete = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, client: OllamaClient, model: str, messages: list) -> None:
        super().__init__()
        self.client = client
        self.model = model
        self.messages = messages
        self._is_running = True
        self._buffer = ""

    def run(self) -> None:
        try:
            for chunk in self.client.chat_stream(self.model, self.messages):
                if not self._is_running:
                    break
                self._buffer += chunk
                self.response_received.emit(self._buffer)

            if self._is_running:
                self.response_complete.emit(self._buffer)
        except Exception as exc:  # pragma: no cover - UI code
            if self._is_running:
                self.error_occurred.emit(str(exc))

    def stop(self) -> None:
        self._is_running = False
        self.wait()
