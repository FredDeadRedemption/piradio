FROM debian:trixie-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends icecast2 media-types \
 && rm -rf /var/lib/apt/lists/* \
 && ln -sf /dev/stdout /var/log/icecast2/access.log \
 && ln -sf /dev/stderr /var/log/icecast2/error.log

COPY deploy/icecast.xml.tpl /icecast.xml.tpl
COPY docker/icecast-entrypoint.sh /entrypoint.sh

USER icecast2
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
