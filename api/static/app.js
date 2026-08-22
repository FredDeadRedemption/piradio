const $ = (id) => document.getElementById(id);
let state = { mode: "random", channel: null, shuffle: false, channels: [] };
let tab = { pool: "random", channel: null };

const api = async (path, options = {}) => {
  const res = await fetch(`/api${path}`, options);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.status === 204 ? null : res.json();
};

const toast = (message) => {
  $("toast").textContent = message;
  $("toast").classList.add("show");
  setTimeout(() => $("toast").classList.remove("show"), 2600);
};

function renderStatus(data) {
  $("dot").classList.toggle("on", data.icecast.online && data.playout);
  $("title").textContent = data.icecast.title || (data.playout ? "starting up" : "playout offline");
  $("listeners").textContent = data.icecast.online ? `${data.icecast.listeners} listening` : "";
  const url = data.stream.url;
  if ($("player").dataset.src !== url) {
    $("player").dataset.src = url;
    $("player").src = url;
  }
}

function renderPublicLink(url) {
  $("public").hidden = !url;
  if (url) {
    $("public").href = url;
    $("public").textContent = `public station \u2192 ${url.replace(/^https?:\/\//, "")}`;
  }
}

function renderControls() {
  document.querySelectorAll(".mode").forEach((button) =>
    button.classList.toggle("active", button.dataset.mode === state.mode));
  $("shuffle").checked = state.shuffle;

  $("channel").innerHTML = state.channels.length
    ? state.channels.map((c) => `<option${c === state.channel ? " selected" : ""}>${c}</option>`).join("")
    : "<option value=''>no channels yet</option>";
  $("channel").disabled = !state.channels.length;

  const tabs = [["random", null], ["segments", null], ...state.channels.map((c) => ["channel", c])];
  $("tabs").innerHTML = tabs.map(([pool, channel]) => {
    const active = tab.pool === pool && tab.channel === channel ? " class='active'" : "";
    return `<button${active} data-pool="${pool}" data-channel="${channel ?? ""}">${channel ?? pool}</button>`;
  }).join("");
}

async function refreshState() {
  const data = await api("/state");
  state = data;
  if (tab.pool === "channel" && !state.channels.includes(tab.channel)) tab = { pool: "random", channel: null };
  renderStatus(data);
  renderPublicLink(data.public);
  renderControls();
}

async function refreshTracks() {
  const query = new URLSearchParams({ pool: tab.pool, ...(tab.channel && { channel: tab.channel }) });
  const { tracks } = await api(`/tracks?${query}`);
  $("tracks").innerHTML = tracks.length
    ? tracks.map((t) => `<li><span class="name">${t.name}</span>
        <button data-del="${encodeURIComponent(t.name)}" title="delete">&times;</button></li>`).join("")
    : "<li class='muted'>empty</li>";
}

async function setMode(mode) {
  const channel = mode === "channel" ? ($("channel").value || null) : state.channel;
  if (mode === "channel" && !channel) return toast("create a channel first");
  try {
    await api("/mode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode, channel, shuffle: $("shuffle").checked }),
    });
  } finally {
    // state is persisted before playout is told, so reflect it even if that failed
    await refreshState();
  }
}

async function upload(files) {
  const body = new FormData();
  body.append("pool", tab.pool);
  if (tab.channel) body.append("channel", tab.channel);
  [...files].forEach((file) => body.append("files", file));

  $("drop").textContent = `uploading ${files.length} file(s)...`;
  try {
    const { stored, rejected } = await api("/tracks", { method: "POST", body });
    toast(`${stored.length} uploaded${rejected.length ? `, ${rejected.length} rejected` : ""}`);
  } catch (error) {
    toast(error.message);
  }
  $("drop").textContent = "drop mp3s here, or click to pick";
  await refreshTracks();
}

document.querySelectorAll(".mode").forEach((button) =>
  button.onclick = () => setMode(button.dataset.mode).catch((e) => toast(e.message)));

$("channel").onchange = () => state.mode === "channel" && setMode("channel");
$("shuffle").onchange = () => state.mode === "channel" && setMode("channel");

$("newChannel").onclick = async () => {
  const name = prompt("channel name (lowercase)");
  if (!name) return;
  try {
    const { channel } = await api("/channels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    await refreshState();
    tab = { pool: "channel", channel };
    renderControls();
    await refreshTracks();
  } catch (error) { toast(error.message); }
};

$("delChannel").onclick = async () => {
  const name = $("channel").value;
  if (!name || !confirm(`delete channel "${name}" and all its files?`)) return;
  await api(`/channels/${encodeURIComponent(name)}`, { method: "DELETE" });
  await refreshState();
  await refreshTracks();
};

$("skip").onclick = () => api("/skip", { method: "POST" }).catch((e) => toast(e.message));

$("copy").onclick = () => {
  const url = state.stream.url;
  navigator.clipboard?.writeText(url).then(() => toast(url), () => toast(url));
};

$("tabs").onclick = (event) => {
  const button = event.target.closest("button[data-pool]");
  if (!button) return;
  tab = { pool: button.dataset.pool, channel: button.dataset.channel || null };
  renderControls();
  refreshTracks();
};

$("tracks").onclick = async (event) => {
  const name = event.target.closest("button[data-del]")?.dataset.del;
  if (!name) return;
  const query = new URLSearchParams({ pool: tab.pool, name: decodeURIComponent(name), ...(tab.channel && { channel: tab.channel }) });
  await api(`/tracks?${query}`, { method: "DELETE" });
  await refreshTracks();
};

$("file").onchange = (event) => upload(event.target.files);
["dragover", "dragleave", "drop"].forEach((type) =>
  $("drop").addEventListener(type, (event) => {
    event.preventDefault();
    $("drop").classList.toggle("over", type === "dragover");
    if (type === "drop") upload(event.dataTransfer.files);
  }));

refreshState().then(refreshTracks).catch((e) => toast(e.message));
setInterval(() => refreshState().catch(() => {}), 5000);
