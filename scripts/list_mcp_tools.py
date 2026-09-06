from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

ROOT = Path(__file__).resolve().parents[1]


async def list_tools() -> None:
    load_dotenv(ROOT / ".env")
    url = os.getenv("BINANCE_MCP_URL", "https://agent.binance.com/mcp/agentic")
    token = os.getenv("BINANCE_MCP_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with streamablehttp_client(url, headers=headers) as streams:
        read, write = streams[0], streams[1]
        session = ClientSession(read, write)
        await session.initialize()
        result = await session.list_tools()
        tools = [
            {
                "name": tool.name,
                "description": (tool.description or "")[:300],
                "inputSchema": tool.inputSchema,
            }
            for tool in result.tools
        ]
        print(json.dumps(tools, indent=2))
        (ROOT / "tools_discovered.json").write_text(json.dumps(tools, indent=2), encoding="utf-8")
        print(f"\n{len(tools)} tools -> tools_discovered.json")


if __name__ == "__main__":
    asyncio.run(list_tools())
