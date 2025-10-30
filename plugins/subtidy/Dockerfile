FROM python:3.11-slim
RUN pip install --no-cache-dir fastapi uvicorn[standard]
WORKDIR /app
COPY handler.py /app/
EXPOSE 9090
CMD ["uvicorn","handler:app","--host","0.0.0.0","--port","9090","--workers","1","--timeout-keep-alive","5"]