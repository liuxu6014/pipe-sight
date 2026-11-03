# 仓库级脚本

| 目录 | 内容 | 工作目录 |
| --- | --- | --- |
| `dev/` | Windows 开发服务启动、停止；CMD 调用同目录 PowerShell | 自动解析仓库根目录 |
| `checks/` | 后端测试、前端测试和构建的统一验证入口 | 自动解析仓库根目录 |

在仓库根目录使用：

```powershell
.\scripts\dev\start-dev.cmd
.\scripts\dev\stop-dev.cmd
```

```sh
bash scripts/checks/verify_project.sh
```

Windows 启动脚本沿用现有的依赖安装和数据库初始化/迁移流程；停止脚本按本项目的 PID 与进程路径识别服务。PID 和日志仍使用根目录 `.runtime/pipesight-dev/`。

仅后端使用的导入、回填和数据库检查脚本放入 [backend/scripts](../backend/scripts/README.md)，不复制到此目录。macOS/Linux 开发启动方式见根目录 [README](../README.md)。
