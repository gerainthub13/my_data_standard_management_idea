import uuid
from datetime import datetime
from enum import IntEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.validators import ensure_valid_display_name, ensure_valid_standard_code, normalize_language


# 标准状态枚举
class StandardStatus(IntEnum):
    draft = 0
    published = 1
    retired = 2
    deprecated = 3
    other = 4


# 分类 Schema
class CategoryBase(BaseModel):
    name: str = Field(..., max_length=200)
    parent_id: int | None = None
    category_type: Literal["system", "custom"] = "custom"
    scope: Literal["standard", "metric", "bizdict"] = "standard"

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return ensure_valid_display_name(value, "分类名称")

    @field_validator("parent_id")
    @classmethod
    def normalize_parent_id(cls, value: int | None) -> int | None:
        # 兼容前端传 0 的情况，统一转为 None
        if value == 0:
            return None
        return value


class CategoryCreate(CategoryBase):
    category_type: Literal["custom"] = "custom"


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    parent_id: int | None = None
    category_type: Literal["custom"] | None = None
    scope: Literal["standard", "metric", "bizdict"] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return ensure_valid_display_name(value, "分类名称")

    @field_validator("parent_id")
    @classmethod
    def normalize_parent_id(cls, value: int | None) -> int | None:
        if value == 0:
            return None
        return value


class CategoryOut(CategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime
    last_update_user: str

    model_config = ConfigDict(from_attributes=True)


class CategoryListOut(BaseModel):
    items: list[CategoryOut]
    total: int
    page: int
    page_size: int


# i18n 项
class I18nItem(BaseModel):
    fieldname: Literal["name", "description"] = Field(..., examples=["name", "description"])
    language: str = Field(..., examples=["en", "ja"])
    content: str = Field(..., min_length=1)

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        return normalize_language(value)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("翻译内容不能为空")
        return normalized


# 标准基础字段
class StandardBase(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=200)
    description: str | None = None
    category_id: int | None = None
    extattributes: dict[str, Any] | None = None

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return ensure_valid_standard_code(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return ensure_valid_display_name(value, "数据标准名称")

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("category_id")
    @classmethod
    def normalize_category_id(cls, value: int | None) -> int | None:
        if value == 0:
            return None
        return value


class StandardCreate(StandardBase):
    translations: list[I18nItem] | None = None

    @model_validator(mode="after")
    def validate_unique_translations(self) -> "StandardCreate":
        if not self.translations:
            return self
        seen: set[tuple[str, str]] = set()
        duplicates: list[str] = []
        for item in self.translations:
            key = (item.fieldname, item.language)
            if key in seen:
                duplicates.append(f"{item.fieldname}:{item.language}")
            seen.add(key)
        if duplicates:
            joined = "、".join(sorted(set(duplicates)))
            raise ValueError(f"translations 存在重复字段语言组合：{joined}")
        return self


class StandardUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    category_id: int | None = None
    extattributes: dict[str, Any] | None = None
    translations: list[I18nItem] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return ensure_valid_display_name(value, "数据标准名称")

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("category_id")
    @classmethod
    def normalize_category_id(cls, value: int | None) -> int | None:
        if value == 0:
            return None
        return value

    @model_validator(mode="after")
    def validate_unique_translations(self) -> "StandardUpdate":
        if not self.translations:
            return self
        seen: set[tuple[str, str]] = set()
        duplicates: list[str] = []
        for item in self.translations:
            key = (item.fieldname, item.language)
            if key in seen:
                duplicates.append(f"{item.fieldname}:{item.language}")
            seen.add(key)
        if duplicates:
            joined = "、".join(sorted(set(duplicates)))
            raise ValueError(f"translations 存在重复字段语言组合：{joined}")
        return self


# 状态更新入参
class StandardStatusUpdate(BaseModel):
    status: StandardStatus


class StandardOut(StandardBase):
    id: uuid.UUID
    status: StandardStatus
    version: int
    is_latest: bool
    created_at: datetime
    updated_at: datetime
    last_update_user: str

    model_config = ConfigDict(from_attributes=True)


class StandardDetailOut(StandardOut):
    translations: list[I18nItem] | None = None
    code_list: "CodeListSummary | None" = None


# 列表分页返回
class StandardListOut(BaseModel):
    items: list[StandardOut]
    total: int
    page: int
    page_size: int


class StandardReadonlyItem(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    status: StandardStatus
    version: int
    is_latest: bool
    created_at: datetime
    updated_at: datetime
    last_update_user: str
    has_code_list: bool


class StandardReadonlyListOut(BaseModel):
    items: list[StandardReadonlyItem]
    total: int
    page: int
    page_size: int


class StandardReadonlyStatusCount(BaseModel):
    draft: int = 0
    published: int = 0
    retired: int = 0
    deprecated: int = 0
    other: int = 0


class StandardReadonlyStatusStatsOut(BaseModel):
    total: int
    counts: StandardReadonlyStatusCount


# 码表子项基础
class CodeItemBase(BaseModel):
    item_code: str = Field(..., max_length=100)
    item_name: str = Field(..., max_length=200)
    meaning: str | None = None
    sort_order: int = Field(default=0, ge=0)

    @field_validator("item_code")
    @classmethod
    def validate_item_code(cls, value: str) -> str:
        return ensure_valid_standard_code(value)

    @field_validator("item_name")
    @classmethod
    def validate_item_name(cls, value: str) -> str:
        return ensure_valid_display_name(value, "标准代码名称")

    @field_validator("meaning")
    @classmethod
    def normalize_meaning(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class CodeItemOut(CodeItemBase):
    id: uuid.UUID
    list_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    last_update_user: str

    model_config = ConfigDict(from_attributes=True)


class CodeListBase(BaseModel):
    list_code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=200)
    purpose: str | None = None

    @field_validator("list_code")
    @classmethod
    def validate_list_code(cls, value: str) -> str:
        return ensure_valid_standard_code(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return ensure_valid_display_name(value, "标准代码列表名称")

    @field_validator("purpose")
    @classmethod
    def normalize_purpose(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class CodeListCreate(CodeListBase):
    items: list[CodeItemBase] | None = None

    @model_validator(mode="after")
    def validate_unique_item_code(self) -> "CodeListCreate":
        if not self.items:
            return self
        seen: set[str] = set()
        duplicates: list[str] = []
        for item in self.items:
            key = item.item_code
            if key in seen:
                duplicates.append(key)
            seen.add(key)
        if duplicates:
            joined = "、".join(sorted(set(duplicates)))
            raise ValueError(f"items 存在重复 item_code：{joined}")
        return self


class CodeListUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    purpose: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return ensure_valid_display_name(value, "标准代码列表名称")

    @field_validator("purpose")
    @classmethod
    def normalize_purpose(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class CodeListOut(CodeListBase):
    id: uuid.UUID
    status: StandardStatus
    version: int
    is_latest: bool
    created_at: datetime
    updated_at: datetime
    last_update_user: str

    model_config = ConfigDict(from_attributes=True)


class CodeListDetailOut(CodeListOut):
    items: list[CodeItemOut] | None = None


class CodeListListOut(BaseModel):
    items: list[CodeListOut]
    total: int
    page: int
    page_size: int


class CodeListStatusUpdate(BaseModel):
    status: StandardStatus


class CodeListItemsReplaceRequest(BaseModel):
    items: list[CodeItemBase] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_item_code(self) -> "CodeListItemsReplaceRequest":
        seen: set[str] = set()
        duplicates: list[str] = []
        for item in self.items:
            key = item.item_code
            if key in seen:
                duplicates.append(key)
            seen.add(key)
        if duplicates:
            joined = "、".join(sorted(set(duplicates)))
            raise ValueError(f"items 存在重复 item_code：{joined}")
        return self


class CodeListItemListOut(BaseModel):
    items: list[CodeItemOut]
    total: int
    page: int
    page_size: int


class CodeListKeywordSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=20, ge=1, le=200)
    only_bindable: bool = False

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query 不能为空")
        return normalized


class CodeListKeywordSearchItem(BaseModel):
    id: uuid.UUID
    list_code: str
    name: str
    purpose: str | None
    version: int
    status: int
    is_latest: bool
    matched_by: list[str]


class CodeListKeywordSearchResponse(BaseModel):
    items: list[CodeListKeywordSearchItem]


class CodeListSummary(BaseModel):
    id: uuid.UUID
    list_code: str
    name: str
    version: int
    status: StandardStatus
    is_latest: bool

    model_config = ConfigDict(from_attributes=True)


class StandardCodeBindingUpdate(BaseModel):
    code_list_id: uuid.UUID | None = None


class StandardCodeBindingOut(BaseModel):
    standard_id: uuid.UUID
    code_list_id: uuid.UUID | None = None
    code_list: CodeListSummary | None = None


class CodeListBindingStandardItem(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    version: int
    status: int
    is_latest: bool

    model_config = ConfigDict(from_attributes=True)


class CodeListBindingListOut(BaseModel):
    items: list[CodeListBindingStandardItem]
    total: int
    page: int
    page_size: int


# 搜索请求
class StandardSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    lang: str = "zh"
    use_vector: bool = True
    top_k: int = Field(default=10, ge=1, le=100)
    status: StandardStatus | None = Field(default=StandardStatus.published)
    is_latest: bool | None = Field(default=True)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query 不能为空")
        return normalized

    @field_validator("lang")
    @classmethod
    def validate_lang(cls, value: str) -> str:
        return normalize_language(value)


# 搜索项
class StandardSearchItem(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    version: int
    status: int
    is_latest: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    has_code_list: bool = False
    score: float | None = None


class StandardSearchResponse(BaseModel):
    items: list[StandardSearchItem]


# 关系创建
class RelationCreate(BaseModel):
    targetid: str = Field(..., min_length=1, max_length=100)
    targetver: str | None = Field(default=None, max_length=20)
    reltype: Literal["parentchild", "maptotable", "standardlink", "modelmapping"]
    targettype: Literal["internalstd", "externalstd", "table", "column"]
    relstatus: int = Field(default=0, ge=0, le=1)

    @field_validator("targetid")
    @classmethod
    def validate_targetid(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("targetid 不能为空")
        return normalized

    @field_validator("targetver")
    @classmethod
    def normalize_targetver(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class RelationOut(RelationCreate):
    id: int
    sourceid: str
    sourcever: str | None = None

    model_config = ConfigDict(from_attributes=True)


# Embedding 重建请求
class EmbeddingRebuildRequest(BaseModel):
    refids: list[uuid.UUID] | None = None
    lang: str | None = None

    @field_validator("lang")
    @classmethod
    def validate_lang(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_language(value)


class EmbeddingRebuildOut(BaseModel):
    accepted: int
    skipped: int
    warnings: list[str] = Field(default_factory=list)
