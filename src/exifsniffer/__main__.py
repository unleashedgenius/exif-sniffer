"""CLI entry: run Streamable HTTP MCP server."""

from __future__ import annotations

from exifsniffer.server import mcp


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
