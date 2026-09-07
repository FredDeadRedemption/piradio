#!/bin/sh
# renders the shared icecast template with this container's settings, then hands over to icecast
set -eu

sed -e "s|__SOURCE_PASSWORD__|${ICECAST_SOURCE_PASSWORD}|" \
    -e "s|__ADMIN_PASSWORD__|${ICECAST_ADMIN_PASSWORD}|" \
    -e "s|__RELAY_PASSWORD__|${ICECAST_RELAY_PASSWORD}|" \
    -e "s|__HOSTNAME__|${WEBRADIO_NAME:-webradio}|" \
    -e "s|__LOCATION__|${WEBRADIO_NAME:-webradio}|" \
    -e "s|__PORT__|8000|" \
    -e "s|__BIND__|0.0.0.0|" \
    -e "s|__CLIENTS__|${WEBRADIO_MAX_LISTENERS:-100}|" \
    -e "s|__MOUNT__|${ICECAST_MOUNT}|" \
    /icecast.xml.tpl \
  | sed -e '/<changeowner>/,/<\/changeowner>/d' > /tmp/icecast.xml

exec icecast2 -c /tmp/icecast.xml
