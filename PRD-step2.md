# PRD-step2（数据标准代码/码表）

## 1. 文档目标

本阶段新增“数据标准代码（码表）”能力，补齐数据标准记录的枚举值/代码域管理。  
目标是在现有 DSMS MVP 架构中，落地可版本化、可追溯、可软删除、可被数据标准引用的码表能力。

---

## 2. 业务背景与问题

当前系统已具备“分类、数据标准、关系、搜索、向量”能力，但缺少“标准代码（列表）”实体，导致：

- 标准字段的取值域无法被结构化管理；
- 标准发布后缺少稳定的码值快照与版本追溯；
- 前端无法提供统一的码表选择、引用与展示能力；
- 下游系统（ETL/数据治理/规则引擎）缺少可消费的权威码表接口。

---

## 3. 范围定义

### 3.1 本期范围（In Scope）

- 标准代码列表主表管理：创建、查询、更新、版本、发布、历史、软删除。
- 标准代码明细子表管理：增删改查、批量维护、草稿编辑约束。
- 数据标准与标准代码列表的绑定管理（每条标准最多绑定一个码表）。
- 变更管理与版本控制：revision、publish、一致性校验。
- 面向前端的查询能力：分页、关键词过滤、可绑定码表筛选。

### 3.2 非本期范围（Out of Scope）

- 码值审批流（多人审批）。
- Excel 导入导出。
- 码值多语言（先保留扩展位，暂不实现 API）。
- 图谱化关系分析与可视化。

---

## 4. 核心业务规则

1. 一个“标准代码列表编码（list_code）”可对应多个版本；同编码仅允许一个已发布且最新版本。  
2. 一条数据标准记录最多绑定一个标准代码列表版本。  
3. 绑定时，默认仅允许绑定“未删除 + 已发布 + 最新”的码表版本。  
4. 码表主表与子表均采用逻辑删除，不做物理删除。  
5. 草稿状态（status=0）允许编辑主表与子表；已发布版本不可直接修改，必须通过 revision 新建版本。  
6. revision 会复制主表内容和子表明细，版本号自动 +1。  
7. 发布新版本时：同 list_code 下其他已发布版本自动退役（status=2），并设置 is_latest=false。  
8. 被“已发布数据标准”绑定的码表版本不允许直接软删除（防止引用断裂）。  

状态枚举沿用现有标准：`0 草稿`、`1 已发布`、`2 退役`、`3 废弃/删除`、`4 其他`。

---

## 5. 业务流程（后端视角）

### 5.1 新建并发布码表

1. 创建码表主表（默认版本 1、草稿）。  
2. 维护码表子项（标准代码、标准代码名称、代码含义）。  
3. 校验子项编码唯一性后发布。  
4. 发布后可被数据标准绑定。

### 5.2 变更码表（版本化）

1. 对已发布版本调用 revision，生成新草稿版本。  
2. 修改草稿版本主表/子项。  
3. 发布新版本，旧发布版本自动退役。  
4. 已绑定旧版本的数据标准保持原引用（历史可追溯），由业务决定是否迁移到新版本。

### 5.3 数据标准绑定码表

1. 前端查询可绑定码表列表。  
2. 选择码表后调用绑定接口。  
3. 系统校验“标准存在、码表可绑定、单标准最多一条绑定”。  
4. 保存绑定关系，用于标准详情和下游消费。

---

## 6. 数据模型设计（新增）

## 6.1 `standardcodelist`（主表）

- `id` UUID PK
- `list_code` VARCHAR(50) NOT NULL（码表编码）
- `name` VARCHAR(200) NOT NULL（码表名称）
- `purpose` TEXT NULL（用途）
- `status` SMALLINT NOT NULL DEFAULT 0
- `version` INTEGER NOT NULL DEFAULT 1
- `is_latest` BOOLEAN NOT NULL DEFAULT FALSE
- `is_deleted` BOOLEAN NOT NULL DEFAULT FALSE
- `created_at`/`updated_at` TIMESTAMPTZ
- `last_update_user` VARCHAR(100) DEFAULT 'api'

约束/索引：

- `CHECK (version >= 1)`，`CHECK (status between 0 and 4)`
- 生效唯一：`UNIQUE(list_code, version) WHERE is_deleted=false`
- 发布唯一：`UNIQUE(list_code) WHERE is_deleted=false AND status=1 AND is_latest=true`
- 普通索引：`list_code`、`status`、`is_latest`、`is_deleted`

## 6.2 `standardcodeitem`（子表）

- `id` UUID PK
- `list_id` UUID FK -> `standardcodelist.id`
- `item_code` VARCHAR(100) NOT NULL（标准代码）
- `item_name` VARCHAR(200) NOT NULL（标准代码名称）
- `meaning` TEXT NULL（代码含义/描述）
- `sort_order` INTEGER NOT NULL DEFAULT 0
- `is_deleted` BOOLEAN NOT NULL DEFAULT FALSE
- `created_at`/`updated_at` TIMESTAMPTZ
- `last_update_user` VARCHAR(100) DEFAULT 'api'

约束/索引：

- 生效唯一：`UNIQUE(list_id, item_code) WHERE is_deleted=false`
- 索引：`(list_id, is_deleted)`、`item_name`

## 6.3 `datastandardcodelink`（标准绑定关系表）

- `id` BIGSERIAL PK
- `standard_id` UUID FK -> `datastandard.id`
- `code_list_id` UUID FK -> `standardcodelist.id`
- `is_deleted` BOOLEAN NOT NULL DEFAULT FALSE
- `created_at`/`updated_at` TIMESTAMPTZ
- `last_update_user` VARCHAR(100) DEFAULT 'api'

约束/索引：

- 生效唯一：`UNIQUE(standard_id) WHERE is_deleted=false`（最多绑定一个）
- 索引：`standard_id`、`code_list_id`

---

## 7. API 设计（MVP）

说明：保持与现有 `/api/v1/standards` 风格一致，统一错误结构 `code/message/errors/warnings`。

### 7.1 码表主表 API

1. `POST /api/v1/code-lists`  
功能：创建码表（`version=1,status=0,is_latest=false`）。

2. `GET /api/v1/code-lists`  
功能：分页查询；支持 `list_code/name/status/is_latest` 过滤；默认仅返回 `is_deleted=false`。

3. `GET /api/v1/code-lists/{code_list_id}`  
功能：码表详情（可选 `include_items=true`）。

4. `PUT /api/v1/code-lists/{code_list_id}`  
功能：更新码表主表（仅草稿/退役可编辑，建议最终限制为草稿）。

5. `DELETE /api/v1/code-lists/{code_list_id}`  
功能：软删除（`is_deleted=true,status=3,is_latest=false`）；若存在已发布标准绑定则拒绝。

6. `POST /api/v1/code-lists/{code_list_id}/revision`  
功能：复制当前版本生成新草稿，自动递增版本，复制全部子项。

7. `PATCH /api/v1/code-lists/{code_list_id}/publish`  
功能：发布当前版本，保证同 `list_code` 仅一条 `status=1,is_latest=true`。

8. `PATCH /api/v1/code-lists/{code_list_id}/status`  
功能：状态变更（若改为发布，走发布一致性逻辑）。

9. `GET /api/v1/code-lists/code/{list_code}/history`  
功能：按编码查询历史版本，按 `version desc` 返回。

### 7.2 码表子项 API

1. `GET /api/v1/code-lists/{code_list_id}/items`  
功能：分页查询子项；支持 `keyword`（item_code/item_name）过滤。

2. `PUT /api/v1/code-lists/{code_list_id}/items`  
功能：批量覆盖式更新（事务内执行）；仅草稿可编辑。  
请求体建议：
- `items[]`: `item_code/item_name/meaning/sort_order`
- 规则：同请求内 `item_code` 不可重复；为空数组表示清空子项（逻辑删除）。

3. `POST /api/v1/code-lists/{code_list_id}/items`（可选）  
功能：单条新增（若前端偏向行级编辑）。

4. `PUT /api/v1/code-lists/{code_list_id}/items/{item_id}`（可选）  
功能：单条更新。

5. `DELETE /api/v1/code-lists/{code_list_id}/items/{item_id}`（可选）  
功能：单条软删除。

MVP 建议优先落地 `GET + PUT(批量)`，满足低代码/表格编辑场景。

### 7.3 数据标准绑定 API

1. `GET /api/v1/standards/{standard_id}/code-list`  
功能：查询当前标准绑定的码表（无则返回空对象/404 由前端约定）。

2. `PUT /api/v1/standards/{standard_id}/code-list`  
功能：设置或替换绑定。  
请求体：
- `code_list_id: UUID | null`（`null` 表示解绑）  
规则：
- 标准记录必须存在且未删除；
- 若标准已发布，建议仅允许绑定“已发布最新码表”；
- 保证单标准最多一条生效绑定。

3. `GET /api/v1/code-lists/{code_list_id}/bindings`（可选）  
功能：查询被哪些标准引用（用于前端删除前提示）。

---

## 8. 前端协同需求（必须预留）

1. 列表页需要“可绑定码表”筛选能力：建议查询参数 `bindable=true`。  
2. 标准详情页需要同时返回绑定码表摘要（`id/list_code/name/version/status`）。  
3. 码表编辑页通常为表格批量提交，后端需支持“批量校验 + 原子写入”。  
4. 版本对比页需要历史列表接口稳定返回 `version/status/is_latest/updated_at`。  
5. 删除动作需要“可解释错误”：若被发布标准引用，返回明确错误码（例如 `CODE_LIST_IN_USE`）。  

---

## 9. 非功能要求

1. 并发一致性：发布、revision、绑定操作需事务化。  
2. 可观测性：关键操作记录审计字段 `last_update_user/updated_at`。  
3. 性能要求：
- 码表列表查询 P95 < 300ms（1 万码表规模）；
- 子项查询 P95 < 300ms（单码表 1 万子项规模，分页）。  
4. 兼容性：不破坏现有 `standards/search/relations` API。  

---

## 10. 验收标准（DoD）

1. 可完成码表从创建、编辑、发布、修订、历史查询到软删除全流程。  
2. 可完成数据标准与码表的一对零或一绑定，并具备约束校验。  
3. revision 能复制子项并生成新版本。  
4. 删除与发布规则可阻断非法操作（如被发布标准引用的码表删除）。  
5. API 文档、测试脚本与 SQL 迁移脚本齐备。  

---

## 11. 待确认事项（需你确认）

1. 已发布标准是否允许绑定“非发布码表”版本（当前建议：不允许）。  
2. 被草稿标准引用的码表是否允许删除（当前建议：允许，但需解绑或随软删除联动）。  
3. 子项编辑方式是否只保留批量 `PUT`，还是同时提供行级 CRUD。  
4. 本期是否需要码表多语言（当前建议：不做，保留扩展）。  

回复： 你的建议很完善，按照建议执行开发