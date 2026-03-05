# 工作计划-step2（数据标准代码/码表）

## 1. 计划目标

基于《PRD-step2》，在不破坏现有 MVP 能力前提下，完成“标准代码（码表）”后端设计与实现，交付可直接联调的 API、数据库迁移、测试与文档。

---

## 2. 实施范围

- 新增码表主表、子表、标准绑定关系表。
- 新增码表管理 API（主表 + 子表 + 版本）。
- 新增标准绑定 API。
- 补充 SQL 初始化与迁移脚本。
- 补充自动化测试脚本与 API 文档。

---

## 3. 分阶段任务

## 阶段 A：需求冻结与接口契约（0.5 天）

产出：

- 冻结《PRD-step2》业务规则与状态流转。
- 确认前端交互模式：子项批量编辑 or 行级编辑。
- 确认绑定规则：发布标准绑定限制。

验收：

- 待确认项形成明确结论，可直接进入开发。

## 阶段 B：数据库设计与迁移（1 天）

任务：

- 在 `app/models.py` 新增：
- `StandardCodeList`
- `StandardCodeItem`
- `DataStandardCodeLink`
- 在 `sql/init_schema.sql` 增加建表、索引、约束。
- 新增迁移脚本（建议：`sql/migrate_v4_codelist.sql`）。

验收：

- 新库初始化可成功建表。
- 旧库迁移脚本可幂等执行。

## 阶段 C：Schema/校验/服务层（1.5 天）

任务：

- 在 `app/schemas.py` 增加码表与绑定相关请求/响应模型。
- 在 `app/validators.py` 增加码表编码、子项编码校验（复用标准编码规则并补充子项规则）。
- 在 `app/services/` 新增 `code_lists.py`：
- 列表查询、详情读取
- revision 复制（含子项复制）
- 发布一致性更新
- 批量子项 upsert/逻辑删除

验收：

- 服务层函数可独立单测（或通过 API 测试覆盖）。
- 校验错误输出符合统一格式。

## 阶段 D：路由实现（2 天）

任务：

- 新增 `app/routers/code_lists.py`：
- 主表 CRUD + history + publish + revision + status
- 子项查询 + 批量更新
- 在 `app/routers/standards.py` 增加标准绑定/解绑接口，或新增 `app/routers/standard_code_links.py`。
- 在 `app/main.py` 注册新路由。

验收：

- OpenAPI 可见完整新接口。
- 核心接口通过手工联调（创建->编辑->发布->绑定->历史）。

## 阶段 E：测试与文档（1 天）

任务：

- 增加脚本测试（建议）：
- `scripts/api_codelist_test.py`（码表主流程）
- `scripts/api_binding_test.py`（绑定约束）
- 更新 `scripts/run_api_tests.py` 聚合执行。
- 更新 `docs/API使用说明.md`（新增接口与错误码）。

验收：

- 测试脚本全部通过。
- 关键异常场景（冲突、非法状态、被引用删除）有覆盖。

---

## 4. 任务清单（按代码目录）

1. `app/models.py`：新增 3 个 ORM 模型 + 约束索引。  
2. `app/schemas.py`：新增码表与绑定 DTO。  
3. `app/services/code_lists.py`：新增核心业务逻辑。  
4. `app/routers/code_lists.py`：新增码表路由。  
5. `app/routers/standards.py`：扩展标准绑定接口。  
6. `app/main.py`：注册路由。  
7. `sql/init_schema.sql`：补充建表。  
8. `sql/migrate_v4_codelist.sql`：新增迁移。  
9. `docs/API使用说明.md`：更新文档。  
10. `scripts/*.py`：新增自动化测试。

---

## 5. 风险与应对

1. 并发发布冲突  
应对：数据库唯一约束 + 事务 + `IntegrityError` 转业务错误。

2. 子项大批量更新性能  
应对：批量写入 + 必要索引 + 分页读取。

3. 绑定规则与业务预期不一致  
应对：阶段 A 冻结规则，并在错误码里给出清晰原因。

4. 历史版本子项复制遗漏  
应对：revision 逻辑纳入主流程测试，强制校验复制数量一致。

---

## 6. 预计工期

总计：约 6 个工作日（不含你确认等待时间）。  
若阶段 A 一次确认完成，可在同一迭代内交付。

---

## 7. 开发完成定义（Done）

1. 新增表结构、迁移脚本、后端接口、测试脚本均提交。  
2. 主流程与关键异常流程测试通过。  
3. 文档更新完成并可指导前端联调。  
4. 不影响现有分类、标准、搜索、关系接口行为。  
