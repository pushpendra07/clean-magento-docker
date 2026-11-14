FROM python:3.13-slim
WORKDIR /app
COPY server.py index.html ./
RUN useradd --uid 10001 --create-home erp && mkdir /data && chown erp:erp /data
USER erp
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "server.py"]
