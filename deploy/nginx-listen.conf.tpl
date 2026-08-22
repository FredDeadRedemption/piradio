# public listener page: read-only, unauthenticated, nothing here writes anything
location ^~ /listen/ {
    proxy_pass http://127.0.0.1:__API_PORT__;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location = /api/now {
    proxy_pass http://127.0.0.1:__API_PORT__;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
