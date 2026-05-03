/* app.js — Frontend logic for Texts to Audiobooks Creator */

// ── Notification ───────────────────────────────────────────────
function notify(msg, type = "info", duration = 4000) {
  const el = document.getElementById("notify");
  if (!el) return;
  el.textContent = msg;
  el.className = type;
  el.style.display = "block";
  clearTimeout(el._timer);
  el._timer = setTimeout(() => { el.style.display = "none"; }, duration);
}

// ── Tabs ───────────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const group = btn.dataset.group;
      document.querySelectorAll(`.tab-btn[data-group="${group}"]`).forEach(b => b.classList.remove("active"));
      document.querySelectorAll(`.tab-panel[data-group="${group}"]`).forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const target = document.getElementById(btn.dataset.target);
      if (target) target.classList.add("active");
    });
  });
}

// ── File Drop Zone ─────────────────────────────────────────────
function initDropZone() {
  const zone = document.querySelector(".drop-zone");
  if (!zone) return;
  const fileInput = zone.querySelector("input[type='file']");
  const fileLabel = zone.querySelector(".selected-file");

  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("dragover"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("dragover");
    if (e.dataTransfer.files[0]) {
      fileInput.files = e.dataTransfer.files;
      showFile(e.dataTransfer.files[0]);
    }
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files[0]) showFile(fileInput.files[0]);
  });

  function showFile(f) {
    if (fileLabel) fileLabel.textContent = `📎 ${f.name}`;
  }
}

// ── Voice Selection ────────────────────────────────────────────
function initVoiceCards() {
  const cards = document.querySelectorAll(".voice-card");
  const hiddenInput = document.getElementById("voice-input");
  cards.forEach((card) => {
    card.addEventListener("click", (e) => {
      if (e.target.classList.contains("preview-btn")) return;
      cards.forEach(c => c.classList.remove("selected"));
      card.classList.add("selected");
      if (hiddenInput) hiddenInput.value = card.dataset.voice;
    });
  });
  // Select first by default
  if (cards.length && hiddenInput) {
    cards[0].classList.add("selected");
    hiddenInput.value = cards[0].dataset.voice;
  }

  // Preview buttons
  document.querySelectorAll(".preview-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const voice = btn.dataset.voice;
      btn.textContent = "Loading…";
      btn.disabled = true;
      try {
        const res = await fetch("/api/preview-voice", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ voice })
        });
        if (!res.ok) throw new Error("Preview failed");
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.play();
        btn.textContent = "▶ Playing…";
        audio.onended = () => {
          btn.textContent = "▶ Preview";
          btn.disabled = false;
          URL.revokeObjectURL(url);
        };
      } catch (err) {
        notify("Voice preview failed: " + err.message, "error");
        btn.textContent = "▶ Preview";
        btn.disabled = false;
      }
    });
  });
}

// ── Word Count & Duration Estimate ────────────────────────────
const WPM_BASE = 140; // average narration words per minute at 1.0x

function updateTextStats(text) {
  const statsBox = document.getElementById("text-stats");
  if (!statsBox) return;

  const trimmed = text.trim();
  if (!trimmed) {
    statsBox.style.display = "none";
    return;
  }

  const words = trimmed.split(/\s+/).filter(Boolean).length;
  const chars = trimmed.length;
  const speed = parseFloat(document.getElementById("speed-slider")?.value || 1.0);
  const minutes = words / (WPM_BASE * speed);
  const duration = formatDuration(minutes);

  // Detect chapters by "Chapter X" pattern
  const chapterMatches = trimmed.match(/chapter\s+\w+/gi);
  const chapters = chapterMatches ? chapterMatches.length : "—";

  document.getElementById("stat-words").textContent    = words.toLocaleString();
  document.getElementById("stat-chars").textContent    = chars.toLocaleString();
  document.getElementById("stat-duration").textContent = duration;
  document.getElementById("stat-chapters").textContent = chapters;

  statsBox.style.display = "block";
}

function formatDuration(minutes) {
  if (minutes < 1) return `~${Math.round(minutes * 60)}s`;
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  if (h > 0) return `~${h}h ${m}m`;
  return `~${m} min`;
}

function initTextStats() {
  const textarea = document.getElementById("text-input");
  if (!textarea) return;

  textarea.addEventListener("input", () => updateTextStats(textarea.value));

  // Re-calculate when speed changes so duration updates live
  const slider = document.getElementById("speed-slider");
  if (slider) {
    slider.addEventListener("input", () => {
      if (textarea.value.trim()) updateTextStats(textarea.value);
    });
  }
}

// ── Speed Slider ───────────────────────────────────────────────
function initSpeedSlider() {
  const slider = document.getElementById("speed-slider");
  const label = document.getElementById("speed-label");
  if (!slider) return;
  slider.addEventListener("input", () => {
    label.textContent = parseFloat(slider.value).toFixed(2) + "x";
  });
}

// ── Create Project Form ────────────────────────────────────────
function initCreateForm() {
  const form = document.getElementById("create-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const submitBtn = form.querySelector("button[type='submit']");
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Creating…';

    const fd = new FormData(form);
    // Ensure voice is set
    const voiceInput = document.getElementById("voice-input");
    if (voiceInput) fd.set("voice", voiceInput.value);

    try {
      const res = await fetch("/api/create", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed");
      notify("Audiobook creation started!", "success");
      form.reset();
      document.querySelectorAll(".voice-card").forEach(c => c.classList.remove("selected"));
      document.querySelectorAll(".voice-card")[0]?.classList.add("selected");
      if (voiceInput) voiceInput.value = document.querySelectorAll(".voice-card")[0]?.dataset.voice || "";
      document.getElementById("speed-label").textContent = "1.00x";
      // Redirect to project tracker
      setTimeout(() => {
        window.location.href = `/listen/${data.project_id}`;
      }, 1000);
    } catch (err) {
      notify("Error: " + err.message, "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '🎙️ Create Audiobook';
    }
  });
}

// ── Poll Project Status (listen page) ─────────────────────────
function initProjectPoll(projectId) {
  if (!projectId) return;
  const progressBar = document.getElementById("progress-bar");
  const progressText = document.getElementById("progress-text");
  const statusBadge = document.getElementById("status-badge");
  const playerSection = document.getElementById("player-section");
  const errorSection = document.getElementById("error-section");

  async function poll() {
    try {
      const res = await fetch(`/api/project/${projectId}`);
      const data = await res.json();
      if (!res.ok) return;

      const pct = data.progress || 0;
      if (progressBar) progressBar.style.width = pct + "%";
      if (progressText) progressText.textContent = `${pct}% complete`;
      if (statusBadge) {
        statusBadge.textContent = data.status;
        statusBadge.className = `badge badge-${data.status}`;
      }

      if (data.status === "completed") {
        if (playerSection) {
          playerSection.style.display = "block";
          const audioEl = playerSection.querySelector("audio");
          if (audioEl && !audioEl.src.includes(projectId)) {
            audioEl.src = `/stream/${projectId}`;
          }
        }
        return; // Stop polling
      } else if (data.status === "failed") {
        if (errorSection) {
          errorSection.style.display = "block";
          errorSection.querySelector(".error-msg").textContent = data.error_msg || "Unknown error";
        }
        return;
      }
      setTimeout(poll, 2000);
    } catch (_) {
      setTimeout(poll, 3000);
    }
  }
  poll();
}

// ── Batch ZIP Export ───────────────────────────────────────────
async function exportAllZip() {
  const btn = document.getElementById("export-zip-btn");
  const progressBox = document.getElementById("export-progress");
  const progressText = document.getElementById("export-progress-text");

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Preparing…';
  if (progressBox) progressBox.style.display = "block";
  if (progressText) progressText.textContent = "Building ZIP — this may take a moment…";

  try {
    const res = await fetch("/api/export-zip");
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || "Export failed");
    }
    // Stream download via blob
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "audiobooks_export.zip";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    notify("ZIP downloaded successfully!", "success");
  } catch (err) {
    notify("Export failed: " + err.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = "📦 Download All as ZIP";
    if (progressBox) progressBox.style.display = "none";
  }
}

// Show export button only when there are completed audiobooks
async function initExportButton() {
  const btn = document.getElementById("export-zip-btn");
  if (!btn) return;
  try {
    const res = await fetch("/api/export-zip/count");
    const data = await res.json();
    if (data.count > 0) {
      btn.style.display = "inline-flex";
      btn.innerHTML = `📦 Download All as ZIP <span style="background:rgba(255,255,255,.15);border-radius:999px;padding:1px 8px;font-size:.75rem;margin-left:4px;">${data.count}</span>`;
    }
  } catch (_) {}
}

// ── Dashboard: load projects ───────────────────────────────────
function initDashboard() {
  const list        = document.getElementById("project-list");
  const loadMoreBtn = document.getElementById("load-more");
  const searchEl    = document.getElementById("filter-search");
  const statusEl    = document.getElementById("filter-status");
  const voiceEl     = document.getElementById("filter-voice");
  const summaryEl   = document.getElementById("filter-summary");
  if (!list) return;

  let offset = 0;
  let _allProjects = []; // master copy of every loaded project

  // ── Render filtered view ──────────────────────────────────────
  function renderFiltered() {
    const q      = (searchEl?.value || "").toLowerCase().trim();
    const status = statusEl?.value || "";
    const voice  = voiceEl?.value  || "";

    const filtered = _allProjects.filter(p => {
      if (q      && !p.name.toLowerCase().includes(q))  return false;
      if (status && p.status !== status)                 return false;
      if (voice  && p.voice  !== voice)                  return false;
      return true;
    });

    list.innerHTML = "";

    if (filtered.length === 0) {
      const hasFilters = q || status || voice;
      list.innerHTML = hasFilters
        ? `<div class="empty-state"><div class="icon">🔍</div><p>No audiobooks match your filters.<br><button onclick="clearFilters()" class="btn btn-secondary btn-sm" style="margin-top:10px;">Clear Filters</button></p></div>`
        : `<div class="empty-state"><div class="icon">📚</div><p>No audiobooks yet. <a href="/">Create your first one!</a></p></div>`;
    } else {
      filtered.forEach(p => list.insertAdjacentHTML("beforeend", projectCard(p)));
    }

    // Summary line
    if (summaryEl) {
      const hasFilters = q || status || voice;
      if (hasFilters) {
        summaryEl.textContent = `Showing ${filtered.length} of ${_allProjects.length} audiobook${_allProjects.length !== 1 ? "s" : ""}`;
        summaryEl.style.display = "block";
      } else {
        summaryEl.style.display = "none";
      }
    }
  }

  // ── Populate voice dropdown from loaded data ──────────────────
  function refreshVoiceOptions() {
    if (!voiceEl) return;
    const current = voiceEl.value;
    const voices  = [...new Set(_allProjects.map(p => p.voice).filter(Boolean))].sort();
    voiceEl.innerHTML = `<option value="">All Voices</option>` +
      voices.map(v => `<option value="${escHtml(v)}"${v === current ? " selected" : ""}>${escHtml(v)}</option>`).join("");
  }

  // ── Load a page of projects from the API ─────────────────────
  async function loadProjects() {
    try {
      const res      = await fetch(`/api/projects?offset=${offset}`);
      const projects = await res.json();

      if (projects.length === 0 && offset === 0) {
        list.innerHTML = `<div class="empty-state"><div class="icon">📚</div><p>No audiobooks yet. <a href="/">Create your first one!</a></p></div>`;
        if (loadMoreBtn) loadMoreBtn.style.display = "none";
        return;
      }

      // Merge into master list, avoiding duplicates
      const existingIds = new Set(_allProjects.map(p => p.id));
      projects.forEach(p => { if (!existingIds.has(p.id)) _allProjects.push(p); });
      offset += projects.length;

      refreshVoiceOptions();
      renderFiltered();

      if (loadMoreBtn) loadMoreBtn.style.display = projects.length < 10 ? "none" : "block";
      initExportButton();
    } catch (err) {
      notify("Failed to load projects", "error");
    }
  }

  // ── Filter event listeners ────────────────────────────────────
  let searchDebounce;
  searchEl?.addEventListener("input", () => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(renderFiltered, 200);
  });
  statusEl?.addEventListener("change", renderFiltered);
  voiceEl?.addEventListener("change",  renderFiltered);

  // Detect admin mode from the container's data attribute
  const isAdmin = document.querySelector(".container")?.dataset.admin === "true";
  const adminKey = "julisunkan";

  // ── Project card HTML ─────────────────────────────────────────
  function projectCard(p) {
    const date    = p.created_at ? p.created_at.split("T")[0] : "";
    const actions = p.status === "completed"
      ? `<a href="/listen/${p.id}"   class="btn btn-sm btn-secondary">▶ Play</a>
         <a href="/download/${p.id}" class="btn btn-sm btn-success">⬇ Download</a>`
      : (p.status === "processing" || p.status === "queued")
      ? `<a href="/listen/${p.id}" class="btn btn-sm btn-secondary">View Progress</a>`
      : `<a href="/listen/${p.id}" class="btn btn-sm btn-secondary">Details</a>`;

    const deleteBtn = isAdmin
      ? `<button class="btn btn-sm" style="background:rgba(239,68,68,.15);color:#ef4444;border:1px solid rgba(239,68,68,.3);"
           onclick="deleteProject('${p.id}', this)" title="Delete project">🗑</button>`
      : "";

    return `<div class="project-card" data-id="${p.id}" data-status="${p.status}">
      <div>
        <div class="project-name">${escHtml(p.name)}</div>
        <div class="project-meta">Voice: ${escHtml(p.voice)} &bull; ${date}</div>
        ${p.status === "processing" ? `<div class="progress-wrap" style="margin-top:8px"><div class="progress-bar" style="width:${p.progress}%"></div></div>` : ""}
      </div>
      <div class="project-actions">
        <span class="badge badge-${p.status}">${p.status}</span>
        ${actions}
        ${deleteBtn}
      </div>
    </div>`;
  }

  loadProjects();
  if (loadMoreBtn) loadMoreBtn.addEventListener("click", loadProjects);

  // Auto-refresh in-progress items every 5 s
  setInterval(async () => {
    try {
      const res      = await fetch("/api/projects?offset=0");
      const projects = await res.json();
      const anyActive = projects.some(p => p.status === "processing" || p.status === "queued");
      if (anyActive) {
        // Update master list entries that changed
        projects.forEach(fresh => {
          const idx = _allProjects.findIndex(p => p.id === fresh.id);
          if (idx !== -1) _allProjects[idx] = fresh;
          else _allProjects.unshift(fresh);
        });
        renderFiltered();
      }
    } catch (_) {}
  }, 5000);
}

// Called by the "Clear Filters" button rendered inside empty state
function clearFilters() {
  const s = document.getElementById("filter-search");
  const st = document.getElementById("filter-status");
  const v = document.getElementById("filter-voice");
  if (s)  s.value  = "";
  if (st) st.value = "";
  if (v)  v.value  = "";
  // Trigger re-render via the status select's change event
  document.getElementById("filter-status")?.dispatchEvent(new Event("change"));
}

// ── Admin: delete a project ────────────────────────────────────
async function deleteProject(id, btn) {
  if (!confirm("Delete this audiobook permanently? This cannot be undone.")) return;
  btn.disabled = true;
  btn.textContent = "…";
  try {
    const res  = await fetch(`/api/project/${id}/delete?key=julisunkan`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Delete failed");
    // Remove card from DOM and master list
    const card = document.querySelector(`.project-card[data-id="${id}"]`);
    if (card) card.remove();
    // Remove from in-memory store
    const dashFn = window._dashboardAllProjects;
    if (Array.isArray(dashFn)) {
      const idx = dashFn.findIndex(p => p.id === id);
      if (idx !== -1) dashFn.splice(idx, 1);
    }
    notify("Audiobook deleted.", "success");
    initExportButton();
  } catch (err) {
    notify(err.message, "error");
    btn.disabled = false;
    btn.textContent = "🗑";
  }
}

function escHtml(str) {
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// ── Voice sample upload ────────────────────────────────────────
function initVoiceSampleUpload() {
  const btn = document.getElementById("voice-sample-btn");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    const fileInput = document.getElementById("voice-sample-file");
    if (!fileInput || !fileInput.files[0]) {
      notify("Please select an audio file first.", "warning");
      return;
    }
    const fd = new FormData();
    fd.append("voice_sample", fileInput.files[0]);
    btn.disabled = true;
    btn.textContent = "Uploading…";
    try {
      const res = await fetch("/api/upload-voice", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      notify(data.message, "success");
      fileInput.value = "";
    } catch (err) {
      notify("Upload failed: " + err.message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Upload Sample";
    }
  });
}

// ── PWA Service Worker ─────────────────────────────────────────
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/service-worker.js").catch(() => {});
  });
}

// ── Init on DOM ready ──────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initDropZone();
  initVoiceCards();
  initSpeedSlider();
  initTextStats();
  initCreateForm();
  initDashboard();
  initVoiceSampleUpload();

  // Listen page polling
  const pid = document.body.dataset.projectId;
  if (pid) initProjectPoll(pid);
});
