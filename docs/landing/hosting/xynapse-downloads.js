(() => {
  const board = document.getElementById("download-board");
  if (!board) return;
  const total = document.getElementById("download-total");
  const label = document.getElementById("download-total-label");
  const status = document.getElementById("download-status");
  const filter = document.getElementById("download-platform");
  const number = new Intl.NumberFormat("en");
  const rows = [...board.querySelectorAll("[data-project]")];
  let projects = null;
  let fetchedAt = 0;
  let loading = false;

  function render() {
    if (!projects) return;
    const platform = filter.value;
    const values = projects.filter((p) => p.kind === "download").map((p) => ({
      ...p, value: p.total === null ? null : platform === "all" ? p.total : p.platforms[platform],
    }));
    const known = values.filter((p) => p.value !== null);
    const sum = known.reduce((n, p) => n + p.value, 0);
    const max = Math.max(1, ...known.map((p) => p.value));
    total.textContent = known.length ? number.format(sum) : "—";
    const scope = platform === "all" ? "package downloads" : `${filter.selectedOptions[0].textContent} downloads`;
    label.textContent = `${scope} · all releases${known.length < values.length ? " · partial data" : ""}`;
    for (const row of rows) {
      const project = values.find((p) => p.id === row.dataset.project);
      if (!project) continue; // goallog is explicitly shown as a web app.
      const count = row.querySelector("[data-count]");
      const bar = row.querySelector("[data-bar]");
      const note = row.querySelector("[data-note]");
      count.textContent = project.value === null ? "—" : number.format(project.value);
      bar.style.width = `${project.value === null ? 0 : (project.value / max) * 100}%`;
      row.classList.toggle("is-unavailable", project.value === null);
      note.textContent = project.value === null ? "Count temporarily unavailable" :
        `${project.releases} releases${project.status === "stale" ? " · last saved count" : ""}`;
      row.querySelector("[data-track]").setAttribute("aria-label",
        `${project.name}: ${project.value === null ? "count unavailable" : number.format(project.value) + " downloads"}`);
    }
    document.getElementById("download-scale").textContent = number.format(Math.max(0, ...known.map((p) => p.value)));
    const dates = known.map((p) => Date.parse(p.checkedAt)).filter(Number.isFinite);
    const oldest = dates.length ? Math.min(...dates) : null;
    const delayed = values.some((p) => p.status !== "ok") || oldest === null || Date.now() - oldest > 90 * 60_000;
    status.classList.toggle("is-delayed", delayed);
    if (oldest !== null) {
      const date = new Date(oldest);
      const dateText = date.toLocaleString("en", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
      status.textContent = `${delayed ? "Updates delayed · saved" : "Updated"} ${dateText}`;
    } else {
      status.textContent = "Download counts temporarily unavailable";
    }
  }

  function validate(payload) {
    if (payload.schemaVersion !== 1 || !Array.isArray(payload.projects)) throw new Error("Invalid statistics");
    for (const id of ["clickntranslate", "xynapse"]) {
      const p = payload.projects.find((entry) => entry.id === id);
      if (!p || p.kind !== "download" || !["ok", "stale", "unavailable"].includes(p.status)) throw new Error("Missing project");
      if (p.total !== null) {
        const counts = ["windows", "macos", "linux", "other"].map((key) => p.platforms?.[key]);
        if (![p.total, ...counts].every((n) => Number.isSafeInteger(n) && n >= 0) ||
            counts.reduce((sum, n) => sum + n, 0) !== p.total || !Number.isFinite(Date.parse(p.checkedAt))) {
          throw new Error("Invalid counts");
        }
      }
    }
    return payload.projects;
  }

  async function refresh() {
    if (loading) return;
    loading = true;
    board.setAttribute("aria-busy", "true");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch("/statistics/downloads.json", {
        cache: "no-store", signal: controller.signal, headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("Statistics unavailable");
      projects = validate(await response.json());
      fetchedAt = Date.now();
      render();
      filter.disabled = false;
    } catch {
      status.textContent = projects ? "Could not refresh · showing previous counts" : "Download counts temporarily unavailable";
      status.classList.add("is-delayed");
      if (!projects) label.textContent = "Try again later";
    } finally {
      clearTimeout(timeout);
      loading = false;
      board.setAttribute("aria-busy", "false");
    }
  }

  filter.addEventListener("change", render);
  setInterval(() => { if (!document.hidden) refresh(); }, 30 * 60_000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && Date.now() - fetchedAt > 30 * 60_000) refresh();
  });
  refresh();
})();
