# public face of the station: the mount and nothing else.
# icecast itself binds 127.0.0.1, so this is the only route in from the network.

limit_conn_zone $binary_remote_addr zone=webradio_conn:10m;

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    server_tokens off;

    # one client could otherwise hold open every icecast slot
    limit_conn webradio_conn 3;

    # certbot validates over plain http, before and after a cert exists
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location = __MOUNT__ {
        proxy_pass http://127.0.0.1:__ICECAST_PORT____MOUNT__;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        # a stream never ends: buffering adds latency and breaks icy metadata
        proxy_buffering off;
        proxy_read_timeout 12h;
        proxy_send_timeout 12h;
    }

    location / {
        return 404;
    }
}
