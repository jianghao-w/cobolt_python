from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from mcp_client import MCPClient


class McpRefreshWorker(QThread):
    """Worker to refresh MCP server connections without blocking the UI."""

    finished = pyqtSignal(dict)

    def __init__(self, client: MCPClient) -> None:
        super().__init__()
        self.client = client

    def run(self) -> None:
        result = self.client.connect_to_servers()
        self.finished.emit(result)

