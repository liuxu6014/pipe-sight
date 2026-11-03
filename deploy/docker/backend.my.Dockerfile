FROM python:3.10
WORKDIR /app

# 先缓存依赖层，后续只改业务代码时无需重复下载全部依赖
COPY requirements.txt pyproject.toml .
RUN grep -v '^\.$' requirements.txt > /tmp/runtime-requirements.txt \
    && pip install --no-cache-dir -r /tmp/runtime-requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制源代码
COPY . .
# 运行依赖层已安装，关闭隔离构建可避免每次构建再次联网下载 setuptools 等构建依赖。
RUN pip install --no-cache-dir --no-build-isolation . --no-deps

# 暴露端口
EXPOSE 9099

# 启动命令
CMD ["ruoyi", "app", "run", "--env=dockermy"]
