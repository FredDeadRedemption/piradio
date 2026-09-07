const $ = (id) => document.getElementById(id);
const DAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"];
const DROP_TEXT = "drop audio here, or click to pick";

let state = { mode: "random", channel: null, shuffle: false, channels: [], station: {} };
let tab = { pool: "random", channel: null };
let schedule = { enabled: false, entries: [] };
let renderedChannels = null;

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

const describe = (entry) => (entry.mode === "channel" ? entry.channel : entry.mode);

function renderStatus(data) {
  document.title = data.station.name;
  $("station").textContent = data.station.name;
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
    $("public").textContent = `public station → ${url.replace(/^https?:\/\//, "")}`;
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

function renderNext(info) {
  if (!info.enabled) return ($("next").textContent = "");
  if (!info.next) return ($("next").textContent = "no slots yet");
  const lead = info.manual ? "on hold, next" : "next";
  $("next").textContent = `${lead} ${info.next.day} ${info.next.entry.start} · ${describe(info.next.entry)}`;
}

function slotOptions(entry) {
  const chosen = entry.mode === "channel" ? `channel:${entry.channel}` : entry.mode;
  return ["random", "segments", ...state.channels.map((c) => `channel:${c}`)]
    .map((value) => {
      const label = value.startsWith("channel:") ? value.slice(8) : value;
      return `<option value="${value}"${value === chosen ? " selected" : ""}>${label}</option>`;
    })
    .join("");
}

function slotRow(entry) {
  const days = DAY_LABELS.map((label, day) =>
    `<button type="button" class="day${entry.days.includes(day) ? " on" : ""}" data-day="${day}">${label}</button>`).join("");
  const shuffle = entry.mode === "channel"
    ? `<label class="check"><input type="checkbox" class="sh"${entry.shuffle ? " checked" : ""}> shuffle</label>`
    : "";
  return `<div class="slot" data-id="${entry.id}">
    <div class="days">${days}</div>
    <input class="time" type="time" value="${entry.start}">
    <select class="what">${slotOptions(entry)}</select>
    ${shuffle}
    <button type="button" class="rm" title="remove slot">&times;</button>
  </div>`;
}

function renderSchedule() {
  $("scheduled").checked = schedule.enabled;
  renderedChannels = state.channels.join(" ");
  $("slots").innerHTML = schedule.entries.length
    ? schedule.entries.map(slotRow).join("")
    : "<p class='muted'>no slots yet</p>";
}

async function refreshState() {
  const data = await api("/state");
  state = data;
  if (tab.pool === "channel" && !state.channels.includes(tab.channel)) tab = { pool: "random", channel: null };
  renderStatus(data);
  renderPublicLink(data.public);
  renderControls();
  renderNext(data.schedule);
  // re-rendering on every poll would steal focus from a slot being edited
  if (state.channels.join(" ") !== renderedChannels) renderSchedule();
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

async function saveSchedule() {
  try {
    schedule = await api("/schedule", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: $("scheduled").checked, entries: schedule.entries }),
    });
  } catch (error) {
    toast(error.message);
    // the save was refused, so fall back to what is actually stored
    schedule = await api("/schedule");
  }
  renderSchedule();
  await refreshState();
}

async function upload(files) {
  const body = new FormData();
  body.append("pool", tab.pool);
  if (tab.channel) body.append("channel", tab.channel);
  [...files].forEach((file) => body.append("files", file));

  $("dropText").textContent = `uploading ${files.length} file(s)...`;
  try {
    const { stored, rejected } = await api("/tracks", { method: "POST", body });
    toast(`${stored.length} uploaded${rejected.length ? `, ${rejected.length} rejected` : ""}`);
  } catch (error) {
    toast(error.message);
  }
  $("dropText").textContent = DROP_TEXT;
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
  schedule = await api("/schedule");
  await refreshState();
  renderSchedule();
  await refreshTracks();
};

$("skip").onclick = () => api("/skip", { method: "POST" }).catch((e) => toast(e.message));

$("copy").onclick = () => {
  const url = state.stream.url;
  navigator.clipboard?.writeText(url).then(() => toast(url), () => toast(url));
};

$("scheduled").onchange = () => saveSchedule();

$("addSlot").onclick = () => {
  schedule.entries.push({ days: [0, 1, 2, 3, 4, 5, 6], start: "08:00", mode: "random", channel: null, shuffle: false });
  saveSchedule();
};

$("slots").onclick = (event) => {
  const row = event.target.closest(".slot");
  const entry = schedule.entries.find((e) => e.id === row?.dataset.id);
  if (!entry) return;

  const day = event.target.closest("button.day");
  if (day) {
    const number = Number(day.dataset.day);
    const days = entry.days.includes(number)
      ? entry.days.filter((d) => d !== number)
      : [...entry.days, number].sort();
    if (!days.length) return toast("a slot needs at least one day");
    entry.days = days;
  } else if (event.target.closest("button.rm")) {
    schedule.entries = schedule.entries.filter((e) => e !== entry);
  } else {
    return;
  }
  saveSchedule();
};

$("slots").onchange = (event) => {
  const row = event.target.closest(".slot");
  const entry = schedule.entries.find((e) => e.id === row?.dataset.id);
  if (!entry) return;
  const field = event.target;

  if (field.classList.contains("time")) entry.start = field.value;
  if (field.classList.contains("sh")) entry.shuffle = field.checked;
  if (field.classList.contains("what")) {
    entry.mode = field.value.startsWith("channel:") ? "channel" : field.value;
    entry.channel = field.value.startsWith("channel:") ? field.value.slice(8) : null;
  }
  saveSchedule();
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

api("/schedule")
  .then((saved) => { schedule = saved; })
  .then(refreshState)
  .then(renderSchedule)
  .then(refreshTracks)
  .catch((e) => toast(e.message));
setInterval(() => refreshState().catch(() => {}), 5000);
