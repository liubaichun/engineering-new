FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# 只从本地 wheel 安装（构建环境无外网）
COPY packages/*.whl /tmp/pkgs/
RUN pip install --no-cache-dir /tmp/pkgs/*.whl

COPY . .

EXPOSE 8080

CMD ["gunicorn", "--bind", ":8080", "--workers", "2", "config.wsgi:application"]
