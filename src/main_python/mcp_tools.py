from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class MCPServer:
    name: str
    command: str
    args: List[str]
    env: Optional[Dict[str, str]] = field(default_factory=dict)


mcp_servers: List[MCPServer] = []


def get_config_path() -> Path:
    app_data = Path.home() / ".cobolt"
    app_data.mkdir(parents=True, exist_ok=True)
    return app_data / "mcp-servers.json"


def load_config() -> bool:
    """Load MCP server configuration from the default JSON file."""
    config_path = get_config_path()
    try:
        mcp_servers.clear()
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as fh:
                config_json = json.load(fh)
        else:
            config_json = {"mcpServers": {}}
            with open(config_path, "w", encoding="utf-8") as fh:
                json.dump(config_json, fh, indent=2)
            logging.info("Created new MCP config file at %s", config_path)

        for name, server in config_json.get("mcpServers", {}).items():
            mcp_servers.append(
                MCPServer(
                    name=name,
                    command=server.get("command", ""),
                    args=server.get("args", []),
                    env=server.get("env", {}),
                )
            )
        return True
    except Exception as exc:  # pragma: no cover - runtime logging
        logging.error("Error loading MCP config: %s", exc)
        return False


def open_config_file() -> None:
    """Open the MCP configuration file with the default system editor."""
    path = get_config_path()
    if not path.exists():
        load_config()
    if sys.platform.startswith("darwin"):
        subprocess.Popen(["open", str(path)])
    elif os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(path)])
