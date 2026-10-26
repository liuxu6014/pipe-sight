from datetime import datetime

from sqlalchemy import CHAR, BigInteger, Column, DateTime, Index, Integer, String

from config.database import Base


class SysLogininfor(Base):
    """
    系统访问记录
    """

    __api_field_map__ = {
        'info_id': 'id',
        'user_name': 'username',
        'ipaddr': 'ip',
        'login_location': 'location',
        'msg': 'message',
        'login_time': 'logged_at',
    }

    __tablename__ = 'sys_logininfor'
    __table_args__ = {'comment': '系统访问记录'}

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='访问ID')
    username = Column(String(50), nullable=True, server_default="''", comment='用户账号')
    ip = Column(String(128), nullable=True, server_default="''", comment='登录IP地址')
    location = Column(String(255), nullable=True, server_default="''", comment='登录地点')
    browser = Column(String(50), nullable=True, server_default="''", comment='浏览器类型')
    os = Column(String(50), nullable=True, server_default="''", comment='操作系统')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='登录状态（0成功 1失败）')
    message = Column(String(255), nullable=True, server_default="''", comment='提示消息')
    logged_at = Column(DateTime, nullable=True, default=datetime.now, comment='访问时间')

    idx_login_logs_s = Index('idx_login_logs_s', status)
    idx_login_logs_lt = Index('idx_login_logs_lt', logged_at)


class SysOperLog(Base):
    """
    操作日志记录
    """

    __api_field_map__ = {
        'oper_id': 'id',
        'oper_name': 'username',
        'oper_url': 'url',
        'oper_ip': 'ip',
        'oper_location': 'location',
        'oper_param': 'request_data',
        'json_result': 'response_data',
        'error_msg': 'error',
        'oper_time': 'operated_at',
        'cost_time': 'duration_ms',
    }

    __tablename__ = 'sys_oper_log'
    __table_args__ = {'comment': '操作日志记录'}

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='日志主键')
    title = Column(String(50), nullable=True, server_default="''", comment='模块标题')
    business_type = Column(
        Integer,
        nullable=True,
        server_default='0',
        comment='业务操作类型（0其他 1新增 2修改 3删除 4授权 5导出 6导入 7强退 8生成代码 9清空）',
    )
    method = Column(String(100), nullable=True, server_default="''", comment='方法名称')
    request_method = Column(String(10), nullable=True, server_default="''", comment='请求方式')
    operator_type = Column(
        Integer, nullable=True, server_default='0', comment='操作类别（0其它 1后台用户 2手机端用户）'
    )
    username = Column(String(50), nullable=True, server_default="''", comment='操作人员')
    url = Column(String(255), nullable=True, server_default="''", comment='请求URL')
    ip = Column(String(128), nullable=True, server_default="''", comment='主机地址')
    location = Column(String(255), nullable=True, server_default="''", comment='操作地点')
    request_data = Column(
        String(2000), nullable=True, server_default="''", comment='经日志清洗及长度限制后的请求参数文本'
    )
    response_data = Column(
        String(2000), nullable=True, server_default="''", comment='经日志清洗及长度限制后的响应结果文本'
    )
    status = Column(Integer, nullable=True, server_default='0', comment='操作状态（0正常 1异常）')
    error = Column(String(2000), nullable=True, server_default="''", comment='错误消息')
    operated_at = Column(DateTime, nullable=True, default=datetime.now, comment='操作时间')
    duration_ms = Column(BigInteger, nullable=True, server_default='0', comment='本次操作处理耗时（毫秒）')

    idx_operation_logs_bt = Index('idx_operation_logs_bt', business_type)
    idx_operation_logs_s = Index('idx_operation_logs_s', status)
    idx_operation_logs_ot = Index('idx_operation_logs_ot', operated_at)
