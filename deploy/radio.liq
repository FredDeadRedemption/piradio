# webradio playout: four sources, one switch, driven by the api over a unix socket.
# selection logic lives in the api; this file only decodes, switches and encodes.

def default(value, fallback) =
  if value == "" then fallback else value end
end

root = environment.get("WEBRADIO_ROOT")
media = "#{root}/media"
state = "#{root}/state"

settings.log.stdout.set(true)
settings.log.file.set(false)
settings.log.level.set(3)

settings.server.telnet.set(false)
settings.server.socket.set(true)
settings.server.socket.path.set("#{root}/run/liquidsoap.sock")
settings.server.socket.permissions.set(432)  # 0o660

# survives a liquidsoap restart without the api having to replay state
mode = ref(file.contents("#{state}/mode"))

random_src = playlist(
  mode="randomize", reload_mode="watch",
  "#{media}/random")

segments_src = playlist(
  mode="randomize", reload_mode="watch",
  "#{media}/segments")

# api rewrites this m3u on every channel switch, then reloads both readers of it
channel_src = playlist(
  mode="normal", reload_mode="watch",
  "#{state}/channel.m3u")

# separate source because playlist ordering is fixed at creation
channel_shuffled = playlist(
  mode="randomize", reload_mode="watch",
  "#{state}/channel.m3u")

radio = switch(track_sensitive=false, [
  ({mode() == "segments"}, segments_src),
  ({mode() == "channel"}, channel_src),
  ({mode() == "channel_shuffle"}, channel_shuffled),
  ({true}, random_src)
])

# untagged uploads would reach icecast with no title at all
def ensure_title(m) =
  if m["title"] == "" then
    [("title", path.remove_extension(path.basename(m["filename"])))]
  else
    []
  end
end

radio = metadata.map(ensure_title, radio)

# blank fallback so the icecast mount never drops on an empty library
radio = mksafe(radio)

# playlist ids do not drive server namespaces in 2.3, so expose reloads by hand
def reload_pool(name) =
  if name == "random" then
    random_src.reload()
    "OK"
  elsif name == "segments" then
    segments_src.reload()
    "OK"
  elsif name == "channel" then
    channel_src.reload()
    channel_shuffled.reload()
    "OK"
  else
    "ERROR: unknown pool"
  end
end

server.register(
  "reload",
  usage="reload <random|segments|channel>",
  description="re-read a pool from disk",
  reload_pool)

server.register(
  "mode",
  usage="mode <random|segments|channel|channel_shuffle>",
  description="select the active source",
  fun (m) -> if list.mem(m, ["random", "segments", "channel", "channel_shuffle"]) then
    mode := m
    "OK"
  else
    "ERROR: unknown mode"
  end)

server.register(
  "current_mode",
  description="report the active source",
  fun (_) -> mode())

output.icecast(
  %mp3(bitrate=int_of_string(default(environment.get("WEBRADIO_BITRATE"), "128")), samplerate=44100, stereo=true),
  id="stream",
  host=environment.get("ICECAST_HOST"),
  port=int_of_string(environment.get("ICECAST_PORT")),
  password=environment.get("ICECAST_SOURCE_PASSWORD"),
  mount=environment.get("ICECAST_MOUNT"),
  name=default(environment.get("WEBRADIO_NAME"), "webradio"),
  description=default(environment.get("WEBRADIO_DESCRIPTION"), "a small internet radio station"),
  radio)
