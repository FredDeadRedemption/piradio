FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api ./api

# same uid as the liquidsoap image, which owns the socket the two share
RUN mkdir -p /srv/webradio/media /srv/webradio/state /srv/webradio/run \
 && chown -R 100:101 /srv/webradio

USER 100:101
EXPOSE 8080
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8080"]
