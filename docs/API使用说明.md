# DSMS API 使用说明（MVP）

## 1. 统一错误返回格式

当请求参数或业务数据不满足校验规则时，接口返回如下结构：

```json
{
  "success": false,
  "code": "REQUEST_VALIDATION_ERROR",
  "message": "请求参数校验失败",
  "errors": [
    {
      "field": "name",
      "message": "分类名称不能以数字开头",
      "type": "value_error"
    }
  ],
  "warnings": [
    "请根据 errors 字段修正请求参数后重试。"
  ]
}
```

字段说明：

- `code`：错误码，便于前端和低代码平台按类型处理。
- `message`：用户可读的错误摘要。
- `errors`：逐字段错误详情。
- `warnings`：非阻断或引导性提示。

## 2. 关键校验规则

### 2.1 名称非法字符校验（分类名称、数据标准名称）

名称规则：

- 不能为空；
- 不能以数字开头；
- 仅允许：中文、英文字母、数字、空格、中划线 `-`、括号 `()（）`、点号 `.`；
- 禁止 `_ % # ? ! * & ^ $ @ ~ ' " ...` 等符号。

### 2.2 关键字段组合唯一

- 分类：生效数据（`is_deleted=false`）中“同父节点下 `name` 必须唯一”；
- 数据标准：生效数据中 `code + version` 必须唯一；
- 码表主表：生效数据中 `list_code + version` 必须唯一；
- 码表子项：同码表下生效数据中 `item_code` 必须唯一；
- 标准绑定码表：同一标准仅允许一个生效绑定；
- 关系：`sourceid + targetid + targetver + reltype + targettype` 组合唯一。

### 2.3 软删除规则

- 分类删除：仅将 `is_deleted=true`，不物理删除；
- 数据标准删除：仅将 `is_deleted=true` 且 `status=3`，不物理删除；
- 码表删除：仅将 `is_deleted=true` 且 `status=3`，不物理删除；
- 已软删除数据默认不会出现在查询结果中。

## 3. 分类 API 使用建议

- `GET /api/v1/categories`
  - 支持 `id` 精确查询；
  - 默认未传 `id` 时需要 `keyword`，也可通过 `allow_empty_keyword=true` 开启无关键词分页查询；
  - 返回结构包含 `total/page/page_size/items`。

- `POST /api/v1/categories`
  - 创建前会校验：
  - 名称非法字符
  - `parent_id` 是否存在
  - 生效分类名称唯一

## 4. 数据标准 API 使用建议

- `POST /api/v1/standards`
  - 创建草稿版（`status=0, version=1`）；
  - 创建前校验：
  - 标准名称非法字符
  - `category_id` 存在性
  - `code+version` 唯一
  - 成功后异步触发 embedding 重建。

- `POST /api/v1/standards/{id}/revision`
  - 自动按同 `code` 的最大版本号 `+1` 创建新版本。

- `PATCH /api/v1/standards/{id}/publish`
  - 发布后自动保证同 `code` 仅一个 `is_latest=true` 且 `status=1`。

- `GET /api/v1/standards/readonly/list`
  - 只读清单接口，前端默认可传 `status=1,is_latest=true,page_size=10`；
  - 支持 `keyword` 关键词筛选；
  - 支持状态过滤：`status=0/1/2/3/4`，可配合 `is_latest=true/false`；
  - 支持排序参数：`order_by=updated_at|created_at|code|name|version`、`order_dir=asc|desc`；
  - 返回字段包含 `has_code_list`，用于前端展示“是否含有标准代码”。

- `GET /api/v1/standards/readonly/stats`
  - 返回只读清单状态统计（`draft/published/retired/deprecated/other`）；
  - 支持 `keyword` 和 `is_latest` 条件过滤；
  - 用于只读 UI 顶部状态统计面板。

## 5. Embedding 重建接口

- `POST /api/v1/embeddings/rebuild`
  - 指定 `refids` 时，返回 `accepted`/`skipped`；
  - 无效或已删除的标准 ID 会被跳过，并在 `warnings` 中提示。

## 5.1 搜索返回字段补充

- `POST /api/v1/standards/search`
  - 在原有字段基础上，新增：
  - `created_at`
  - `updated_at`
  - `has_code_list`
  - 便于只读 UI 直接渲染清单行。
  - 支持可选过滤：
  - `status`（默认 `1`）
  - `is_latest`（默认 `true`）
  - 用于关键词搜索与向量搜索按状态一致过滤。

## 6. 标准代码（码表）API 使用建议

- `POST /api/v1/code-lists`
  - 创建草稿码表（`status=0, version=1`）；
  - 可一次性提交子项 `items`。

- `POST /api/v1/code-lists/search`
  - 关键词检索码表；
  - 同时搜索主表字段（`list_code/name/purpose`）与子项字段（`item_code/item_name/meaning`）；
  - 支持 `only_bindable=true` 仅返回已发布且最新版本。

- `PUT /api/v1/code-lists/{id}/items`
  - 批量覆盖更新子项；
  - 仅草稿码表可编辑；
  - 未提交的旧子项会被逻辑删除。

- `PATCH /api/v1/code-lists/{id}/publish`
  - 发布后自动保证同 `list_code` 仅一个 `is_latest=true` 且 `status=1`。

- `POST /api/v1/code-lists/{id}/revision`
  - 自动复制当前版本主表与生效子项，生成新草稿版本。

## 7. 标准与码表绑定 API

- `GET /api/v1/standards/{id}/code-list`
  - 查询标准当前绑定的码表摘要（未绑定返回空）。

- `PUT /api/v1/standards/{id}/code-list`
  - 设置或解绑标准码表（`code_list_id=null` 为解绑）；
  - 仅允许绑定已发布且最新的码表版本。

- `GET /api/v1/code-lists/{id}/bindings`
  - 查询码表被哪些标准引用；
  - 支持 `published_only=true` 仅返回已发布标准。

- `GET /api/v1/standards/{id}`
  - 详情响应增加 `code_list` 字段，用于返回当前绑定码表摘要（无绑定则为 `null`）。
