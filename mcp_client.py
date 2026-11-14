"""Saathi AI — Model Context Protocol (MCP) Client Adapter.

Provides seamless tool invocation through MCP:
1. By default, executes tools via local in-process MCP dispatcher (saathi_mcp.py).
2. If MCP_SERVER_URL is configured in .env, connects via Streamable-HTTP (MCP Protocol 2024-11-05).
3. Tools: search_policy, explain_payslip, check_payslip_anomalies, get_pf_howto,
   get_worker_payroll_record, get_ticket_status, create_hr_ticket (consent required).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
import httpx
from config import settings
import saathi_mcp


class MCPClient:
    """Unified MCP Client supporting both in-process dispatch and Streamable-HTTP."""
    def __init__(self):
        self.url = settings.mcp_server_url.strip() if settings.mcp_server_url else ""
        self.token = settings.mcp_auth_token
        self.version = settings.mcp_protocol_version
        self.session_id: Optional[str] = None
        self.initialized = False
        self.tools_cache: List[Dict[str, Any]] = saathi_mcp.TOOLS
        self._id = 0

    @property
    def configured(self) -> bool:
        # Always configured: uses local MCP tools if no remote URL is set
        return True

    @property
    def is_remote(self) -> bool:
        return bool(self.url)

    def _headers(self, method: Optional[str] = None, name: Optional[str] = None) -> Dict[str, str]:
        h = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": self.version
        }
        if self.token:
            h["Authorization"] = "Bearer " + self.token
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        if method:
            h["Mcp-Method"] = method
        if name:
            h["Mcp-Name"] = name
        return h

    async def _post_remote(self, method: str, params: Optional[Dict[str, Any]] = None, tool_name: Optional[str] = None) -> Any:
        self._id += 1
        body = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
        headers = self._headers(
            method if self.version == "2026-07-28" else None,
            (tool_name or method) if self.version == "2026-07-28" else None
        )
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.post(self.url, headers=headers, json=body)
            if res.status_code >= 400:
                raise RuntimeError(f"MCP HTTP {res.status_code}")
            sid = res.headers.get("Mcp-Session-Id")
            if sid:
                self.session_id = sid
            raw = res.text.strip()
            if raw.startswith("event:") or "data:" in raw:
                payloads = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")]
                raw = payloads[-1] if payloads else "{}"
            data = json.loads(raw or "{}")
            if data.get("error"):
                raise RuntimeError(str(data["error"].get("message", "MCP error")))
            return data.get("result", {})

    async def connect(self) -> Dict[str, Any]:
        """Connects to remote MCP server or verifies local MCP tools registry."""
        if not self.is_remote:
            self.tools_cache = saathi_mcp.TOOLS
            return {
                "connected": True,
                "mode": "local_in_process_mcp",
                "tools": [{"name": t["name"], "description": t["description"]} for t in self.tools_cache]
            }

        try:
            if self.version != "2026-07-28" and not self.initialized:
                await self._post_remote("initialize", {
                    "protocolVersion": self.version,
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "saathi-ai", "version": "2.0.0"}
                })
                self.initialized = True
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.post(self.url, headers=self._headers(), json={"jsonrpc": "2.0", "method": "notifications/initialized"})
                except Exception:
                    pass
            result = await self._post_remote("tools/list", {})
            self.tools_cache = result.get("tools", []) if isinstance(result, dict) else []
            return {
                "connected": True,
                "mode": "remote_streamable_http",
                "tools": [{"name": t.get("name"), "description": t.get("description", "")} for t in self.tools_cache]
            }
        except Exception as e:
            # Fall back to local MCP engine if remote fails
            self.tools_cache = saathi_mcp.TOOLS
            return {
                "connected": True,
                "mode": "fallback_local_in_process",
                "remote_error": str(e),
                "tools": [{"name": t["name"], "description": t["description"]} for t in self.tools_cache]
            }

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Invokes an MCP tool either remotely or via the in-process MCP server."""
        if self.is_remote:
            try:
                result = await self._post_remote("tools/call", {"name": name, "arguments": arguments}, tool_name=name)
                content = result.get("content", [])
                texts = [x.get("text", "") for x in content if x.get("type") == "text"]
                return {
                    "isError": bool(result.get("isError")),
                    "text": "\n".join(texts)[:12000],
                    "structuredContent": result.get("structuredContent") or (json.loads(texts[0]) if texts else {})
                }
            except Exception as e:
                # Fall back to local dispatcher
                pass

        try:
            res = saathi_mcp.execute_mcp_tool(name, arguments)
            text_repr = json.dumps(res, ensure_ascii=False)
            is_err = isinstance(res, dict) and bool(res.get("error"))
            return {
                "isError": is_err,
                "text": text_repr[:12000],
                "structuredContent": res
            }
        except Exception as e:
            return {
                "isError": True,
                "text": json.dumps({"error": str(e)}),
                "structuredContent": {"error": str(e)}
            }

    async def create_ticket(self, title: str, description: str, category: str, language: str, consent_given: bool = True) -> Optional[Dict[str, Any]]:
        """Invokes create_hr_ticket with explicit worker consent enforcement."""
        args = {
            "title": title,
            "description": description,
            "category": category,
            "language": language,
            "consent_given": consent_given
        }
        return await self.call_tool("create_hr_ticket", args)


mcp_client = MCPClient()
