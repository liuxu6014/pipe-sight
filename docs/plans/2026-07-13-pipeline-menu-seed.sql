-- 管网科技情报平台菜单示例。
-- 使用方式：在若依“系统管理 / 菜单管理”中手工录入，或按当前数据库调整 ID 后执行。
-- 组件路径对应 frontend/src/views 下的 .vue 文件。

insert into sys_menu
(menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, update_by, update_time, remark)
values
(2000, '管网情报', 0, '5', 'pipeline', null, '', '', 1, 0, 'M', '0', '0', '', 'chart', 'admin', current_timestamp, '', null, '管网科技情报目录'),
(2001, '工作台', 2000, '1', 'dashboard', 'pipeline/dashboard/index', '', '', 1, 0, 'C', '0', '0', 'pipeline:dashboard:view', 'dashboard', 'admin', current_timestamp, '', null, '管网情报工作台'),
(2002, '情报检索', 2000, '2', 'intelligence', 'pipeline/intelligence/index', '', '', 1, 0, 'C', '0', '0', 'pipeline:intel:list', 'search', 'admin', current_timestamp, '', null, '新闻公众号论文统一检索'),
(2003, '情报详情', 2000, '3', 'intelligence/detail', 'pipeline/intelligence/detail', '', '', 1, 0, 'C', '1', '0', 'pipeline:intel:detail', 'list', 'admin', current_timestamp, '', null, '情报详情隐藏路由'),
(2004, '数据源管理', 2000, '4', 'source', 'pipeline/source/index', '', '', 1, 0, 'C', '0', '0', 'pipeline:source:list', 'link', 'admin', current_timestamp, '', null, '采集数据源管理'),
(2005, '采集任务', 2000, '5', 'task', 'pipeline/task/index', '', '', 1, 0, 'C', '0', '0', 'pipeline:task:list', 'job', 'admin', current_timestamp, '', null, '采集任务监控'),
(2006, '日报周报', 2000, '6', 'report', 'pipeline/report/index', '', '', 1, 0, 'C', '0', '0', 'pipeline:report:list', 'documentation', 'admin', current_timestamp, '', null, '日报周报与科研报告'),
(2008, '模板管理', 2000, '8', 'template', 'pipeline/template/index', '', '', 1, 0, 'C', '0', '0', 'pipeline:template:list', 'documentation', 'admin', current_timestamp, '', null, '科研报告和周期简报模板'),
(2009, '模型与 Prompt', 2000, '9', 'model', 'pipeline/model/index', '', '', 1, 0, 'C', '0', '0', 'ai:model:list', 'ai', 'admin', current_timestamp, '', null, '模型路由与 Prompt 版本管理');

insert into sys_menu
(menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, update_by, update_time, remark)
values
(2010, '情报查询', 2002, '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:intel:query', '#', 'admin', current_timestamp, '', null, ''),
(2011, '数据源配置', 2004, '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:source:edit', '#', 'admin', current_timestamp, '', null, ''),
(2012, '任务运行', 2005, '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:task:run', '#', 'admin', current_timestamp, '', null, ''),
(2013, '报告导出', 2006, '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:report:export', '#', 'admin', current_timestamp, '', null, ''),
(2014, '报告发布', 2006, '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:report:publish', '#', 'admin', current_timestamp, '', null, '');

insert into sys_menu
(menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, update_by, update_time, remark)
values
(2015, 'Prompt 查询', 118, '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:prompt:list', '#', 'admin', current_timestamp, '', null, 'Prompt版本查询'),
(2016, 'Prompt 保存', 118, '6', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:prompt:save', '#', 'admin', current_timestamp, '', null, 'Prompt草稿保存'),
(2017, 'Prompt 测试', 118, '7', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:prompt:test', '#', 'admin', current_timestamp, '', null, 'Prompt离线结构测试'),
(2018, 'Prompt 发布', 118, '8', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:prompt:publish', '#', 'admin', current_timestamp, '', null, 'Prompt版本发布'),
(2019, '模板查询', 2000, '8', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:template:list', '#', 'admin', current_timestamp, '', null, '模板版本查询'),
(2020, '模板保存', 2000, '9', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:template:save', '#', 'admin', current_timestamp, '', null, '模板草稿保存'),
(2021, '模板发布', 2000, '10', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:template:publish', '#', 'admin', current_timestamp, '', null, '模板版本发布与停用'),
(2022, '数据源查询', 2004, '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:source:list', '#', 'admin', current_timestamp, '', null, '数据源列表查询'),
(2023, '数据源配置', 2004, '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:source:save', '#', 'admin', current_timestamp, '', null, '数据源创建、修改与启停'),
(2024, '采集任务查询', 2005, '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:task:list', '#', 'admin', current_timestamp, '', null, '采集任务列表查询'),
(2025, '采集任务运行', 2005, '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:task:run', '#', 'admin', current_timestamp, '', null, '采集任务运行与外部处理同步'),
(2026, '审核队列查询', 2002, '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:review:list', '#', 'admin', current_timestamp, '', null, '内容审核队列查询'),
(2027, '审核队列处理', 2002, '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:review:operate', '#', 'admin', current_timestamp, '', null, '内容审核动作'),
(2028, '审核内容重处理', 2002, '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:review:reprocess', '#', 'admin', current_timestamp, '', null, '审核内容重新处理');
