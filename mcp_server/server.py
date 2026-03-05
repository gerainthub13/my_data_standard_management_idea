"""
server.py — DSMS MCP Server 入口

启动方式：
  # SSE 模式（默认，读 config.toml 中 transport=sse）
  python -m mcp_server.server

  # stdio 模式（覆盖 config.toml，供 Claude Desktop / Cursor 等客户端使用）
  python -m mcp_server.server --transport stdio

  # SSE 模式（显式指定，可覆盖 config.toml 中的 host/port）
  python -m mcp_server.server --transport sse --host 0.0.0.0 --port 9000
"""
from __future__ import annotations

import argparse
import sys

from mcp.server.fastmcp import FastMCP

from mcp_server.config import get_settings
from mcp_server.tools.categories import (
    create_category,
    delete_category,
    list_categories,
    update_category,
)
from mcp_server.tools.code_lists import (
    create_code_list,
    create_code_list_revision,
    delete_code_list,
    get_code_list_bindings,
    get_code_list_detail,
    get_code_list_history,
    get_code_list_items,
    list_code_lists,
    publish_code_list,
    replace_code_list_items,
    search_code_lists,
    update_code_list,
    update_code_list_status,
)
from mcp_server.tools.relations import (
    create_standard_relation,
    delete_standard_relation,
    list_standard_relations,
)
from mcp_server.tools.search import keyword_search_standards, vector_search_standards
from mcp_server.tools.standards import (
    bind_standard_codelist,
    create_standard,
    create_standard_revision,
    delete_standard,
    get_standard_codelist_binding,
    get_standard_detail,
    get_standard_history,
    list_standards,
    publish_standard,
    update_standard,
    update_standard_status,
)

settings = get_settings()

mcp = FastMCP(name=settings.server.name)

# ─── 搜索工具（最常用，优先注册）────────────────────────────────────────────────
mcp.tool()(keyword_search_standards)
mcp.tool()(vector_search_standards)

# ─── 分类管理 ───────────────────────────────────────────────────────────────────
mcp.tool()(list_categories)
mcp.tool()(create_category)
mcp.tool()(update_category)
mcp.tool()(delete_category)

# ─── 数据标准管理 ───────────────────────────────────────────────────────────────
mcp.tool()(list_standards)
mcp.tool()(get_standard_detail)
mcp.tool()(get_standard_history)
mcp.tool()(create_standard)
mcp.tool()(update_standard)
mcp.tool()(publish_standard)
mcp.tool()(update_standard_status)
mcp.tool()(create_standard_revision)
mcp.tool()(delete_standard)
mcp.tool()(get_standard_codelist_binding)
mcp.tool()(bind_standard_codelist)

# ─── 码表管理 ───────────────────────────────────────────────────────────────────
mcp.tool()(list_code_lists)
mcp.tool()(search_code_lists)
mcp.tool()(get_code_list_detail)
mcp.tool()(get_code_list_items)
mcp.tool()(get_code_list_history)
mcp.tool()(get_code_list_bindings)
mcp.tool()(create_code_list)
mcp.tool()(update_code_list)
mcp.tool()(replace_code_list_items)
mcp.tool()(publish_code_list)
mcp.tool()(update_code_list_status)
mcp.tool()(create_code_list_revision)
mcp.tool()(delete_code_list)

# ─── 标准关系管理 ───────────────────────────────────────────────────────────────
mcp.tool()(list_standard_relations)
mcp.tool()(create_standard_relation)
mcp.tool()(delete_standard_relation)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DSMS MCP Server — 数据标准管理系统 MCP 服务",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--transport",
        choices=["sse", "stdio"],
        default=None,
        help="传输方式（覆盖 config.toml 中的 transport 配置）。"
             "stdio 适合 Claude Desktop/Cursor 等本地客户端；"
             "sse 适合通过 HTTP 连接的远程客户端。",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="SSE 监听 host（覆盖 config.toml 中的 sse.host）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="SSE 监听端口（覆盖 config.toml 中的 sse.port）",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    transport = args.transport or settings.server.transport

    if transport == "stdio":
        print("[DSMS MCP Server] 以 stdio 模式启动", file=sys.stderr)
        mcp.run(transport="stdio")
    else:
        host = args.host or settings.sse.host
        port = args.port or settings.sse.port
        print(
            f"[DSMS MCP Server] 以 SSE 模式启动，监听 http://{host}:{port}/sse",
            file=sys.stderr,
        )
        # FastMCP.run() 不接受 host/port 关键字参数；
        # 通过 mcp.settings 配置后再调用 run()。
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport="sse")


if __name__ == "__main__":
    main()
