-- 已废弃的 MySQL 提示词血缘设计草案。
-- 不得执行：项目数据库已转向 pipeline_news.news PostgreSQL。
-- 真实结构以 04_pipeline_news_pg_migration.sql 为准；保留本文件仅用于设计演进对照。

-- 1. 提示词版本表。
-- parent_prompt_version_id 可跨 prompt_key：既支持同一 Prompt 演进，也支持从通用 Prompt 派生新 Prompt。
CREATE TABLE sys_prompt_version (
    prompt_version_id         bigint NOT NULL AUTO_INCREMENT,
    parent_prompt_version_id  bigint DEFAULT NULL,
    prompt_key                varchar(150) NOT NULL,
    prompt_name               varchar(255) NOT NULL,
    prompt_type               varchar(50) NOT NULL,
    domain_id                 bigint DEFAULT NULL,
    category_id               bigint DEFAULT NULL,
    version_no                int NOT NULL,
    system_prompt             mediumtext NOT NULL,
    user_prompt               mediumtext NOT NULL,
    template_variables        json DEFAULT NULL,
    content_hash              char(64) NOT NULL,
    status                    enum('draft','published','retired') NOT NULL DEFAULT 'draft',
    derivation_note           varchar(1000) DEFAULT NULL,
    created_by                varchar(255) DEFAULT NULL,
    created_at                datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at                datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                              ON UPDATE CURRENT_TIMESTAMP(6),
    published_at              datetime(6) DEFAULT NULL,

    -- MySQL 无部分唯一索引。生成列保证同一 prompt_key 最多一个 published 版本。
    published_prompt_key varchar(150)
        GENERATED ALWAYS AS (
            CASE WHEN status = 'published' THEN prompt_key ELSE NULL END
        ) STORED,

    PRIMARY KEY (prompt_version_id),
    UNIQUE KEY uk_prompt_version (prompt_key, version_no),
    UNIQUE KEY uk_prompt_content (prompt_key, content_hash),
    UNIQUE KEY uk_prompt_single_published (published_prompt_key),
    KEY idx_prompt_parent (parent_prompt_version_id),
    KEY idx_prompt_lookup (prompt_type, domain_id, category_id, status),

    CONSTRAINT fk_prompt_parent
        FOREIGN KEY (parent_prompt_version_id)
        REFERENCES sys_prompt_version (prompt_version_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    CONSTRAINT ck_prompt_version_positive
        CHECK (version_no > 0),
    CONSTRAINT ck_prompt_key_not_blank
        CHECK (TRIM(prompt_key) <> ''),
    CONSTRAINT ck_prompt_name_not_blank
        CHECK (TRIM(prompt_name) <> ''),
    CONSTRAINT ck_prompt_type_not_blank
        CHECK (TRIM(prompt_type) <> ''),
    CONSTRAINT ck_prompt_content_hash_sha256
        CHECK (content_hash REGEXP '^[0-9a-f]{64}$'),
    CONSTRAINT ck_prompt_not_own_parent
        CHECK (
            parent_prompt_version_id IS NULL
            OR parent_prompt_version_id <> prompt_version_id
        ),
    CONSTRAINT ck_prompt_published_at
        CHECK (
            status <> 'published'
            OR published_at IS NOT NULL
        )
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='不可变提示词版本及单父派生关系';

-- 2. 新闻主表增加血缘入口。
-- 仅成功入库新闻记录完整血缘；ULID 在 Worker 开始处理该领域结果时生成。
ALTER TABLE hp_news
    ADD COLUMN prompt_trace_id char(26)
        CHARACTER SET ascii COLLATE ascii_bin
        DEFAULT NULL
        COMMENT '本次新闻处理使用的提示词血缘批次ULID',
    ADD UNIQUE KEY uk_hp_news_prompt_trace (prompt_trace_id);

-- 3. 新闻与 Prompt 版本的多对多使用关系。
-- sequence_no 表示该新闻处理过程中 Prompt 的使用顺序；同阶段可记录多个分类标准 Prompt。
CREATE TABLE news_prompt_usage (
    usage_id           bigint NOT NULL AUTO_INCREMENT,
    prompt_trace_id    char(26)
        CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    stage              varchar(50) NOT NULL,
    prompt_version_id  bigint NOT NULL,
    sequence_no        int NOT NULL,
    model_name         varchar(255) DEFAULT NULL,
    created_at         datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    PRIMARY KEY (usage_id),
    UNIQUE KEY uk_prompt_usage_sequence (prompt_trace_id, sequence_no),
    KEY idx_prompt_usage_version (prompt_version_id),
    KEY idx_prompt_usage_stage (stage, created_at),

    CONSTRAINT fk_prompt_usage_news_trace
        FOREIGN KEY (prompt_trace_id)
        REFERENCES hp_news (prompt_trace_id)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,
    CONSTRAINT fk_prompt_usage_version
        FOREIGN KEY (prompt_version_id)
        REFERENCES sys_prompt_version (prompt_version_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    CONSTRAINT ck_prompt_usage_stage_not_blank
        CHECK (TRIM(stage) <> ''),
    CONSTRAINT ck_prompt_usage_sequence_positive
        CHECK (sequence_no > 0)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='成功入库新闻使用过的提示词版本及顺序';

-- 4. 已发布、已退役或已被新闻引用的 Prompt 版本不可修改内容和派生身份。
-- 提示词表和新闻使用表创建完成后再创建本触发器。
DELIMITER $$
CREATE TRIGGER trg_prompt_version_immutable
BEFORE UPDATE ON sys_prompt_version
FOR EACH ROW
BEGIN
    IF OLD.status <> 'draft'
       OR EXISTS (
            SELECT 1
            FROM news_prompt_usage u
            WHERE u.prompt_version_id = OLD.prompt_version_id
            LIMIT 1
       ) THEN
        IF NOT (
            NEW.parent_prompt_version_id <=> OLD.parent_prompt_version_id
            AND NEW.prompt_key = OLD.prompt_key
            AND NEW.prompt_name = OLD.prompt_name
            AND NEW.prompt_type = OLD.prompt_type
            AND NEW.domain_id <=> OLD.domain_id
            AND NEW.category_id <=> OLD.category_id
            AND NEW.version_no = OLD.version_no
            AND NEW.system_prompt = OLD.system_prompt
            AND NEW.user_prompt = OLD.user_prompt
            AND NEW.template_variables <=> OLD.template_variables
            AND NEW.content_hash = OLD.content_hash
            AND NEW.derivation_note <=> OLD.derivation_note
        ) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Prompt version content and derivation are immutable after publish or use';
        END IF;
    END IF;
END$$
DELIMITER ;

-- 5. 分类关系表逐步从内嵌文本迁移到 Prompt 版本引用。

-- 迁移期保留 category_prompts；完成双读校验后必须删除旧文本列。
ALTER TABLE act_domain_topic_actions
    ADD COLUMN prompt_version_id bigint DEFAULT NULL
        COMMENT '分类标准提示词版本ID',
    ADD KEY idx_domain_topic_prompt_version (prompt_version_id),
    ADD CONSTRAINT fk_domain_topic_prompt_version
        FOREIGN KEY (prompt_version_id)
        REFERENCES sys_prompt_version (prompt_version_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT;


-- 发布流程必须在应用事务中额外校验：
-- 1. parent_prompt_version_id 指向存在且内容不可变的历史版本；
-- 2. 从父节点向上遍历不能再次遇到当前节点，防止长度大于 1 的派生环；
-- 3. parent 可跨 prompt_key，这是“派生新 Prompt”的设计能力，不是数据错误；
-- 4. 已被 news_prompt_usage 引用的版本禁止修改 system_prompt、user_prompt、content_hash；
-- 5. 修改内容必须 INSERT 新版本，不能覆盖历史版本。
