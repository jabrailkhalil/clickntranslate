const releasePage =
  "https://github.com/jabrailkhalil/clickntranslate/releases/latest";
const releaseApi =
  "https://api.github.com/repos/jabrailkhalil/clickntranslate/releases/latest";
const supported = ["en", "ru", "es", "de", "fr", "zh-CN"];
// Explicit locale URLs win. Only the root selects a language automatically.
if (document.body.dataset.locale === "en") {
  try {
    const saved = localStorage.getItem("clickntranslate-site-language");
    const preferred = (
      navigator.languages?.[0] ||
      navigator.language ||
      "en"
    ).toLowerCase();
    const detected = preferred.startsWith("zh")
      ? "zh-CN"
      : preferred.split("-")[0];
    const locale = supported.includes(saved) ? saved : detected;
    if (supported.includes(locale) && locale !== "en") {
      const destination = new URL(`${locale}/`, document.baseURI);
      destination.searchParams.set("v", document.body.dataset.siteRevision);
      destination.hash = location.hash;
      location.replace(destination.href);
    }
  } catch {
    /* English remains usable without storage. */
  }
}
document.querySelectorAll("[data-language-choice]").forEach((link) =>
  link.addEventListener("click", () => {
    try {
      localStorage.setItem(
        "clickntranslate-site-language",
        link.dataset.languageChoice,
      );
    } catch {
      /* Links still work. */
    }
  }),
);
const languageMenu = document.querySelector(".language-menu");
document.addEventListener("click", (event) => {
  if (!languageMenu.contains(event.target)) languageMenu.open = false;
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && languageMenu.open) {
    languageMenu.open = false;
    languageMenu.querySelector("summary").focus();
  }
});
const tabs = [...document.querySelectorAll("[data-demo-tab]")];
const showDemo = (tab, focus = false) => {
  tabs.forEach((item) => {
    const selected = item === tab;
    item.setAttribute("aria-selected", String(selected));
    item.tabIndex = selected ? 0 : -1;
    const panel = document.getElementById(item.getAttribute("aria-controls"));
    panel.hidden = !selected;
    if (selected) {
      const image = panel.querySelector("img[data-src]");
      if (image) {
        image.src = image.dataset.src;
        image.removeAttribute("data-src");
      }
    }
  });
  if (focus) tab.focus();
};
tabs.forEach((tab, index) => {
  tab.addEventListener("click", () => showDemo(tab));
  tab.addEventListener("keydown", (event) => {
    let next;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    if (event.key === "ArrowLeft")
      next = (index - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = tabs.length - 1;
    if (next !== undefined) {
      event.preventDefault();
      showDemo(tabs[next], true);
    }
  });
});
document.querySelectorAll("[data-theme-preview]").forEach((button) =>
  button.addEventListener("click", () => {
    const image = document.getElementById("companion-preview");
    image.src = image.dataset[button.dataset.themePreview];
    document
      .querySelectorAll("[data-theme-preview]")
      .forEach((item) =>
        item.setAttribute("aria-pressed", String(item === button)),
      );
  }),
);
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
let motionAllowed = !reducedMotion.matches;
let motionChosen = false;
const updateMotion = () => {
  document.documentElement.classList.toggle("no-motion", !motionAllowed);
  document.documentElement.classList.toggle("allow-motion", motionAllowed);
  document.querySelectorAll("[data-motion-toggle]").forEach((button) => {
    button.textContent = motionAllowed
      ? button.dataset.stop
      : button.dataset.play;
    button.setAttribute("aria-pressed", String(motionAllowed));
  });
};
document.querySelectorAll("[data-motion-toggle]").forEach((button) =>
  button.addEventListener("click", () => {
    motionChosen = true;
    motionAllowed = !motionAllowed;
    updateMotion();
  }),
);
reducedMotion.addEventListener("change", (event) => {
  if (!motionChosen) {
    motionAllowed = !event.matches;
    updateMotion();
  }
});
updateMotion();
document.querySelectorAll("[data-motion-play]").forEach((button) =>
  button.addEventListener("click", () => {
    motionChosen = true;
    motionAllowed = true;
    updateMotion();
  }),
);
// Versioned asset names require resolving the latest stable release first.
const patterns = {
  windows: /windows-x64-installer\.exe$/i,
  portable: /windows-portable-x64\.zip$/i,
  "mac-arm": /macos-arm64\.dmg$/i,
  "mac-intel": /macos-x86_64\.dmg$/i,
  linux: /linux-x86_64\.AppImage$/i,
};
async function updateDownloads() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 6500);
  try {
    const response = await fetch(releaseApi, {
      headers: { Accept: "application/vnd.github+json" },
      signal: controller.signal,
    });
    if (!response.ok) return;
    const release = await response.json();
    if (release.draft || release.prerelease || !Array.isArray(release.assets))
      return;
    document.querySelectorAll("[data-latest-version]").forEach((element) => {
      element.textContent = release.tag_name || "Latest";
    });
    document.querySelectorAll("[data-download]").forEach((link) => {
      const pattern = patterns[link.dataset.download];
      const asset = release.assets.find(
        (item) => pattern.test(item.name || "") && item.state === "uploaded",
      );
      link.href = asset?.browser_download_url?.startsWith(
        "https://github.com/jabrailkhalil/clickntranslate/releases/download/",
      )
        ? asset.browser_download_url
        : releasePage;
    });
  } catch {
    /* Links retain the latest-release page on timeout, API limits or offline use. */
  } finally {
    clearTimeout(timeout);
  }
}
updateDownloads();
