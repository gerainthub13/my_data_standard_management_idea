# PRD v3

<aside>
🔑

主要内容由Gemini牵头进行规划（对比了ChatGPT，发现Gemini的工程思维更好一些）。经过Grok、Perplexity、ChatGPT三位的共同意见，最终以perplexity版本为主，综合其他选手的输出，迭代生成v0.3版本PRD。

人工完善和更新

</aside>

## 一、整体项目规划与功能设计

## 1. 产品背景与目标

- 建立一套「数据标准管理系统（DSMS）」，让企业内部的字段、指标、码表等标准可以统一管理、版本化、关联建模，并支持语义相似搜索。
- 使用嵌入向量 + 向量库（pgvector）能力，为「模糊搜索 / 语义检索」提供底层支撑，最终服务于标准治理、元数据管理、数据资产地图等上层应用。

核心目标：

- 建立数据标准和码值的单一事实来源。
- 支持标准的全生命周期管理：草稿、发布、废弃、历史版本追溯。
- 支持多语言展示和编辑（至少 zh、en，将来可扩展 ja 等）。
- 支持通过关键词 + 向量召回的混合搜索，提升「找标准」的体验。
- 支持高效发现：关键词搜索 + 语义搜索（利用已部署的pgvector + LMstudio）。
- 为未来的「标准与模型/表字段映射」打基础，提供关系建模能力。
- 实现严格的版本与状态控制，确保下游系统（ETL、质量检查、建模工具）消费到的标准具有权威性。
- 在MVP阶段最小化开发范围，同时奠定可复用的元数据模型基础。

未来功能点（当前不关注，但如果有强相关性，考虑预留设计）

- 物理模型自动映射/发现标准。
- 完整的多用户审批流程。
- 基于标准的内置数据质量校验。
- 复杂的关联关系图可视化。

## 2. 核心用户与场景

- 数据标准管理人员：定义标准、维护版本与状态、管理分类、维护业务/技术属性等。
- 数据工程师 / 开发：通过 API/DB 查询标准，做表结构设计、字段命名、ETL 映射等工作。
- 业务分析 / 数据消费者：通过自然语言或关键词搜索找到合适的数据标准，理解含义和属性。
- 对接多种前端界面，实现“能力的输出”而不是“大而全的产品”，例如：既可以对接对接UI，也可以部分对接低代码开发环境，还可以通过MCP协议封装，形成智能工具。

典型场景示例：

- 「我要新建一个用户主题表，希望所有字段都对齐到标准字典」。
- 「我有一个外部系统的字段列表，想快速找到内部标准字段进行映射」。
- 「我要看某一个标准从 1.0 到 2.0 的变更历史」。
- 业务人员通过ChatBot了解数据标准信息。数据管理人员需要通过低代码平台实现快速的数据导入和导出查询。

## 3. 功能模块概览

1. 分类管理模块（专用于系统管理的分类，很少变动）
2. 数据标准管理模块（含版本控制、状态流转）
3. 扩展属性（业务/技术/管理属性）管理
4. 多语言（i18n）管理
5. 关系管理（标准与标准、标准与外部对象）
6. 搜索与向量检索模块
7. Embedding 生成与同步任务模块
8. 对外 API 服务模块（RESTful）

---

## 二、阶段聚焦与功能细化 + 技术路径

## 1. 现阶段聚焦范围（MVP）

MVP 范围锁定在：

1. 核心数据结构落地（datastandard、standardvectorstore、i18n 表结构 & 关系）。
2. 标准的基础 CRUD + 版本升级/发布 + 状态管理 API。
3. 按标准维度的多语言读写（至少 name / description 字段的 i18n）。
4. 向量生成 & 向量检索 API（仅覆盖标准实体）；调用LMstudio提供的embedding API服务。
5. 简单的关系表（为后续标准-表字段映射预留）。

先不做的（仅做 schema 预留）：

- 高复杂度的关系管理（图谱式关系可放后续）。
- 支持多实体类型（如指标、度量、度量字典）统一建模，可放 Roadmap。
- 精细化权限、工作流引擎、审批流等，可在 DSMS 成熟后叠加。

## 2. 模块级功能细化（MVP）

## 2.1 分类管理

- 功能：
    - 创建/修改/删除分类（支持父子层级）。
    - 分类类型（系统 / 自定义）、分类作用域（标准、指标、字典等）。
- 技术建议：
    - 使用单表 category，支持 parent_id 自引用实现树形结构。
    - 提供基础 CRUD API，后续可扩展为多租户/多系统 scope。

## 2.2 数据标准管理（核心）

- 功能：
    - 创建标准（草稿态，默认 version=1 （整数，不采用小版本逻辑），status=0）。
    - 编辑标准（仅草稿状态允许修改）。
    - 发布标准（status 从 0→1，并把同 code 的其它版本 is_latest=false）。
    - 废弃标准（status=2退役； status =3 废弃）。
    - 查询标准详情（包含 extattributes + i18n）。
    - 查询标准历史版本（按 code 聚合）。
- 技术路径：
    - 业务/技术/管理属性，拆多张属性表。
    - 通过 is_latest + status 保证一个 code 在任一时刻只有一个「发布」版本。

## 2.3 扩展属性（extattributes）

- 功能：
    - 支持为标准配置扩展属性，如：
        - 业务属性：业务口径、业务部门、所属系统等。
        - 技术属性：数据类型、长度、精度、取值范围、默认值等。
        - 管理属性：维护周期、标准等级、责任人等。

## 2.4 i18n 多语言

- 功能：
    - 为标准的 name / description 等字段维护多语言版本。
    - 读取时，根据 Accept-Language 或 lang 参数返回对应语言，若无则回退到默认语言（如 zh）。
- 技术路径：
    - 使用独立 i18n 表（例如 standard_i18n / standardi18n），字段：
        - refid：指向 datastandard.id
        - fieldname：name / description
        - language：zh/en/ja
        - content：文本内容。
    - 读取时通过 LEFT JOIN 关联，写入时控制 refid+fieldname+language 唯一约束。

## 2.5 关系管理（为后续做准备）

- 功能：
    - 维护标准与标准、标准与外部对象（表、字段、外部标准）之间的关系。
    - 常见关系类型：parent-child、标准映射、映射到表字段等。
- 技术路径：
    - 采用 entityrelation / standardrelation 表：
        - sourceid / sourcecode + sourcever
        - targetid / targetver
        - reltype：parentchild, maptotable, standardlink 等
        - targettype：internalstd, externalstd, table, column 等。
    - MVP 建议只保留结构，不强行做复杂校验，先支持简单录入和查询。

## 2.6 搜索与向量检索

- 功能：
    - 关键字搜索：支持对 code、name、description 的模糊匹配。
    - 向量搜索：支持按自然语言描述进行相似标准召回。支持预先限定分类或者标签筛选
- 技术路径：
    - 关键词搜索用 Postgres ILIKE + 合理的索引。
    - 向量搜索：
        - Embedding 存放在 standardvectorstore（refid+lang+embedding）。
        - 使用 pgvector HNSW 索引（1024-4096 维，由embedding模型决定，cosine similarity）。
        - 查询语句中 join datastandard 获取标准信息，并过滤 is_latest、status=1。

## 2.7 Embedding 生成与同步

- 功能：
    - 当新建/更新标准时，自动生成或更新其 embedding。
    - 支持按语言分别生成向量（cn/en）。
- 技术路径：
    - 通过 FastAPI BackgroundTasks 或独立任务队列（后续可扩展 Celery/RQ），调用 LM Studio提供的Embedding API。
    - 将生成结果写入 standardvectorstore（refid+lang+sourcecontent+embedding）。
    - 同步逻辑：
        - 若标准是草稿，embedding 可生成但检索接口可根据 status 决定是否参与搜索。
        - 发布时确保对应标准的 embedding 最新有效。

---

## 三、数据结构设计与思路说明

- 向量独立存储：避免TOAST机制对主表I/O的影响，保持主表轻量。
- 属性子表拆分：便于原型阶段直接加字段、约束数据质量（优于JSONB的模糊性）。
- 多语言行式存储：扩展性强，主表保留中文列便于低代码直接使用。
- 关联关系占位：MVP阶段仅记录必要引用，不引入复杂图模型。

## 1. 分类表：category

核心字段建议：

- id：SERIAL / BIGSERIAL，“整数+自增长”模式，保证每一个分类目录名称有唯一的ID
- name：分类名称，分类名称作为面向用户的重要信息，在生效的记录中（is_delete= Y）不允许出现重复。
- parent_id：父分类 id（可为 null）
- category_type：category_type 目前只有system/custom两种类型，分别代表系统预置的分类与用户自定义分类
- scope：只有standard、metric、bizdict三类。分别面向数据标准、分析指标、业务字典三类应用。目前只使用standard
- is_deleted：删除标记（Y/N）
- created_at：TIMESTAMP
- updated_at：TIMESTAMP。
- last_update_user（默认使用”api“，后期API添加用户鉴权后，填写调用API的用户名）

设计思路：

- 保留 scope 字段，为未来统一管理不同对象类型的分类做准备。
- parent_id 实现树结构，方便做主题域、业务域等多级分类。
1. 创建逻辑（POST）：API被调用时，代码需要首先检验传入数据是否满足约定的数据类型要求。
1. 名称中仅允许有效的字符和“-”，不允许存在“_%#?!*&^$@~‘“”等可能导致“注入漏洞zhu”或者可能会影响代码逻辑的字符。阿拉伯数字不能作为名称开头使用。
2. parent_id需要校验是否为存在ID
3. category_type字段仅接受”custom“值，系统预置的条目会通过数据库进行统一调整
2. 查询逻辑（GET）：支持传ID查询，也支持模糊查询。当用户请求获取category且没有提供ID时，需要用户提供名称关键词和每页展示条数。API提供简单的关键词搜索功能，返回总条目数、每页显示条目数、当前页数和记录信息。
3. 更新逻辑（PUT）：在更新数据之前，必须验证ID是否存在。如果用户更新记录的parent_id，还需要验证parent_id对应的id是否存在。同样，需要在更新name时验证是否存在非法字符。
4. 删除逻辑（DELETE）：不允许物理删除数据，仅通过变更”is_delete“字段内容标记记录是否被删除。不允许用户通过API恢复已删除的数据记录。

## 2. 标准主表：datastandard

- id：UUID（主键）
- code：VARCHAR(50)，业务编码，同一 code 对应多个版本
- name：VARCHAR(200)，默认语言名称（如中文）
- description：TEXT，默认语言描述
- status：SMALLINT（0 草稿，1 已发布，2 退役/历史，3 废弃（未被发布的历史版本），4 其他/未定义）
- is_deleted: BOOLEAN，代替物理删除的逻辑删除标记。当记录标记删除后，API不再访问此纪录。
- version：INT（整数）
- is_latest：BOOLEAN，标识同 code 下是否为最新版本
- category_id：INT，指向 category.id
- created_at：TIMESTAMP
- updated_at：TIMESTAMP。
- last_update_user（默认使用”api“，后期API添加用户鉴权后，填写调用API的用户名）

设计考量：

- 采用 UUID 作为 id，便于分布式环境，也方便与向量表等外表对接。
- 使用 code + version 做业务维度标识，保证可追溯历史版本。
- 使用 is_latest 帮助快速查询当前生效版本，避免复杂子查询。
- extattributes 用 JSONB，兼顾灵活性和 Postgres 层面的索引能力（后期可对常用 key 建 GIN 索引）。

## 2.5 扩展属性：业务属性表、技术属性表、管理属性表

（结构较为简单，根据主表设计，此处未提供建议）

## 3. 向量存储表：standardvectorstore

字段建议：

- id：BIGSERIAL
- refid：UUID，指向 datastandard.id
- lang：VARCHAR(10)，如 zh、en
- modelname：VARCHAR，记录 embedding 模型名称（如 bge-large-zh）
- sourcecontent：TEXT，用于记录生成 embedding 的原始文本（如 name + description + 关键属性拼接）。
- embedding：VECTOR(4096)，pgvector 类型。

索引建议：

- HNSW 索引：
    - `CREATE INDEX idx_std_vector_hnsw ON standardvectorstore USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);`

设计思路：

- 将向量拆分至独立表，避免 datastandard 行过大触发频繁 TOAST（特别是 4096 维向量）。
- lang 字段使多语言 embedding 共存，不同语言检索可按 lang 过滤。
- sourcecontent 便于调试/回溯，以及后续做 embedding 质量分析。

## 4. i18n 表：standardi18n（示例命名）

字段：

- id：SERIAL
- refid：UUID，指向 datastandard.id
- fieldname：VARCHAR(50)，例如 name / description
- language：VARCHAR(10)，如 en、ja
- content：TEXT。

约束：

- 唯一索引：refid + fieldname + language。

设计意图：

- 解耦主表与多语言内容，将来可扩展更多字段（如 remark、alias 等）。
- 允许增量添加语言而不影响现有数据结构。

## 5. 关系表：standardrelation / entityrelation

字段（结合你多次迭代的设计）：

- id：SERIAL
- sourceid：UUID / VARCHAR（标准内部 id 或代码）
- sourcever：VARCHAR(20)，可选
- targetid：VARCHAR(100)，可以是内部 id / 外部系统 id / 表字段标识等
- targetver：VARCHAR(20)，可选
- reltype：VARCHAR(30)，如 parentchild, maptotable, standardlink, modelmapping
- targettype：VARCHAR(50)，如 internalstd, externalstd, table, column
- relstatus：INT，0 草稿，1 生效等。

设计考虑：

- 通过 targettype 支持多种对象类型，不局限于内部标准。
- 将来可用此表构建数据资产图谱，但 MVP 阶段只提供记录 +简单查询。
- 源对象可以统一用 datastandard.id，避免 code/version 变更导致关系错乱。

## 6. 操作日志表

（未给出参考设计）

设计考虑：

- 记录API调用情况
- 为后期多用户操作日志预留设计

---

## 四、API 清单与功能对标

这一部分，把你在对话里分散列出的 API 端点收束成一份清晰清单，并说明各 API 与业务功能的对应关系。

## 1. 分类管理 API

1. GET `/api/v1/categories`
    - 功能：查询分类列表（可支持树形展开）。
    - 参数：可选 parent_id / scope 等。
2. POST `/api/v1/categories`
    - 功能：创建分类。
3. PUT `/api/v1/categories/{id}`
    - 功能：更新分类。
4. DELETE `/api/v1/categories/{id}`
    - 功能：删除分类（如有子节点可限制或级联）。

## 2. 标准 CRUD + 版本管理 API

1. POST `/api/v1/standards`
    - 功能：创建标准（草稿）。
    - 行为：写入 datastandard（status=0），触发异步 embedding 任务写 standardvectorstore。
    - 入参：StandardSchema（含基础字段 + extattributes）。
2. GET `/api/v1/standards`
    - 功能：分页查询标准列表。
    - 过滤：code、name、status、category、is_latest 等。
3. GET `/api/v1/standards/{id}`
    - 功能：查询标准详情。
    - 行为：JOIN standardi18n（根据 Accept-Language 或 lang）+ 返回 extattributes。
4. PUT `/api/v1/standards/{id}`
    - 功能：更新标准（仅允许在草稿/历史状态下）。
    - 行为：更新 datastandard，并触发 embedding 异步更新（写 standardvectorstore）。
5. DELETE `/api/v1/standards/{id}`
    - 功能：逻辑删除（视业务需求，用 is_deleted=True 替代物理删除）。
6. POST `/api/v1/standards/{id}/revision` / `/upgrade`
    - 功能：基于已有标准创建新版本。
    - 行为：复制原记录，version+1（如 1→2），status=0, is_latest=false（待发布）。
7. PATCH `/api/v1/standards/{id}/publish`
    - 功能：发布指定版本。
    - 行为：
        - 将该记录 status=1, is_latest=true。
        - 将相同 code 的其它记录 is_latest=false，status 视情况保持为历史。
8. PATCH `/api/v1/standards/{id}/status`
    - 功能：修改标准状态（如废弃）。
    - 行为：更新 status，并根据需要更新 is_latest（例如废弃最新版本后，需要指定新的最新版本或全部失效）。
9. GET `/api/v1/standards/{code}/history`
    - 功能：按 code 返回全部版本历史。
    - 行为：datastandard 过滤 code，按 version / created_at 排序。

## 3. 搜索与向量检索 API

1. POST `/api/v1/standards/search`
    - 功能：组合搜索。
    - 请求体：
        - `query`: 关键词字符串，可为空
        - `lang`: zh/en
        - `use_vector`: bool，是否使用向量检索
        - `top_k`: int。
    - 行为：
        - 若 use_vector=true：
            - 调用 Embedding API 得到 query 向量；
            - 在 standardvectorstore 以 lang 过滤，做向量相似检索；
            - join datastandard 取得标准详情，限制 is_latest=true, status=1；
        - 若 query 不为空，额外用 ILIKE 对 name/code 做 filter 或结果重排。
2. 可选：GET `/api/v1/standards/similar/{id}`
    - 功能：给定某个标准，找相似标准。
    - 行为：取 standardvectorstore 中该 refid 的 embedding，然后做向量检索。

## 4. 关系管理 API

1. POST `/api/v1/standards/{id}/relations`
    - 功能：创建从当前标准出发的关系。
    - 请求体：targetid, targettype, reltype, relstatus 等。
2. GET `/api/v1/standards/{id}/relations`
    - 功能：查询当前标准的所有出入度关系记录。
3. DELETE `/api/v1/standards/relations/{relid}`
    - 功能：删除关系记录。

## 5. Embedding 管理 API

1. POST `/api/v1/embeddings/rebuild`
    - 功能：对指定标准 / 全量标准重建 embedding。
    - 适用场景：模型升级、向量维度变更等。

---

## 五、技术重点与难点提示

## 1. pgvector + 1024维向量的存储与性能

- 难点：4096 维向量单行体积大，写入频繁时对 IO 和 TOAST 存储有压力。
- ~~解决策略：~~
    - ~~将 embedding 拆分至标准向量表 standardvectorstore，而不是直接塞在 datastandard。~~
    - ~~使用 HNSW 索引做 ANN，结合合适的 m、ef_construction 和查询时的 ef_search。~~
    - ~~注意 PostgreSQL 配置（shared_buffers、work_mem）与磁盘 IO 监控。~~
- 实际部署时发现，postgres HNSW索引不支持超过2000dim向量索引。所以，向量维度退回1024维（20260214）

## 2. 版本与 is_latest 一致性

- 难点：发布流程中，保证同一 code 始终只有一个 is_latest=true 的发布版本。
- 解决策略：
    - 在发布 API 内部使用事务：
        - 将同 code 所有记录 is_latest=false；
        - 将当前版本 status=1, is_latest=true；
    - 可增加 check 逻辑或唯一索引（例如在已发布记录上加部分索引）。

## 3. i18n 查询复杂度

- 难点：频繁 LEFT JOIN standardi18n 可能引入一定性能损耗，特别是列表查询。
- 建议：
    - 列表接口可以只返回默认语言，详情接口再做 i18n JOIN；
    - 或对标准表加冗余字段，例如 name_en 简单缓存部分关键语言，但仍以 i18n 表为准。
    - 加索引：refid + language + fieldname，减少 JOIN 代价。

## 4. Embedding 生成与异步任务

- 难点：标准变更频繁时，如何保证 embedding 与标准内容一致，并控制延迟。
- 建议：
    - 所有涉及 name/description/关键属性变动的更新，都触发「embedding 重建任务」。
    - 使用 BackgroundTasks 起步，随着规模增大可迁移到 Celery/RabbitMQ 等队列方案。
    - 接口层建议返回「已接受任务」状态，而不是同步等待 embedding 完成。

## **5. 多语言与低代码友好**

- 主表中文列直接支持低代码绑定。
- i18n表仅在需要非中文时JOIN，避免默认查询开销。

## **6. 通用约束**

- 禁止SELECT *，必须显式列出字段。
- 使用SQLAlchemy异步 + pgvector支持。
- 变更操作建议记录审计日志。