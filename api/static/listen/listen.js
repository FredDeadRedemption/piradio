const $ = (id) => document.getElementById(id);
const audio = $("audio");

const PLAY = "M8 5v14l11-7z";
const PAUSE = "M6 5h4v14H6zM14 5h4v14h-4z";

let stream = null;
let wanted = false;
let backoff = 1000;
let retry = null;

const setGlyph = (playing) => {
  $("glyph").firstElementChild.setAttribute("d", playing ? PAUSE : PLAY);
  $("play").classList.toggle("on", playing);
  $("play").setAttribute("aria-label", playing ? "pause" : "play");
};

function describe(state) {
  $("title").textContent = state.title || (state.online ? "on air" : "off air");
  $("dot").classList.toggle("on", Boolean(state.online));
  const count = state.listeners === 1 ? "1 listener" : `${state.listeners} listeners`;
  $("status").textContent = state.online ? count : "off air";

  // only served to callers on the local network
  $("control").hidden = !state.control;
  if (state.control) {
    $("control").href = state.control;
    $("control").textContent = state.control.replace(/^https?:\/\//, "control panel \u2192 ");
  }

  if ("mediaSession" in navigator) {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: state.title || "finrod radio",
      artist: "finrod radio",
      artwork: [
        { src: "/listen/icon-192.png", sizes: "192x192", type: "image/png" },
        { src: "/listen/icon-512.png", sizes: "512x512", type: "image/png" },
      ],
    });
  }
}

async function poll() {
  try {
    const state = await (await fetch("/api/now", { cache: "no-store" })).json();
    stream = state.url;
    describe(state);
  } catch {
    $("dot").classList.remove("on");
  }
}

function start() {
  if (!stream) return;
  // a fresh query string forces a new connection rather than a resumed, stale one
  audio.src = `${stream}?t=${Date.now()}`;
  audio.play().catch(() => setGlyph(false));
}

function reconnect() {
  if (!wanted || retry) return;
  $("status").textContent = "reconnecting";
  retry = setTimeout(() => {
    retry = null;
    if (wanted) start();
  }, backoff);
  backoff = Math.min(backoff * 2, 30000);
}

$("play").onclick = () => {
  if (wanted) {
    wanted = false;
    clearTimeout(retry);
    retry = null;
    audio.pause();
    audio.removeAttribute("src");
    audio.load();
    setGlyph(false);
    return;
  }
  wanted = true;
  setGlyph(true);
  start();
};

audio.addEventListener("playing", () => {
  backoff = 1000;
  setGlyph(true);
  poll();
});
audio.addEventListener("pause", () => wanted || setGlyph(false));
["error", "stalled", "ended", "suspend"].forEach((event) =>
  audio.addEventListener(event, () => audio.paused && reconnect()));

if ("mediaSession" in navigator) {
  navigator.mediaSession.setActionHandler("play", () => wanted || $("play").click());
  navigator.mediaSession.setActionHandler("pause", () => wanted && $("play").click());
}

// a phone waking from sleep resumes on a dead socket, so re-establish it
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    poll();
    if (wanted && audio.paused) reconnect();
  }
});

poll();
setInterval(poll, 10000);
