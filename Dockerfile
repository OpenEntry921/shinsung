FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt ./
RUN --mount=type=secret,id=build_ca,required=false \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 portal && mkdir -m 700 /data && chown portal:portal /data /app
COPY --chown=portal:portal . .
USER portal
ENV DATA_DIR=/data APP_MODE=production
EXPOSE 8000
CMD ["sh", "scripts/start-production.sh"]
