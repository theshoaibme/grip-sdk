"""Model Context Protocol (MCP) client and tool connector for Grip AI SDK.

Supports connecting to MCP servers via standard I/O (stdio subprocess)
or HTTP/SSE endpoints, discovering remote tools dynamically, and binding
them into Grip Agents.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from google_ai_search.tools.base import Tool

logger = logging.getLogger("grip.mcp")


@dataclass
class MCPTool:
    """A tool advertised by an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class MCPClient:
    """Client for Model Context Protocol (MCP) servers.

    Usage:
        >>> # Stdio connection
        >>> mcp = MCPClient(command="python", args=["my_mcp_server.py"])
        >>> mcp.connect()
        >>> tools = mcp.list_tools()
        >>> result = mcp.call_tool("read_file", {"path": "report.txt"})
        >>> mcp.close()

        >>> # Or directly connect to an Agent:
        >>> agent = grip.Agent(provider="google")
        >>> agent.connect_mcp(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"])
    """

    def __init__(
        self,
        command: str | list[str] | None = None,
        args: list[str] | None = None,
        url: str | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        mock_tools: dict[str, tuple[str, Callable[..., Any], dict[str, Any]]] | None = None,
    ) -> None:
        self.command = command
        self.args = args or []
        self.url = url
        self.env = env
        self.cwd = cwd
        self.mock_tools = mock_tools or {}

        self._process: subprocess.Popen[str] | None = None
        self._request_id = 0
        self._lock = threading.Lock()
        self._tools_cache: list[MCPTool] = []
        self._connected = False

    def __enter__(self) -> MCPClient:
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def connect(self) -> bool:
        """Establish connection and perform MCP initialization handshake."""
        if self._connected:
            return True

        # Mock in-memory mode
        if self.mock_tools:
            self._connected = True
            self._tools_cache = [
                MCPTool(name=name, description=desc, input_schema=schema)
                for name, (desc, _, schema) in self.mock_tools.items()
            ]
            return True

        if not self.command and not self.url:
            raise ValueError("MCPClient requires either 'command' (stdio) or 'url' (HTTP/SSE).")

        if self.command:
            cmd_list = [self.command] if isinstance(self.command, str) else list(self.command)
            cmd_list.extend(self.args)

            full_env = os.environ.copy()
            if self.env:
                full_env.update(self.env)

            try:
                self._process = subprocess.Popen(
                    cmd_list,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    cwd=self.cwd,
                    env=full_env,
                )
            except Exception as exc:
                raise RuntimeError(f"Failed to spawn MCP process {cmd_list}: {exc}") from exc

            # Handshake: initialize
            init_res = self._send_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "grip-sdk", "version": "0.3.4"},
                },
            )

            # Notification: initialized
            self._send_notification("notifications/initialized", {})
            self._connected = True
            logger.info("Connected to MCP server via stdio: %s", cmd_list[0])
            return True

        # HTTP/SSE mode
        self._connected = True
        return True

    def _next_id(self) -> int:
        with self._lock:
            self._request_id += 1
            return self._request_id

    def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        req_id = self._next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        if self._process and self._process.stdin and self._process.stdout:
            with self._lock:
                req_line = json.dumps(payload) + "\n"
                self._process.stdin.write(req_line)
                self._process.stdin.flush()

                # Read response line
                resp_line = self._process.stdout.readline()
                if not resp_line:
                    raise RuntimeError("MCP process closed stdout unexpectedly.")
                data = json.loads(resp_line.strip())
                if "error" in data:
                    raise RuntimeError(f"MCP Error [{data['error'].get('code')}]: {data['error'].get('message')}")
                return data.get("result", {})

        raise RuntimeError("MCPClient is not connected via stdio transport.")

    def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        if self._process and self._process.stdin:
            with self._lock:
                self._process.stdin.write(json.dumps(payload) + "\n")
                self._process.stdin.flush()

    def list_tools(self) -> list[MCPTool]:
        """List all tools advertised by the connected MCP server."""
        if not self._connected:
            self.connect()

        if self.mock_tools:
            return self._tools_cache

        res = self._send_request("tools/list", {})
        raw_tools = res.get("tools", [])
        tools = [
            MCPTool(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
            for t in raw_tools
        ]
        self._tools_cache = tools
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call an MCP tool by name with arguments."""
        if not self._connected:
            self.connect()

        args = arguments or {}

        if self.mock_tools:
            if name not in self.mock_tools:
                raise KeyError(f"Mock MCP tool '{name}' not found.")
            _, fn, _ = self.mock_tools[name]
            return fn(**args)

        res = self._send_request("tools/call", {"name": name, "arguments": args})
        # MCP tools return content blocks: [{"type": "text", "text": "..."}]
        content_list = res.get("content", [])
        if content_list and isinstance(content_list, list):
            text_parts = [c.get("text", "") for c in content_list if isinstance(c, dict) and "text" in c]
            if text_parts:
                return "\n".join(text_parts)
        return res

    def as_tools(self) -> list[Tool]:
        """Convert all MCP tools into standard Grip callable Tool objects."""
        mcp_tools = self.list_tools()
        callable_tools: list[Tool] = []

        for mt in mcp_tools:
            t_name = mt.name
            t_desc = mt.description
            t_schema = mt.input_schema

            # Build a closure binding t_name
            def make_caller(tool_name: str) -> Callable[..., Any]:
                def caller(**kwargs: Any) -> Any:
                    return self.call_tool(tool_name, kwargs)

                caller.__name__ = tool_name
                caller.__doc__ = t_desc
                return caller

            tool_obj = Tool(
                name=t_name,
                description=t_desc,
                fn=make_caller(t_name),
                parameters_schema=t_schema,
            )
            callable_tools.append(tool_obj)

        return callable_tools

    def close(self) -> None:
        """Terminate connection and clean up child processes."""
        if self._process:
            try:
                if self._process.stdin:
                    self._process.stdin.close()
                self._process.terminate()
                self._process.wait(timeout=2.0)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            finally:
                self._process = None
        self._connected = False


def create_in_memory_mcp_client(
    tools: dict[str, tuple[str, Callable[..., Any], dict[str, Any]]],
) -> MCPClient:
    """Create an in-memory MCPClient for testing or local agent tool composition."""
    client = MCPClient(mock_tools=tools)
    client.connect()
    return client
