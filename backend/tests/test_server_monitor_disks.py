"""Monitor mounted filesystems rather than device-node storage."""

from types import SimpleNamespace

import pytest

from app.infrastructure.services import server
from app.infrastructure.services.formatting import format_bytes


@pytest.mark.parametrize('unavailable_second_mount', [False, True])
async def test_disk_capacity_is_read_from_each_mountpoint(monkeypatch, unavailable_second_mount):
    mounts = [
        SimpleNamespace(device='/dev/disk3s1', mountpoint='/', fstype='apfs'),
        SimpleNamespace(device='/dev/disk3s5', mountpoint='/System/Volumes/Data', fstype='apfs'),
    ]
    capacities = {
        '/': SimpleNamespace(total=500 * 1024**3, used=400 * 1024**3, free=100 * 1024**3, percent=80.0),
        '/System/Volumes/Data': SimpleNamespace(
            total=500 * 1024**3, used=350 * 1024**3, free=150 * 1024**3, percent=70.0
        ),
    }
    requested = []

    def disk_usage(path):
        requested.append(path)
        if unavailable_second_mount and path == mounts[1].mountpoint:
            raise PermissionError(path)
        return capacities[path]

    monkeypatch.setattr(server.psutil, 'disk_partitions', lambda: mounts)
    monkeypatch.setattr(server.psutil, 'disk_usage', disk_usage)
    monkeypatch.setattr(server.socket, 'gethostbyname', lambda _hostname: '127.0.0.1')

    result = await server.ServerService.get_server_monitor_info()

    assert requested == [mount.mountpoint for mount in mounts]
    assert len(result.sys_files) == (1 if unavailable_second_mount else 2)
    for item, mount in zip(result.sys_files, mounts, strict=False):
        usage = capacities[mount.mountpoint]
        assert item.dir_name == mount.device
        assert mount.mountpoint in item.type_name
        assert item.total == format_bytes(usage.total)
        assert item.free == format_bytes(usage.free)
        assert item.used == format_bytes(usage.used)
        assert item.usage == f'{usage.percent}%'
