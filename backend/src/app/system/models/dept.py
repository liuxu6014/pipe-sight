"""Native RuoYi department columns; intentionally no compact-schema renames."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, Index, Integer, String, text

from config.database import Base


class SysDept(Base):
    __tablename__ = 'sys_dept'
    __api_field_map__ = {}
    __table_args__ = (
        CheckConstraint("status IN ('0', '1')", name='ck_sys_dept_status'),
        CheckConstraint("del_flag IN ('0', '2')", name='ck_sys_dept_del_flag'),
        Index('ix_sys_dept_parent_id', 'parent_id'),
        Index(
            'uq_sys_dept_active_name',
            'parent_id',
            'dept_name',
            unique=True,
            postgresql_where=text("del_flag = '0'"),
            sqlite_where=text("del_flag = '0'"),
        ),
        {'comment': '部门表'},
    )

    dept_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='部门ID')
    parent_id = Column(BigInteger, nullable=False, server_default='0', comment='父部门ID')
    ancestors = Column(String(500), nullable=False, server_default='0', comment='祖级列表')
    dept_name = Column(String(30), nullable=False, comment='部门名称')
    order_num = Column(Integer, nullable=False, server_default='0', comment='显示顺序')
    leader = Column(String(20), nullable=True, comment='负责人')
    phone = Column(String(11), nullable=True, comment='联系电话')
    email = Column(String(50), nullable=True, comment='邮箱')
    status = Column(String(1), nullable=False, server_default='0', comment='部门状态（0正常 1停用）')
    del_flag = Column(String(1), nullable=False, server_default='0', comment='删除标志（0存在 2删除）')
    create_by = Column(String(64), nullable=True, comment='创建者')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')
    update_by = Column(String(64), nullable=True, comment='更新者')
    update_time = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment='更新时间')
