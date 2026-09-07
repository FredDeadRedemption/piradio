# reached only over tls, where basic auth is not sent in the clear
location / {
    add_header Strict-Transport-Security "max-age=15552000" always;
    limit_req zone=webradio_ui burst=20 nodelay;
    client_max_body_size __MAX_UPLOAD__m;

    proxy_pass http://127.0.0.1:__API_PORT__;
    proxy_http_version 1.1;
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    # large uploads stream straight through rather than landing in a temp file first
    proxy_request_buffering off;
    proxy_read_timeout 10m;
    proxy_send_timeout 10m;
}
