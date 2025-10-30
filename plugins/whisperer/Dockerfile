FROM python:3.11-slim

# ffmpeg は音声抽出で使う
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi uvicorn[standard] faster-whisper

WORKDIR /app
COPY handler.py /app/

EXPOSE 9090
ENV WHISPER_MODEL=small WHISPER_DEVICE=cpu WHISPER_COMPUTE=int8
CMD ["uvicorn","handler:app","--host","0.0.0.0","--port","9090","--workers","1","--timeout-keep-alive","5"]