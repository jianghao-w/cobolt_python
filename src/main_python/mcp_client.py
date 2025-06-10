from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List

from mcp_tools import MCPServer, mcp_servers


@dataclass
class McpTool:
    server: str
    name: str
    description: str

    def call(self, arguments: Dict[str, Any]) -> str:
        # Placeholder implementation - real MCP interaction would go here
        return f"Executed {self.name} with {arguments}"


class MCPClient:
    def __init__(self) -> None:
        self.clients: List[subprocess.Popen] = []
        self.tool_cache: List[McpTool] = []

    # ------------------------------------------------------------------
    def connect_to_servers(self) -> Dict[str, Any]:
        at_least_one_success = False
        errors: List[Dict[str, str]] = []
        self.clients.clear()
        for server in mcp_servers:
            try:
                self._connect_to_server(server)
                at_least_one_success = True
            except Exception as exc:  # pragma: no cover - runtime logging
                logging.error("Failed to connect to MCP server %s: %s", server.name, exc)
                errors.append({"serverName": server.name, "error": str(exc)})

        if at_least_one_success:
            self.tool_cache = self.list_all_connected_tools()

        return {
            "success": at_least_one_success,
            "errors": errors,
            "errorMessage": None if at_least_one_success else "Failed to connect to any MCP server",
        }

    # ------------------------------------------------------------------
    def _connect_to_server(self, server: MCPServer) -> None:
        env = os.environ.copy()
        if server.env:
            env.update(server.env)
        proc = subprocess.Popen(
            [server.command, *server.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
        self.clients.append(proc)
        logging.info("Connected to MCP server %s", server.name)

    # ------------------------------------------------------------------
    def list_all_connected_tools(self) -> List[McpTool]:
        tools: List[McpTool] = []
        for client, server in zip(self.clients, mcp_servers):
            tools.extend(self.list_tools(client, server))
        return tools

    # ------------------------------------------------------------------
    def list_tools(self, proc: subprocess.Popen, server: MCPServer) -> List[McpTool]:
        try:
            if proc.stdin and proc.stdout:
                proc.stdin.write(json.dumps({"command": "listTools"}) + "\n")
                proc.stdin.flush()
                response = proc.stdout.readline()
                data = json.loads(response)
                return [
                    McpTool(server=server.name, name=t.get("name", ""), description=t.get("description", ""))
                    for t in data.get("tools", [])
                ]
        except Exception as exc:  # pragma: no cover - runtime logging
            logging.error("Failed to list tools for %s: %s", server.name, exc)
        return []
