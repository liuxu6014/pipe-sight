-- pipeline_news.news 全量字段/表备注补充
-- 已审计 news schema 全部业务对象；本文件只补遗漏 COMMENT，不改结构、索引、分区或数据。
-- 执行目标：pipeline_news / news schema

\set ON_ERROR_STOP on

BEGIN;

-- 业务表遗漏字段
COMMENT ON COLUMN news.hp_data_source.category IS
    '数据源分类标识；用于区分来源类别';
COMMENT ON COLUMN news.hp_topic.return_flag IS
    '分类处理返回标志；用于控制分类处理器行为';
COMMENT ON COLUMN news.hp_topic.update_by IS
    '分类最后修改人';
COMMENT ON COLUMN news.hp_news.filter_result IS
    '新闻过滤处理结果或过滤说明';
COMMENT ON COLUMN news.hp_news.is_top IS
    '是否置顶标识';
COMMENT ON COLUMN news.hp_news.uuid IS
    '上游业务新闻标识；不保证唯一';

-- 父表新增/遗漏字段的列备注
COMMENT ON COLUMN news.hp_news.prompt_trace_id IS
    '提示词处理血缘批次 ULID；详细使用记录见 news.news_prompt_usage';

-- 既有分区需要显式补列备注；列描述不会可靠地从父表回填到已存在分区。
DO $$
DECLARE
    partition_name text;
BEGIN
    FOR partition_name IN
        SELECT c.relname
        FROM pg_inherits i
        JOIN pg_class parent ON parent.oid = i.inhparent
        JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
        JOIN pg_class c ON c.oid = i.inhrelid
        JOIN pg_namespace child_ns ON child_ns.oid = c.relnamespace
        WHERE parent_ns.nspname = 'news'
          AND child_ns.nspname = 'news'
          AND parent.relname = 'hp_news'
          AND c.relkind = 'r'
    LOOP
        EXECUTE format(
            'COMMENT ON COLUMN news.%I.prompt_trace_id IS %L',
            partition_name,
            '提示词处理血缘批次 ULID；详细使用记录见 news.news_prompt_usage'
        );
        EXECUTE format(
            'COMMENT ON COLUMN news.%I.filter_result IS %L',
            partition_name,
            '新闻过滤处理结果或过滤说明'
        );
        EXECUTE format(
            'COMMENT ON COLUMN news.%I.is_top IS %L',
            partition_name,
            '是否置顶标识'
        );
        EXECUTE format(
            'COMMENT ON COLUMN news.%I.uuid IS %L',
            partition_name,
            '上游业务新闻标识；不保证唯一'
        );
    END LOOP;
END
$$;

-- 表/视图级备注：交接和 \dt+ 只能看到有对象说明的对象。
COMMENT ON TABLE news.hp_data_source IS
    '新闻来源、媒体和数据源主数据';
COMMENT ON TABLE news.hp_domain IS
    '新闻领域定义及领域处理配置';
COMMENT ON TABLE news.hp_topic IS
    '新闻分类定义和分类树';
COMMENT ON TABLE news.act_domain_topic_actions IS
    '领域与分类关系及分类标准提示词绑定';
COMMENT ON TABLE news.sys_prompt_version IS
    '不可变提示词版本、发布状态和单父派生关系';
COMMENT ON TABLE news.news_prompt_usage IS
    '成功入库新闻实际使用的提示词版本、处理阶段和顺序';
COMMENT ON TABLE news.news_embedding IS
    '新闻 1024 维向量、过滤投影和轻量检索快照';
COMMENT ON VIEW news.sys_domain IS
    '领域配置兼容视图；数据直接来自 news.hp_domain，不复制数据';

-- 新闻分区对象级备注
DO $$
DECLARE
    partition_name text;
BEGIN
    FOR partition_name IN
        SELECT c.relname
        FROM pg_inherits i
        JOIN pg_class parent ON parent.oid = i.inhparent
        JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
        JOIN pg_class c ON c.oid = i.inhrelid
        JOIN pg_namespace child_ns ON child_ns.oid = c.relnamespace
        WHERE parent_ns.nspname = 'news'
          AND child_ns.nspname = 'news'
          AND parent.relname = 'hp_news'
          AND c.relkind = 'r'
    LOOP
        EXECUTE format(
            'COMMENT ON TABLE news.%I IS %L',
            partition_name,
            'hp_news 新闻月分区；分区键 create_time；表空间由热冷策略维护'
        );
    END LOOP;
END
$$;

-- pg_partman 管理表字段备注
COMMENT ON TABLE news.part_config IS
    'pg_partman 分区父表维护配置';
COMMENT ON COLUMN news.part_config.parent_table IS 'pg_partman 管理的分区父表';
COMMENT ON COLUMN news.part_config.control IS '分区控制列';
COMMENT ON COLUMN news.part_config.time_encoder IS '时间值编码函数';
COMMENT ON COLUMN news.part_config.time_decoder IS '时间值解码函数';
COMMENT ON COLUMN news.part_config.partition_interval IS '分区时间间隔';
COMMENT ON COLUMN news.part_config.partition_type IS '分区类型；native 表示 PostgreSQL 原生分区';
COMMENT ON COLUMN news.part_config.premake IS '提前创建的未来分区数量';
COMMENT ON COLUMN news.part_config.automatic_maintenance IS '是否启用自动分区维护';
COMMENT ON COLUMN news.part_config.template_table IS '分区模板表';
COMMENT ON COLUMN news.part_config.retention IS '分区保留策略';
COMMENT ON COLUMN news.part_config.retention_schema IS '保留分区迁移目标 Schema';
COMMENT ON COLUMN news.part_config.retention_keep_index IS '保留分区索引标志';
COMMENT ON COLUMN news.part_config.retention_keep_table IS '保留分区表标志';
COMMENT ON COLUMN news.part_config.epoch IS '控制列 Epoch 解释方式';
COMMENT ON COLUMN news.part_config.constraint_cols IS '分区约束列集合';
COMMENT ON COLUMN news.part_config.optimize_constraint IS '约束优化周期';
COMMENT ON COLUMN news.part_config.infinite_time_partitions IS '是否允许无限时间分区';
COMMENT ON COLUMN news.part_config.datetime_string IS '分区日期格式';
COMMENT ON COLUMN news.part_config.jobmon IS '是否启用 pg_jobmon 监控';
COMMENT ON COLUMN news.part_config.sub_partition_set_full IS '子分区集合完整性标志';
COMMENT ON COLUMN news.part_config.undo_in_progress IS '是否正在执行撤销分区操作';
COMMENT ON COLUMN news.part_config.inherit_privileges IS '新分区是否继承权限';
COMMENT ON COLUMN news.part_config.constraint_valid IS '分区约束是否有效';
COMMENT ON COLUMN news.part_config.ignore_default_data IS '是否忽略默认分区数据';
COMMENT ON COLUMN news.part_config.date_trunc_interval IS '日期截断间隔';
COMMENT ON COLUMN news.part_config.maintenance_order IS '分区维护顺序';
COMMENT ON COLUMN news.part_config.retention_keep_publication IS '保留分区发布关系标志';
COMMENT ON COLUMN news.part_config.maintenance_last_run IS '最近一次分区维护时间';
COMMENT ON COLUMN news.part_config.async_partitioning_in_progress IS '异步分区操作状态';

COMMENT ON TABLE news.part_config_sub IS
    'pg_partman 子分区维护配置';
COMMENT ON COLUMN news.part_config_sub.sub_parent IS '子分区父表';
COMMENT ON COLUMN news.part_config_sub.sub_control IS '子分区控制列';
COMMENT ON COLUMN news.part_config_sub.sub_time_encoder IS '子分区时间值编码函数';
COMMENT ON COLUMN news.part_config_sub.sub_time_decoder IS '子分区时间值解码函数';
COMMENT ON COLUMN news.part_config_sub.sub_partition_interval IS '子分区时间间隔';
COMMENT ON COLUMN news.part_config_sub.sub_partition_type IS '子分区类型';
COMMENT ON COLUMN news.part_config_sub.sub_premake IS '子分区提前创建数量';
COMMENT ON COLUMN news.part_config_sub.sub_automatic_maintenance IS '是否启用子分区自动维护';
COMMENT ON COLUMN news.part_config_sub.sub_template_table IS '子分区模板表';
COMMENT ON COLUMN news.part_config_sub.sub_retention IS '子分区保留策略';
COMMENT ON COLUMN news.part_config_sub.sub_retention_schema IS '子分区保留目标 Schema';
COMMENT ON COLUMN news.part_config_sub.sub_retention_keep_index IS '保留子分区索引标志';
COMMENT ON COLUMN news.part_config_sub.sub_retention_keep_table IS '保留子分区表标志';
COMMENT ON COLUMN news.part_config_sub.sub_epoch IS '子分区 Epoch 解释方式';
COMMENT ON COLUMN news.part_config_sub.sub_constraint_cols IS '子分区约束列集合';
COMMENT ON COLUMN news.part_config_sub.sub_optimize_constraint IS '子分区约束优化周期';
COMMENT ON COLUMN news.part_config_sub.sub_infinite_time_partitions IS '是否允许无限子分区';
COMMENT ON COLUMN news.part_config_sub.sub_jobmon IS '是否启用子分区任务监控';
COMMENT ON COLUMN news.part_config_sub.sub_inherit_privileges IS '子分区是否继承权限';
COMMENT ON COLUMN news.part_config_sub.sub_constraint_valid IS '子分区约束是否有效';
COMMENT ON COLUMN news.part_config_sub.sub_ignore_default_data IS '是否忽略子分区默认数据';
COMMENT ON COLUMN news.part_config_sub.sub_default_table IS '是否为子分区默认表';
COMMENT ON COLUMN news.part_config_sub.sub_date_trunc_interval IS '子分区日期截断间隔';
COMMENT ON COLUMN news.part_config_sub.sub_maintenance_order IS '子分区维护顺序';
COMMENT ON COLUMN news.part_config_sub.sub_retention_keep_publication IS '保留子分区发布关系标志';
COMMENT ON COLUMN news.part_config_sub.sub_control_not_null IS '子分区控制列非空标志';

-- 权限审计 View
COMMENT ON VIEW news.table_privs IS
    '业务 Schema 表权限审计视图';
COMMENT ON COLUMN news.table_privs.grantor IS '权限授予者';
COMMENT ON COLUMN news.table_privs.grantee IS '权限受益角色';
COMMENT ON COLUMN news.table_privs.table_schema IS '对象所在 Schema';
COMMENT ON COLUMN news.table_privs.table_name IS '被授权表名称';
COMMENT ON COLUMN news.table_privs.privilege_type IS '权限类型，例如 SELECT、INSERT、UPDATE、DELETE';

COMMIT;
