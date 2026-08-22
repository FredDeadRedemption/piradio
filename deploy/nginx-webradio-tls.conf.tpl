# public face of the station: the mount over tls and nothing else.
# icecast binds 127.0.0.1, so this is the only route in from the network.

limit_conn_zone $binary_remote_addr zone=webradio_conn:10m;
limit_req_zone $binary_remote_addr zone=webradio_ui:10m rate=10r/s;

# bare ip and unknown hosts get nothing, but renewals must still validate
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    server_tokens off;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 404;
    }
}

server {
    listen 80;
    listen [::]:80;
    server_name __DOMAIN__;
    server_tokens off;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name __DOMAIN__;
    server_tokens off;

    ssl_certificate     /etc/letsencrypt/live/__DOMAIN__/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/__DOMAIN__/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    location = __MOUNT__ {
        # one client could otherwise hold open every icecast slot
        limit_conn webradio_conn 3;

        proxy_pass http://127.0.0.1:__ICECAST_PORT____MOUNT__;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        # a stream never ends: buffering adds latency and breaks icy metadata
        proxy_buffering off;
        proxy_read_timeout 12h;
        proxy_send_timeout 12h;
    }

    # the control ui is only ever exposed here, where there is tls in front of basic auth
    location / {
        limit_req zone=webradio_ui burst=20 nodelay;
        client_max_body_size __MAX_UPLOAD__m;

        proxy_pass http://127.0.0.1:__API_PORT__;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        # large uploads stream straight through rather than landing in a temp file first
        proxy_request_buffering off;
        proxy_read_timeout 10m;
        proxy_send_timeout 10m;
    }
}
