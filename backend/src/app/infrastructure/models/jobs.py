from datetime import datetime

from sqlalchemy import CHAR, BigInteger, Column, DateTime, ForeignKey, Index, String, UniqueConstraint

from config.database import Base


class SysJob(Base):
    """
    定时任务调度表
    """

    __api_field_map__ = {
        'job_id': 'id',
        'job_name': 'name',
        'job_group': 'group_key',
        'job_executor': 'executor',
        'job_args': 'args',
        'job_kwargs': 'kwargs',
        'create_by': 'created_by',
        'create_time': 'created_at',
        'update_by': 'updated_by',
        'update_time': 'updated_at',
    }

    __tablename__ = 'sys_job'
    __table_args__ = (
        UniqueConstraint('name', 'group_key', name='uk_scheduled_jobs_name_group'),
        Index('idx_scheduled_jobs_status_group', 'status', 'group_key'),
        {'comment': '定时任务调度表'},
    )

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='任务ID')
    name = Column(String(64), nullable=True, server_default="''", comment='任务名称')
    group_key = Column(String(64), nullable=True, server_default='default', comment='任务组名')
    executor = Column(String(64), nullable=True, server_default='default', comment='任务执行器')
    invoke_target = Column(String(500), nullable=False, comment='调用目标字符串')
    args = Column(
        String(255), nullable=True, server_default="''", comment='调用位置参数文本；按英文逗号分隔后传给执行函数'
    )
    kwargs = Column(String(255), nullable=True, server_default="''", comment='调用关键字参数的JSON对象文本')
    cron_expression = Column(String(255), nullable=True, server_default="''", comment='cron执行表达式')
    misfire_policy = Column(
        String(20),
        nullable=True,
        server_default='3',
        comment='错过触发策略编码；当前实现中2合并补跑，3使用超长宽限期，其他不合并且不限制宽限期',
    )
    concurrent = Column(CHAR(1), nullable=True, server_default='1', comment='是否并发执行（0允许 1禁止）')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1暂停）')
    created_by = Column(String(64), nullable=True, server_default="''", comment='创建者')
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')
    updated_by = Column(String(64), nullable=True, server_default="''", comment='更新者')
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    remark = Column(String(500), nullable=True, server_default="''", comment='备注信息')


class SysJobLog(Base):
    """
    定时任务调度日志表
    """

    __api_field_map__ = {
        'job_log_id': 'id',
        'job_name': 'name',
        'job_group': 'group_key',
        'job_executor': 'executor',
        'job_args': 'args',
        'job_kwargs': 'kwargs',
        'job_trigger': 'trigger',
        'job_message': 'message',
        'exception_info': 'error',
        'create_time': 'created_at',
    }

    __tablename__ = 'sys_job_log'
    __table_args__ = (
        Index('idx_job_logs_job_time', 'job_id', 'created_at'),
        Index('idx_job_logs_status_time', 'status', 'created_at'),
        {'comment': '定时任务调度日志表'},
    )

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='任务日志ID')
    job_id = Column(BigInteger, ForeignKey('sys_job.id', ondelete='SET NULL'), nullable=True, comment='任务ID')
    name = Column(String(64), nullable=False, comment='任务名称')
    group_key = Column(String(64), nullable=False, comment='任务组名')
    executor = Column(String(64), nullable=False, comment='任务执行器')
    invoke_target = Column(String(500), nullable=False, comment='调用目标字符串')
    args = Column(String(255), nullable=True, server_default="''", comment='执行时的位置参数快照；英文逗号分隔文本')
    kwargs = Column(String(255), nullable=True, server_default="''", comment='执行时的关键字参数快照；JSON对象文本')
    trigger = Column(String(255), nullable=True, server_default="''", comment='任务触发器')
    message = Column(String(500), nullable=True, comment='日志信息')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='执行状态（0正常 1失败）')
    error = Column(String(2000), nullable=True, server_default="''", comment='异常信息')
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')
