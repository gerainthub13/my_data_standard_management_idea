# DSMS MCP Server

[DSMS](../README.md)（Data Standard Management System）的 MCP Server，让 LLM 能够通过 [Model Context Protocol](https://modelcontextprotocol.io) 直接查询和管理数据标准。

## 工具列表（26个）

| 分类 | 工具 | 说明 |
|------|------|------|
| **搜索** | `keyword_search_standards` | 关键词搜索标准（精确定位） |
| | `vector_search_standards` | 向量语义搜索标准（近似检索） |
| **分类** | `list_categories` | 查询分类 |
| | `create_category` | 创建分类 |
| | `update_category` | 更新分类 |
| | `delete_category` | 软删除分类 |
| **数据标准** | `list_standards` | 分页查询标准 |
| | `get_standard_detail` | 查询标准详情（含多语言、码表） |
| | `get_standard_history` | 查询标准历史版本 |
| | `create_standard` | 创建标准（草稿） |
| | `update_standard` | 更新标准内容 |
| | `publish_standard` | 发布标准 |
| | `update_standard_status` | 更新标准状态 |
| | `create_standard_revision` | 创建标准新版本 |
| | `delete_standard` | 软删除标准 |
| | `get_standard_codelist_binding` | 查询标准绑定码表 |
| | `bind_standard_codelist` | 绑定/解绑码表 |
| **码表** | `list_code_lists` | 分页查询码表 |
| | `search_code_lists` | 关键词搜索码表（主表+子项） |
| | `get_code_list_detail` | 查询码表详情（含子项） |
| | `get_code_list_items` | 分页查询码表子项 |
| | `get_code_list_history` | 查询码表历史版本 |
| | `get_code_list_bindings` | 查询码表被哪些标准引用 |
| | `create_code_list` | 创建码表 |
| | `update_code_list` | 更新码表主表 |
| | `replace_code_list_items` | 批量替换码表子项 |
| | `publish_code_list` | 发布码表 |
| | `update_code_list_status` | 更新码表状态 |
| | `create_code_list_revision` | 创建码表新版本 |
| | `delete_code_list` | 软删除码表 |
| **标准关系** | `list_standard_relations` | 查询标准关系 |
| | `create_standard_relation` | 创建标准关系 |
| | `delete_standard_relation` | 删除标准关系 |

## 安装依赖

> [!IMPORTANT]
> **必须使用独立的虚拟环境**，不能与主项目共用 venv。
> 原因：MCP SDK（`mcp[cli]`）依赖 `starlette>=0.52`，而主项目的
> `fastapi==0.115.6` 要求 `starlette<0.42.0`，两者不兼容。
> MCP server 本身就是独立部署，使用独立 venv 是正确的架构。

```bash
# 1. 在 mcp_server/ 目录下创建专用虚拟环境
python -m venv mcp_server/.venv

# 2. 激活（Windows）
mcp_server\.venv\Scripts\activate
# 激活（macOS / Linux）
# source mcp_server/.venv/bin/activate

# 3. 安装依赖
pip install -r mcp_server/requirements.txt
```

也可以用 `uv`：

```bash
uv venv mcp_server/.venv
uv pip install -r mcp_server/requirements.txt --python mcp_server/.venv
```

## 配置

编辑 `mcp_server/config.toml`（所有配置均在此文件，无需环境变量）：

```toml
[api]
base_url = "http://127.0.0.1:8000"   # DSMS API 地址
timeout_seconds = 30

[server]
name = "dsms-mcp-server"
default_language = "zh"              # 向量搜索默认语言
transport = "sse"                    # 默认传输方式：sse 或 stdio

[sse]
host = "127.0.0.1"
port = 8765
```

## 启动

### SSE 模式（默认，适合网络连接）

```bash
# 读取 config.toml 中的配置
python -m mcp_server.server

# 覆盖 host/port
python -m mcp_server.server --transport sse --host 0.0.0.0 --port 9000
```

### stdio 模式（适合 Claude Desktop / Cursor 等本地客户端）

```bash
python -m mcp_server.server --transport stdio
```

## 在 LLM 客户端中配置

### Claude Desktop（stdio）

编辑 Claude Desktop 配置文件（`claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "dsms": {
      "command": "python",
      "args": ["-m", "mcp_server.server", "--transport", "stdio"],
      "cwd": "C:/path/to/dsms"
    }
  }
}
```

### Cursor / 其他客户端（SSE）

先启动 MCP Server（保持运行），再在客户端配置 SSE 地址：

```
http://127.0.0.1:8765/sse
```

### MCP Inspector（调试用）

```bash
# 需先安装 mcp[cli]
python -m mcp dev mcp_server/server.py
```

## 项目文件结构

```
mcp_server/
├── __init__.py
├── server.py           # 入口：注册工具，启动 MCP server
├── config.py           # 读取 config.toml
├── http_client.py      # httpx 异步客户端封装
├── config.toml         # 独立配置文件 ← 修改此文件连接你的 DSMS API
├── pyproject.toml
├── requirements.txt
├── README.md           # 本文档
└── tools/
    ├── categories.py   # 分类管理工具
    ├── standards.py    # 数据标准管理工具
    ├── search.py       # 搜索工具（关键词 + 向量）
    ├── code_lists.py   # 码表管理工具
    └── relations.py    # 标准关系工具
```

## 注意事项

- **MCP Server 独立部署**：不依赖主项目的 FastAPI 进程，但 DSMS API 必须在线；
- **向量搜索**（`vector_search_standards`）依赖 DSMS API 后端配置的 LM Studio embedding 服务；
  其他工具无此依赖；
- **写操作**均包含在内，请确保客户端（LLM）有合适的操作权限意识；
- Python 版本要求：`>=3.12`（使用内置 `tomllib`）。
