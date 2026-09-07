# public listener page: read-only, unauthenticated, nothing here writes anything
location ^~ /listen/ {
    proxy_pass http://127.0.0.1:__API_PORT__;
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

location = /api/now {
    proxy_pass http://127.0.0.1:__API_PORT__;
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
