FROM python:3.10-slim

WORKDIR /app

# 复制所需文件到容器中
COPY ./requirements.txt /app
COPY ./VERSION /app
# COPY ./.env /app/.env.exaple

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建数据目录
RUN mkdir -p /app/data

# 复制应用代码
COPY ./app /app/app

# 设置环境变量，确保使用SQLite
ENV DATABASE_URL=sqlite:///data/gemini_balance.db
ENV DATABASE_TYPE=sqlite

# 暴露端口
EXPOSE 8000

# 运行应用
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
