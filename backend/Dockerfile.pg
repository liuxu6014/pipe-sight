FROM python:3.10
WORKDIR /app

# 先单独复制依赖清单，让仅修改业务代码时可以复用依赖层。
COPY requirements-pg.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements-pg.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制源代码
COPY . .

# 安装后端包本身，提供 app、CLI 及统一的进程入口。
RUN pip install --no-cache-dir --no-build-isolation . --no-deps

# 暴露端口
EXPOSE 9099

# 启动命令
CMD ["ruoyi", "app", "run", "--env=dockerpg"]
