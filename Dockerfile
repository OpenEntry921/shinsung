FROM python:3.12-slim
WORKDIR /srv/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home church && mkdir /data && chown church:church /data
COPY --chown=church:church . .
USER church
ENV DATA_DIR=/data PORT=3000
EXPOSE 3000
CMD ["sh", "-c", "gunicorn --workers 2 --threads 2 --bind 0.0.0.0:${PORT:-3000} --config gunicorn.conf.py --access-logfile /dev/null 'app:create_app()'"]
