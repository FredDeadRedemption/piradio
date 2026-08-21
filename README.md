# webradio

A Raspberry Pi internet radio station: one always-on MP3 stream, three programming
modes, and a small web interface for uploading tracks and switching what's on air.

```
browser  ──uploads / mode switch──>  FastAPI  ──unix socket──>  Liquidsoap
                                        │                           │
                                    /srv/webradio                Icecast2 (localhost)
                                                                    │
                                                       listeners ──> nginx :80 /radio.mp3
```

* **nginx** is the only thing listening on the network: it proxies exactly one path,
  the mount, and 404s everything else. Icecast's admin panel and status endpoints are
  not reachable from outside the Pi.
* **Icecast2** owns the stream and the listener count, bound to `127.0.0.1`.
* **Liquidsoap** is the playout engine: gapless decoding, three sources behind one
  switch, and a blank fallback so the mount never drops even with an empty library.
* **FastAPI** owns every decision. Liquidsoap gets two commands (`mode`, `*.reload`)
  and nothing else, which keeps the audio layer version-agnostic and boring.

## Modes

| Mode | Source | Order |
| --- | --- | --- |
| `random` | `/srv/webradio/media/random` | shuffled, forever |
| `segments` | `/srv/webradio/media/segments` | shuffled, forever |
| `channel` | `/srv/webradio/media/playlists/<name>` | filename order, optionally shuffled |

A channel is just a folder. Create one in the UI, upload into it, and the mode-3
selector becomes a channel switcher.

State lives in `/srv/webradio/state/`: `state.json` for the API, a one-word `mode`
file that Liquidsoap reads at startup, and `channel.m3u` rendered on every switch.
That means a reboot or a crash of either process resumes on the same programming.

## Install

On the Pi:

```sh
git clone <this repo> ~/webradio && sudo bash ~/webradio/deploy/install.sh
```

Or from your laptop, to sync a checkout and provision in one step:

```sh
./deploy/push.sh rpi.local
```

The installer is idempotent, generates all passwords on first run into
`/etc/webradio.env`, and prints the stream URL, the UI URL and the login at the end.

## Operating

```sh
journalctl -u webradio-liquidsoap -u webradio-api -f   # logs
systemctl restart webradio-liquidsoap                  # restart playout
socat - UNIX-CONNECT:/srv/webradio/run/liquidsoap.sock # talk to playout (apt install socat)
```

Socket commands: `current_mode`, `mode <random|segments|channel|channel_shuffle>`,
`reload <random|segments|channel>`, `stream.skip`, `help`.

Note that `reload` and `mode` are registered by `radio.liq` rather than derived from
source ids: Liquidsoap 2.3 accepts `id=` on `playlist` but still registers its server
commands as `playlist`, `playlist.1`, ... so anything keyed on those ids is positional
and would silently break when a source is added.

## The ffmpeg pin

Raspberry Pi OS pulls ffmpeg from `archive.raspberrypi.com`, whose rebuild carries a
higher epoch than Debian's and therefore wins. Liquidsoap 2.3.2 **segfaults on startup**
against it, before reading any script: its avfilter binding walks every filter and reads
pad names off filters that expose none.

The installer detects this (`liquidsoap --version` crashing) and pins the ffmpeg
libraries to Debian's build in `/etc/apt/preferences.d/webradio-ffmpeg`. On a headless
Pi nothing else links those libraries, so the pin is free. If you later install
something that wants hardware-accelerated video, revisit it.

## Exposure

nginx serves the mount on port 80 and nothing else, so forwarding port 80 to the Pi
publishes the stream without publishing anything that can write to it. The upload
interface stays on `:8080`, unforwarded and LAN-only.

`WEBRADIO_STREAM_PORT` in `/etc/webradio.env` is what the UI advertises to listeners;
`ICECAST_PORT` is where icecast actually listens behind the proxy. They are different
numbers on purpose.

## Security

The stream is public by design; the control plane is not. The UI and API sit behind
HTTP Basic auth over plain HTTP, so the password is only as private as the network -
keep `:8080` off the internet unless you put TLS in front of it first. Uploads are
restricted to `.mp3`, filenames are sanitised and path-resolved back into their
pool, and both services run as an unprivileged system user with `ProtectSystem=strict`.
Do not port-forward this as-is; put it behind a reverse proxy with TLS first.
