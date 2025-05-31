# 基于Python官方镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制项目文件到容器
COPY . /app

# 安装依赖（如有requirements.txt可取消注释）
RUN pip install -r requirements.txt

# 先运行main.py，等待其加载完成后再运行auto-ref.py
CMD ["/bin/sh", "-c", "python main.py && python auto-ref.py"]
