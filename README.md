# DSMS（Data Standard Management System）MVP API

本项目基于 `FastAPI + SQLAlchemy(Async) + PostgreSQL/pgvector`，实现 `PRD.md` 定义的数据标准管理后端能力。

## 当前能力

- 分类管理：创建/更新/查询/软删除（含父子校验、名称非法字符校验、名称唯一校验）
- 数据标准管理：CRUD、版本升级、发布、状态流转（含 `code+version` 唯一约束）
- 标准代码（码表）管理：主表/子项维护、版本升级、发布、历史追溯、软删除
- 标准与码表绑定：每条标准最多绑定一个可用码表版本
- i18n 多语言：`standardi18n` 管理 `name/description` 多语言内容
- 搜索能力：关键词检索 + 向量检索
- 码表搜索：支持按主表字段与子项字段做关键词检索
- 只读前端界面：位于 `ui-readonly/`，支持标准列表、关键词/向量搜索、分页、列头排序、状态过滤、状态统计面板、详情与码表联动查看
- 关系管理：标准关系创建/查询/删除（含关键字段组合去重）
- Embedding 任务：支持指定或全量重建
- 统一错误返回：参数/业务校验失败时返回 `warnings` 和 `errors`

## 快速启动

1. 准备 PostgreSQL 并启用 `pgvector`。
2. 配置 `.env`（示例）：

```env
DATABASE_URL=postgresql+asyncpg://vector:vector@127.0.0.1:5432/vector
LMSTUDIO_BASE_URL=http://127.0.0.1:1234
LMSTUDIO_EMBEDDING_MODEL=text-embedding-qwen3-embedding-0.6b
DEFAULT_LANGUAGE=zh
```

3. 安装依赖：

```bash
pip install -r requirements.txt
```

4. 初始化系统（建表 + 索引 + Embedding 连通性检测）：

```bash
python init_system.py
```

也可直接执行 SQL：

```bash
psql -f sql/init_schema.sql
```

5. 启动 API：

```bash
uvicorn app.main:app --reload
```

6. 访问只读 UI：

```text
http://127.0.0.1:8000/ui-readonly/
```

## 说明

- 向量维度固定为 `1024`，并基于 HNSW 索引（`<=2000` 维）。
- Embedding 依赖 LM Studio 提供 `/v1/embeddings` 接口。
- 生产环境建议补充：Alembic 迁移、鉴权、审计日志与接口限流。
- 更详细接口说明见：`docs/API使用说明.md`。

## API 测试脚本

- 冒烟脚本：`scripts/api_smoke_test.py`
- 规则校验脚本：`scripts/api_validation_test.py`
- 全流程脚本：`scripts/api_workflow_test.py`
- 码表流程脚本：`scripts/api_codelist_test.py`
- 只读 UI 相关脚本：`scripts/api_readonly_ui_test.py`
- demo 数据脚本：`scripts/seed_demo_standards.py`（HR/EHS/财务资金各10条）
- 批量执行入口：`scripts/run_api_tests.py`

执行示例：

```bash
API_BASE_URL=http://127.0.0.1:8000 uv run python scripts/api_validation_test.py
API_BASE_URL=http://127.0.0.1:8000 SKIP_VECTOR=true uv run python scripts/api_workflow_test.py
API_BASE_URL=http://127.0.0.1:8000 SKIP_VECTOR=true uv run python scripts/run_api_tests.py
```

## MCP Server

`mcp_server/` 目录提供 MCP Server，让 LLM 通过 [Model Context Protocol](https://modelcontextprotocol.io) 直接操作数据标准。

### 快速启动

```bash
# 安装依赖
pip install -r mcp_server/requirements.txt

# SSE 模式启动（默认，适合远程客户端）
python -m mcp_server.server

# stdio 模式（适合 Claude Desktop / Cursor 等本地客户端）
python -m mcp_server.server --transport stdio
```

### 配置

编辑 `mcp_server/config.toml`（无需环境变量）：

```toml
[api]
base_url = "http://127.0.0.1:8000"   # 指向本 DSMS API

[sse]
host = "127.0.0.1"
port = 8765
```

详细说明见 [`mcp_server/README.md`](mcp_server/README.md)，包含 Claude Desktop / Cursor 配置示例和完整工具列表（26个工具）。
