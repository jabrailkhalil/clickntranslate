document.documentElement.classList.add("js");

document.querySelectorAll("[data-language-choice]").forEach((link) => {
  link.addEventListener("click", () => {
    try {
      localStorage.setItem("clickntranslate-site-language", link.dataset.languageChoice);
    } catch (_) {
      // Language navigation still works when browser storage is unavailable.
    }
  });
});

document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener("click", (event) => {
    const target = document.querySelector(link.getAttribute("href"));
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

const latestReleasePage = "https://github.com/jabrailkhalil/clickntranslate/releases/latest";
const latestReleaseApi = "https://api.github.com/repos/jabrailkhalil/clickntranslate/releases/latest";

const pickLatestWindowsInstaller = (assets = []) => {
  const preferredPatterns = [
    /windows-x64-installer\.exe$/i,
    /windows.*x64.*installer\.exe$/i,
    /windows.*installer\.exe$/i,
  ];

  for (const pattern of preferredPatterns) {
    const asset = assets.find(({ name = "" }) => pattern.test(name));
    if (asset?.browser_download_url) return asset.browser_download_url;
  }

  return latestReleasePage;
};

const updateLatestRelease = async () => {
  try {
    const response = await fetch(latestReleaseApi, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!response.ok) throw new Error(`GitHub API returned ${response.status}`);

    const release = await response.json();
    const latestVersion = release.tag_name || release.name || "latest release";
    const windowsInstaller = pickLatestWindowsInstaller(release.assets);

    document.querySelectorAll("[data-latest-version]").forEach((element) => {
      element.textContent = latestVersion;
    });
    document.querySelectorAll("[data-latest-windows]").forEach((link) => {
      link.href = windowsInstaller;
    });
  } catch {
    // The permanent /releases/latest link remains a working fallback when the
    // public GitHub API is unavailable, rate-limited, or blocked by the browser.
  }
};

updateLatestRelease();
