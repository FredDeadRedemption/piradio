FROM savonet/liquidsoap:v2.3.3

USER root
# the mount points must exist here so a fresh named volume inherits their ownership
RUN mkdir -p /srv/webradio/media /srv/webradio/state /srv/webradio/run \
 && printf random > /srv/webradio/state/mode \
 && : > /srv/webradio/state/channel.m3u \
 && chown -R liquidsoap:liquidsoap /srv/webradio
COPY deploy/radio.liq /radio.liq

USER liquidsoap
CMD ["/radio.liq"]
