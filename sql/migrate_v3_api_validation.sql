-- DSMS v3 迁移脚本（兼容已有库）
-- 用途：
-- 1) 补齐软删除字段与审计字段
-- 2) 增加关键组合唯一约束/索引
-- 3) 对齐 PRD v3 的 API 校验前提

-- category 补字段
ALTER TABLE category ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE category ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now();
ALTER TABLE category ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now();
ALTER TABLE category ADD COLUMN IF NOT EXISTS last_update_user VARCHAR(100) NOT NULL DEFAULT 'api';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_category_type_valid'
    ) THEN
        ALTER TABLE category
        ADD CONSTRAINT ck_category_type_valid CHECK (category_type IN ('system', 'custom'));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_category_scope_valid'
    ) THEN
        ALTER TABLE category
        ADD CONSTRAINT ck_category_scope_valid CHECK (scope IN ('standard', 'metric', 'bizdict'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_category_parent ON category (parent_id);
CREATE INDEX IF NOT EXISTS ix_category_scope ON category (scope);
CREATE INDEX IF NOT EXISTS ix_category_is_deleted ON category (is_deleted);
DROP INDEX IF EXISTS uq_category_name_active;
CREATE UNIQUE INDEX IF NOT EXISTS uq_category_name_parent_active ON category (name, COALESCE(parent_id, 0)) WHERE is_deleted = FALSE;

-- datastandard 补字段
ALTER TABLE datastandard ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE datastandard ADD COLUMN IF NOT EXISTS last_update_user VARCHAR(100) NOT NULL DEFAULT 'api';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_datastandard_status_range'
    ) THEN
        ALTER TABLE datastandard
        ADD CONSTRAINT ck_datastandard_status_range CHECK (status >= 0 AND status <= 4);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_datastandard_deleted ON datastandard (is_deleted);
CREATE UNIQUE INDEX IF NOT EXISTS uq_datastandard_code_version_active ON datastandard (code, version) WHERE is_deleted = FALSE;
CREATE UNIQUE INDEX IF NOT EXISTS uq_datastandard_code_published_active ON datastandard (code)
WHERE is_deleted = FALSE AND status = 1 AND is_latest = TRUE;

-- standardrelation 唯一约束
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_standardrelation_unique'
    ) THEN
        ALTER TABLE standardrelation
        ADD CONSTRAINT uq_standardrelation_unique UNIQUE (sourceid, targetid, targetver, reltype, targettype);
    END IF;
END $$;
