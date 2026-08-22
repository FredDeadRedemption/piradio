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

    # lan listeners reach the pi by ip over plain http, with no domain to redirect to
    include /etc/nginx/snippets/webradio-stream.conf;

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

    include /etc/nginx/snippets/webradio-stream.conf;

    # public or 404, depending on whether the ui is meant to have a public door
    include /etc/nginx/snippets/webradio-ui.conf;
}
