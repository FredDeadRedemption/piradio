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
