FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.title="ExifSniffer" \
      org.opencontainers.image.description="ExifSniffer MCP server: Streamable HTTP, media fetch, EXIF/metadata extraction" \
      org.opencontainers.image.version="0.1.1"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir . \
    && chown -R app:app /app

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

RUN mkdir -p /data && chown app:app /data

ENV DATA_DIR=/data \
    HOST=0.0.0.0 \
    PORT=3000

EXPOSE 3000

VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os,socket; p=int(os.environ.get('PORT','3000')); s=socket.socket(); s.settimeout(3); s.connect(('127.0.0.1',p)); s.close()"

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "-m", "exifsniffer"]
