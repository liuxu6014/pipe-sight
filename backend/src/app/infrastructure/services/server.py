"""服务器与 Python 进程监控服务。"""

import os
import platform
import socket
import time

import anyio
import psutil

from app.infrastructure.schemas.server import CpuInfo, MemoryInfo, PyInfo, ServerMonitorModel, SysFiles, SysInfo
from app.infrastructure.services.formatting import format_bytes


class ServerService:
    """读取当前 API 进程所在主机的运行指标。"""

    @staticmethod
    async def get_server_monitor_info() -> ServerMonitorModel:
        cpu_num = psutil.cpu_count(logical=True)
        cpu_usage_percent = psutil.cpu_times_percent()
        cpu = CpuInfo(cpuNum=cpu_num, used=cpu_usage_percent.user, sys=cpu_usage_percent.system, free=cpu_usage_percent.idle)

        memory_info = psutil.virtual_memory()
        mem = MemoryInfo(
            total=format_bytes(memory_info.total),
            used=format_bytes(memory_info.used),
            free=format_bytes(memory_info.free),
            usage=memory_info.percent,
        )

        hostname = socket.gethostname()
        computer_ip = socket.gethostbyname(hostname)
        sys_info = SysInfo(
            computerIp=computer_ip,
            computerName=platform.node(),
            osArch=platform.machine(),
            osName=platform.platform(),
            userDir=str(await anyio.Path.cwd()),
        )

        current_process = psutil.Process(os.getpid())
        start_time_stamp = current_process.create_time()
        difference = time.time() - start_time_stamp
        days = int(difference // (24 * 60 * 60))
        hours = int((difference % (24 * 60 * 60)) // (60 * 60))
        minutes = int((difference % (60 * 60)) // 60)
        process_memory = current_process.memory_info()
        py = PyInfo(
            name=current_process.name(),
            version=platform.python_version(),
            startTime=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time_stamp)),
            runTime=f'{days}天{hours}小时{minutes}分钟',
            home=current_process.exe(),
            total=format_bytes(memory_info.available),
            used=format_bytes(process_memory.rss),
            free=format_bytes(memory_info.available - process_memory.rss),
            usage=round((process_memory.rss / memory_info.available) * 100, 2),
        )

        sys_files = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.device)
                sys_files.append(
                    SysFiles(
                        dirName=partition.device,
                        sysTypeName=partition.fstype,
                        typeName=f'本地固定磁盘（{partition.mountpoint.replace(chr(92), "")}）',
                        total=format_bytes(usage.total),
                        used=format_bytes(usage.used),
                        free=format_bytes(usage.free),
                        usage=f'{usage.percent}%',
                    )
                )
            except Exception:  # noqa: PERF203
                continue

        return ServerMonitorModel(cpu=cpu, mem=mem, sys=sys_info, py=py, sysFiles=sys_files)


__all__ = ['ServerService']
