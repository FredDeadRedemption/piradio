#!/usr/bin/env bash
# provisions the whole stack on a fresh debian/raspberry pi os host. idempotent.
set -euo pipefail

APP=/opt/webradio
DATA=/srv/webradio
ENV_FILE=/etc/webradio.env
PORT_API=8080
PORT_STREAM=8000
PORT_PUBLIC=80
MOUNT=/radio.mp3
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

[[ $EUID -eq 0 ]] || { echo "run as root"; exit 1; }

echo "==> packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq icecast2 liquidsoap nginx python3-venv python3-pip rsync

# liquidsoap 2.3.2 segfaults on startup against raspberrypi.com's ffmpeg rebuild:
# its avfilter binding reads pad names off filters that expose none. debian's build is fine.
FFMPEG_PKGS="libavcodec61 libavcodec-extra61 libavdevice61 libavfilter10 libavfilter-extra10
             libavformat61 libavformat-extra61 libavutil59 libpostproc58 libswresample5 libswscale8 ffmpeg"

if ! liquidsoap --version >/dev/null 2>&1; then
  echo "==> liquidsoap crashes on this ffmpeg build, pinning debian's"
  cat > /etc/apt/preferences.d/webradio-ffmpeg <<PIN
# liquidsoap's ffmpeg binding segfaults against the raspberrypi.com rebuild of ffmpeg.
Package: $(echo $FFMPEG_PKGS)
Pin: release o=Debian
Pin-Priority: 1001
PIN
  apt-get update -qq
  # dpkg-query exits non-zero for the names that are not installed, which pipefail would fatal on
  installed=$(dpkg-query -W -f='${Package} ${db:Status-Status}\n' $FFMPEG_PKGS 2>/dev/null \
              | awk '$2 == "installed" { print $1 }' || true)
  apt-get install -y -qq --allow-downgrades $installed
  liquidsoap --version >/dev/null 2>&1 || {
    echo "liquidsoap still segfaults after the downgrade; refusing to continue"; exit 1; }
fi

echo "==> user and directories"
id -u webradio >/dev/null 2>&1 || useradd --system --home "$DATA" --shell /usr/sbin/nologin webradio
install -d -o webradio -g webradio "$DATA"/media/{random,segments,playlists} "$DATA"/state "$DATA"/run
[[ -f "$DATA/state/mode" ]] || printf 'random' > "$DATA/state/mode"
[[ -f "$DATA/state/channel.m3u" ]] || : > "$DATA/state/channel.m3u"
chown -R webradio:webradio "$DATA"

echo "==> secrets"
if [[ ! -f $ENV_FILE ]]; then
  gen() { head -c 18 /dev/urandom | base64 | tr -d '/+='; }
  cat > "$ENV_FILE" <<ENV
WEBRADIO_ROOT=$DATA
WEBRADIO_PASSWORD=$(gen)
WEBRADIO_MAX_UPLOAD_MB=300
ICECAST_HOST=127.0.0.1
ICECAST_PORT=$PORT_STREAM
ICECAST_MOUNT=$MOUNT
ICECAST_SOURCE_PASSWORD=$(gen)
ICECAST_ADMIN_PASSWORD=$(gen)
ICECAST_RELAY_PASSWORD=$(gen)
ENV
fi
# remembered once passed, so later deploys need it only on the command line the first time
if [[ -n ${WEBRADIO_DOMAIN:-} ]]; then
  sed -i '/^WEBRADIO_DOMAIN=/d' "$ENV_FILE"
  echo "WEBRADIO_DOMAIN=$WEBRADIO_DOMAIN" >> "$ENV_FILE"
fi
if [[ -n ${WEBRADIO_PUBLIC_UI:-} ]]; then
  sed -i '/^WEBRADIO_PUBLIC_UI=/d' "$ENV_FILE"
  echo "WEBRADIO_PUBLIC_UI=$WEBRADIO_PUBLIC_UI" >> "$ENV_FILE"
fi
# added after the first release, so top it up rather than regenerating secrets
grep -q WEBRADIO_STREAM_PORT "$ENV_FILE" || echo "WEBRADIO_STREAM_PORT=$PORT_PUBLIC" >> "$ENV_FILE"
chown root:webradio "$ENV_FILE"
chmod 640 "$ENV_FILE"
set -a; . "$ENV_FILE"; set +a

echo "==> icecast"
sed -e "s|__SOURCE_PASSWORD__|$ICECAST_SOURCE_PASSWORD|" \
    -e "s|__ADMIN_PASSWORD__|$ICECAST_ADMIN_PASSWORD|" \
    -e "s|__RELAY_PASSWORD__|$ICECAST_RELAY_PASSWORD|" \
    -e "s|__HOSTNAME__|$(hostname)|" \
    -e "s|__LOCATION__|$(hostname)|" \
    -e "s|__PORT__|$PORT_STREAM|" \
    -e "s|__MOUNT__|$MOUNT|" \
    "$SRC/deploy/icecast.xml.tpl" > /etc/icecast2/icecast.xml
chown root:icecast /etc/icecast2/icecast.xml
chmod 640 /etc/icecast2/icecast.xml
sed -i 's/^ENABLE=.*/ENABLE=true/' /etc/default/icecast2 2>/dev/null || true
systemctl enable --now icecast2
systemctl restart icecast2

echo "==> nginx"
render_nginx() {
  sed -e "s|__MOUNT__|$MOUNT|g" \
      -e "s|__ICECAST_PORT__|$PORT_STREAM|g" \
      -e "s|__API_PORT__|$PORT_API|g" \
      -e "s|__MAX_UPLOAD__|$WEBRADIO_MAX_UPLOAD_MB|g" \
      -e "s|__DOMAIN__|${WEBRADIO_DOMAIN:-}|g" \
      "$1" > /etc/nginx/sites-available/webradio
}
install -d /etc/nginx/snippets
sed -e "s|__MOUNT__|$MOUNT|g" -e "s|__ICECAST_PORT__|$PORT_STREAM|g" \
    "$SRC/deploy/nginx-stream.conf.tpl" > /etc/nginx/snippets/webradio-stream.conf
ln -sfn /etc/nginx/sites-available/webradio /etc/nginx/sites-enabled/webradio
rm -f /etc/nginx/sites-enabled/default

# plain http: the whole config without a domain, and the validation path with one
render_nginx "$SRC/deploy/nginx-webradio.conf.tpl"
nginx -t
systemctl enable --now nginx
systemctl reload nginx

if [[ -n ${WEBRADIO_DOMAIN:-} ]]; then
  apt-get install -y -qq certbot
  install -d /var/www/certbot
  if [[ ! -f /etc/letsencrypt/live/$WEBRADIO_DOMAIN/fullchain.pem ]]; then
    echo "==> certificate for $WEBRADIO_DOMAIN"
    certbot certonly --webroot -w /var/www/certbot -d "$WEBRADIO_DOMAIN" \
      --non-interactive --agree-tos --deploy-hook "systemctl reload nginx" \
      ${WEBRADIO_LE_EMAIL:+-m "$WEBRADIO_LE_EMAIL"} \
      ${WEBRADIO_LE_EMAIL:---register-unsafely-without-email}
  fi
  # the ui gets a public door only when explicitly asked for, and only behind tls
  if [[ ${WEBRADIO_PUBLIC_UI:-false} == true ]]; then
    sed -e "s|__API_PORT__|$PORT_API|g" -e "s|__MAX_UPLOAD__|$WEBRADIO_MAX_UPLOAD_MB|g" \
        "$SRC/deploy/nginx-ui-public.conf.tpl" > /etc/nginx/snippets/webradio-ui.conf
  else
    install -m 644 "$SRC/deploy/nginx-ui-private.conf" /etc/nginx/snippets/webradio-ui.conf
  fi
  render_nginx "$SRC/deploy/nginx-webradio-tls.conf.tpl"
  nginx -t
  systemctl reload nginx
fi

echo "==> application"
install -d "$APP"
rsync -a --delete --exclude venv --exclude .git "$SRC/api" "$SRC/requirements.txt" "$APP/"
install -m 644 "$SRC/deploy/radio.liq" "$APP/radio.liq"
[[ -d $APP/venv ]] || python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q --upgrade pip
"$APP/venv/bin/pip" install -q -r "$APP/requirements.txt"
chown -R root:webradio "$APP"

echo "==> validating playout script"
liquidsoap --check "$APP/radio.liq"

echo "==> hardening"
apt-get install -y -qq unattended-upgrades fail2ban
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'AUTO'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
AUTO
install -m 644 "$SRC/deploy/fail2ban-webradio.conf" /etc/fail2ban/filter.d/webradio-auth.conf
install -m 644 "$SRC/deploy/fail2ban-jail.conf" /etc/fail2ban/jail.d/webradio.conf
systemctl enable --now unattended-upgrades
systemctl enable --now fail2ban
systemctl reload fail2ban 2>/dev/null || systemctl restart fail2ban

echo "==> services"
install -m 644 "$SRC"/deploy/systemd/*.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now webradio-liquidsoap webradio-api
systemctl restart webradio-liquidsoap webradio-api

LAN=$(hostname -I | awk '{print $1}')
if [[ -n ${WEBRADIO_DOMAIN:-} ]]; then
  if [[ ${WEBRADIO_PUBLIC_UI:-false} == true ]]; then
    PUBLIC="  public    https://$WEBRADIO_DOMAIN$MOUNT (stream) and https://$WEBRADIO_DOMAIN (ui)"
  else
    PUBLIC="  public    https://$WEBRADIO_DOMAIN$MOUNT (stream only; ui stays private)"
  fi
else
  PUBLIC="  public    not configured (set WEBRADIO_DOMAIN to publish over tls)"
fi

cat <<DONE

  stream    http://$LAN$MOUNT
  interface http://$LAN:$PORT_API
$PUBLIC
  login     any username / password: $WEBRADIO_PASSWORD

  logs      journalctl -u webradio-liquidsoap -u webradio-api -f
DONE
