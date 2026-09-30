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
(2007, '知识库问答', 2000, '7', 'knowledge', 'pipeline/knowledge/index', '', '', 1, 0, 'C', '0', '0', 'pipeline:kb:view', 'education', 'admin', current_timestamp, '', null, '内部资料库与智能问答');

insert into sys_menu
(menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, update_by, update_time, remark)
values
(2010, '情报查询', 2002, '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:intel:query', '#', 'admin', current_timestamp, '', null, ''),
(2011, '数据源配置', 2004, '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:source:edit', '#', 'admin', current_timestamp, '', null, ''),
(2012, '任务运行', 2005, '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:task:run', '#', 'admin', current_timestamp, '', null, ''),
(2013, '报告导出', 2006, '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'pipeline:report:export', '#', 'admin', current_timestamp, '', null, '');
