import uuid
from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db import Base


# 分类表
class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("category.id"), nullable=True)
    category_type: Mapped[str] = mapped_column(String(20), nullable=False, default="system")
    scope: Mapped[str] = mapped_column(String(30), nullable=False, default="standard")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_update_user: Mapped[str] = mapped_column(String(100), nullable=False, default="api")

    # 自引用父子关系
    parent = relationship("Category", remote_side=[id], backref="children")

    __table_args__ = (
        CheckConstraint("category_type in ('system','custom')", name="ck_category_type_valid"),
        CheckConstraint("scope in ('standard','metric','bizdict')", name="ck_category_scope_valid"),
        Index("ix_category_parent", "parent_id"),
        Index("ix_category_scope", "scope"),
        Index("ix_category_is_deleted", "is_deleted"),
        Index(
            "uq_category_name_parent_active",
            "name",
            text("COALESCE(parent_id, 0)"),
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )


# 数据标准主表
class DataStandard(Base):
    __tablename__ = "datastandard"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    category_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("category.id"), nullable=True)
    extattributes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_update_user: Mapped[str] = mapped_column(String(100), nullable=False, default="api")

    # 关联关系
    category = relationship("Category")
    i18n = relationship("StandardI18n", back_populates="standard", cascade="all, delete-orphan")
    vectors = relationship("StandardVectorStore", back_populates="standard", cascade="all, delete-orphan")
    code_links = relationship("DataStandardCodeLink", back_populates="standard", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_datastandard_code", "code"),
        Index("ix_datastandard_status", "status"),
        Index("ix_datastandard_latest", "is_latest"),
        Index("ix_datastandard_deleted", "is_deleted"),
        Index("ix_datastandard_category", "category_id"),
        CheckConstraint("version >= 1", name="ck_datastandard_version_positive"),
        CheckConstraint("status >= 0 and status <= 4", name="ck_datastandard_status_range"),
        Index(
            "uq_datastandard_code_version_active",
            "code",
            "version",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index(
            "uq_datastandard_code_published_active",
            "code",
            unique=True,
            postgresql_where=text("is_deleted = false AND status = 1 AND is_latest = true"),
        ),
    )


# 标准代码列表主表（码表）
class StandardCodeList(Base):
    __tablename__ = "standardcodelist"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    list_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_update_user: Mapped[str] = mapped_column(String(100), nullable=False, default="api")

    items = relationship("StandardCodeItem", back_populates="code_list", cascade="all, delete-orphan")
    links = relationship("DataStandardCodeLink", back_populates="code_list", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_standardcodelist_code", "list_code"),
        Index("ix_standardcodelist_status", "status"),
        Index("ix_standardcodelist_latest", "is_latest"),
        Index("ix_standardcodelist_deleted", "is_deleted"),
        CheckConstraint("version >= 1", name="ck_standardcodelist_version_positive"),
        CheckConstraint("status >= 0 and status <= 4", name="ck_standardcodelist_status_range"),
        Index(
            "uq_standardcodelist_code_version_active",
            "list_code",
            "version",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index(
            "uq_standardcodelist_code_published_active",
            "list_code",
            unique=True,
            postgresql_where=text("is_deleted = false AND status = 1 AND is_latest = true"),
        ),
    )


# 标准代码子表（码值）
class StandardCodeItem(Base):
    __tablename__ = "standardcodeitem"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    list_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("standardcodelist.id"), nullable=False)
    item_code: Mapped[str] = mapped_column(String(100), nullable=False)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_update_user: Mapped[str] = mapped_column(String(100), nullable=False, default="api")

    code_list = relationship("StandardCodeList", back_populates="items")

    __table_args__ = (
        Index("ix_standardcodeitem_list_deleted", "list_id", "is_deleted"),
        Index("ix_standardcodeitem_name", "item_name"),
        Index(
            "uq_standardcodeitem_list_code_active",
            "list_id",
            "item_code",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )


# 数据标准与码表绑定关系表（每个标准最多一个生效绑定）
class DataStandardCodeLink(Base):
    __tablename__ = "datastandardcodelink"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    standard_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datastandard.id"), nullable=False)
    code_list_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("standardcodelist.id"), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_update_user: Mapped[str] = mapped_column(String(100), nullable=False, default="api")

    standard = relationship("DataStandard", back_populates="code_links")
    code_list = relationship("StandardCodeList", back_populates="links")

    __table_args__ = (
        Index("ix_datastandardcodelink_standard", "standard_id"),
        Index("ix_datastandardcodelink_codelist", "code_list_id"),
        Index(
            "uq_datastandardcodelink_standard_active",
            "standard_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )


# 多语言表
class StandardI18n(Base):
    __tablename__ = "standardi18n"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    refid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datastandard.id"), nullable=False)
    fieldname: Mapped[str] = mapped_column(String(50), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    standard = relationship("DataStandard", back_populates="i18n")

    __table_args__ = (
        UniqueConstraint("refid", "fieldname", "language", name="uq_standard_i18n_ref_field_lang"),
        Index("ix_standard_i18n_ref_lang", "refid", "language"),
    )


# 向量存储表（pgvector）
class StandardVectorStore(Base):
    __tablename__ = "standardvectorstore"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    refid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datastandard.id"), nullable=False)
    lang: Mapped[str] = mapped_column(String(10), nullable=False)
    modelname: Mapped[str] = mapped_column(String(100), nullable=False)
    sourcecontent: Mapped[str] = mapped_column(Text, nullable=False)
    # 维度受索引能力限制，当前固定为 1024（<=2000）
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)

    standard = relationship("DataStandard", back_populates="vectors")

    __table_args__ = (
        Index("ix_std_vector_ref_lang", "refid", "lang"),
        UniqueConstraint("refid", "lang", "modelname", name="uq_std_vector_ref_lang_model"),
    )


# 标准关系表（MVP 预留结构）
class StandardRelation(Base):
    __tablename__ = "standardrelation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sourceid: Mapped[str] = mapped_column(String(100), nullable=False)
    sourcever: Mapped[str | None] = mapped_column(String(20), nullable=True)
    targetid: Mapped[str] = mapped_column(String(100), nullable=False)
    targetver: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reltype: Mapped[str] = mapped_column(String(30), nullable=False)
    targettype: Mapped[str] = mapped_column(String(50), nullable=False)
    relstatus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_standardrelation_source", "sourceid"),
        Index("ix_standardrelation_target", "targetid"),
        UniqueConstraint("sourceid", "targetid", "targetver", "reltype", "targettype", name="uq_standardrelation_unique"),
    )
