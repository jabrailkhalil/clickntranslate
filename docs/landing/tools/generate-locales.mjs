// Layout adapted from Astroship by Web3Templates, GPL-3.0. See DESIGN.md.
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { content, languages } from "./content.mjs";
import { setup, setupSources } from "./setup-content.mjs";
import { siteAssets } from "./site-assets.mjs";
const bundle = await siteAssets();
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const origin = "https://xynapse.online/clickntranslate/";
const repo = "https://github.com/jabrailkhalil/clickntranslate";
const latest = `${repo}/releases/latest`;
const esc = (value) =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
const lines = (value) => esc(value).replaceAll("\n", "<br>");
const paths = {
  arrow: '<path d="M7 17 17 7M7 7h10v10"/>',
  down: '<path d="M12 3v12m-5-5 5 5 5-5M5 16v5h14v-5"/>',
  play: '<path d="m9 5 11 7-11 7Z"/>',
  star: '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-2.9-5.6 2.9 1.1-6.2L3 9.6l6.2-.9Z"/>',
  globe:
    '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18Z"/>',
  scan: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M7 12h10"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
  windows:
    '<path d="m3 5 8-1v8H3Zm10-1 8-1v9h-8ZM3 14h8v7l-8-1Zm10 0h8v9l-8-1Z"/>',
  mac: '<rect x="3" y="3" width="18" height="14" rx="2"/><path d="M8 21h8m-4-4v4m-5-9h1m8 0h1m-7 3h4"/>',
  linux:
    '<path d="M5 7h14M5 12l4 3-4 3m8 0h6"/><rect x="2" y="3" width="20" height="19" rx="3"/>',
};
const icon = (name) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]}</svg>`;
const recordings = [
  "translation-demo.gif",
  "area-ocr-demo.gif",
  "fullscreen-translation-demo.gif",
  "selected-text-demo.gif",
];
const shortcuts = [
  "Ctrl + Alt + T",
  "Ctrl + Alt + C",
  "Ctrl + Alt + F",
  "Ctrl + Alt + Q",
];
for (const [lang, t] of Object.entries(content)) {
  const guide = setup[lang];
  const steps = (items) =>
    `<ol class="setup-steps">${items.map(([title, text]) => `<li><h3>${esc(title)}</h3><p>${esc(text)}</p></li>`).join("")}</ol>`;
  const sources = setupSources
    .map((url, i) => `<a href="${url}">${esc(guide.sourceLabels[i])}</a>`)
    .join("");
  const setupSection = `<section class="section setup wrap" id="setup"><div class="section-intro"><h2>${esc(guide.title)}</h2><p>${esc(guide.lead)}</p></div><p class="setup-trust">${esc(guide.trust)}</p><div class="setup-guides"><details id="setup-windows" class="setup-guide"><summary>${icon("windows")}<span>${esc(guide.windows)}</span><span aria-hidden="true">+</span></summary><div class="setup-body">${steps(guide.windowsSteps)}<p class="setup-note">${esc(guide.windowsNote)}</p></div></details><details id="setup-macos" class="setup-guide"><summary>${icon("mac")}<span>${esc(guide.macos)}</span><span aria-hidden="true">+</span></summary><div class="setup-body">${steps(guide.macSteps)}<p class="setup-note">${esc(guide.macNote)}</p><p class="setup-note">${esc(guide.macWarning)}</p></div></details><details id="setup-verify" class="setup-guide"><summary>${icon("lock")}<span>${esc(guide.verify)}</span><span aria-hidden="true">+</span></summary><div class="setup-body"><p>${esc(guide.verifyText)}</p><a class="text-link" href="${latest}">${esc(guide.official)} ${icon("arrow")}</a><p>Windows · PowerShell</p><pre><code>Get-FileHash -LiteralPath &quot;C:\\path\\to\\installer.exe&quot; -Algorithm SHA256</code></pre><p>macOS · Terminal</p><pre><code>shasum -a 256 &quot;/path/to/Click-n-Translate.dmg&quot;</code></pre></div></details></div><div class="setup-start"><h3>${esc(guide.use)}</h3><p>${esc(guide.useText)}</p></div><a class="text-link" href="${repo}/issues">${esc(guide.help)} ${icon("arrow")}</a><details class="setup-sources"><summary>${esc(guide.sources)}</summary><div>${sources}</div></details></section>`;
  const prefix = lang === "en" ? "" : "../",
    url = origin + (lang === "en" ? "" : `${lang}/`),
    asset = (name) => `${prefix}assets/${name}`;
  const languageLinks = Object.entries(languages)
    .map(
      ([code, label]) =>
        `<a href="${prefix}${code === "en" ? "./" : code + "/"}?v=${bundle.revision}" lang="${code}" hreflang="${code}" data-language-choice="${code}" ${code === lang ? 'aria-current="page"' : ""}>${label}<span aria-hidden="true">${code === lang ? "✓" : ""}</span></a>`,
    )
    .join("");
  const downloadLink = (key, label, cls = "download-button") =>
    `<a class="${cls}" data-download="${key}" href="${latest}">${esc(label)} ${icon("down")}</a>`;
  const toggle = () =>
    `<button class="motion-toggle" type="button" data-motion-toggle data-play="${t.motion[0]}" data-stop="${t.motion[1]}">${t.motion[1]}</button>`;
  const placeholder = (poster = true) =>
    `<div class="motion-placeholder ${poster ? "with-poster" : ""}">${poster ? `<img src="${asset("game-poster.png")}" width="1270" height="760" alt="${t.heroAlt}">` : ""}<button type="button" data-motion-play aria-label="${t.motion[0]}">${icon("play")}</button><p>${t.stopped}</p></div>`;
  const html = `<!doctype html>
<html lang="${lang}"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(t.title)}</title><meta name="description" content="${esc(t.description)}"><meta name="theme-color" content="#0b0b0d">
<meta property="og:type" content="website"><meta property="og:title" content="${esc(t.title)}"><meta property="og:description" content="${esc(t.description)}"><meta property="og:image" content="${origin}assets/translation-demo.gif"><meta property="og:url" content="${url}"><link rel="canonical" href="${url}">
${Object.keys(languages)
  .map(
    (code) =>
      `<link rel="alternate" hreflang="${code}" href="${origin}${code === "en" ? "" : code + "/"}">`,
  )
  .join("\n")}<link rel="alternate" hreflang="x-default" href="${origin}">
<link rel="icon" href="${asset("icon.png")}"><link rel="stylesheet" href="${asset("fonts/fonts.css")}"><link rel="stylesheet" href="${prefix}${bundle.style}">
<script type="application/ld+json">${JSON.stringify({ "@context": "https://schema.org", "@type": "SoftwareApplication", name: "Click'n'Translate", applicationCategory: "UtilitiesApplication", operatingSystem: "Windows 10, Windows 11, macOS 13.4+, Linux x86_64", isAccessibleForFree: true, license: `${repo}/blob/main/LICENSE`, url, downloadUrl: latest, codeRepository: repo, description: t.description, offers: { "@type": "Offer", price: "0", priceCurrency: "USD" } })}</script>
<script src="${prefix}${bundle.script}" defer></script></head>
<body id="top" data-locale="${lang}" data-site-revision="${bundle.revision}"><a class="skip-link" href="#main">${t.skip}</a>
<header class="header wrap"><a class="brand" href="https://xynapse.online/" aria-label="Xynapse — xynapse.online"><img src="${asset("xynapse-logo.png")}" width="34" height="34" alt=""><span>Xynapse<span class="brand-dot">.</span></span></a><nav class="desktop-nav" aria-label="${t.nav[0]}"><a href="#how-it-works">${t.nav[0]}</a><a href="#companion">${t.nav[1]}</a><a href="${repo}">GitHub ${icon("arrow")}</a></nav><div class="header-actions"><details class="language-menu"><summary aria-label="${t.language}">${icon("globe")}<span>${lang === "zh-CN" ? "中文" : lang.toUpperCase()}</span><span aria-hidden="true">⌄</span></summary><div class="language-options">${languageLinks}</div></details><a class="button small" href="#download">${t.nav[2]} ${icon("down")}</a></div></header>
<main id="main"><section class="hero wrap"><div class="hero-copy"><p class="eyebrow">${t.eyebrow}</p><h1>${t.hero[0]}<br><span>${t.hero[1]}</span></h1><p class="hero-lead">${t.lead}</p><div class="hero-actions"><a class="button" href="#download">${t.download} ${icon("down")}</a><a class="text-link" href="#how-it-works">${icon("play")}${t.demo}</a></div><p class="microcopy">${t.free}</p><div class="platform-line">${icon("windows")}${icon("mac")}${icon("linux")}<span>${t.release}</span></div></div>
<div class="hero-art"><div class="art-label"><span class="status-dot"></span>Click’n’Translate <span data-latest-version>v1.8.1</span></div><figure class="app-window"><div class="window-bar"><div class="window-dots"><i></i><i></i><i></i></div><span>${t.modes[0][0]}</span>${icon("scan")}</div><div class="recording"><img class="motion-image" src="${asset(recordings[0])}" width="640" height="365" alt="${t.heroAlt}" fetchpriority="high">${placeholder()}</div><figcaption><span><i class="live-dot"></i>${t.recording}</span>${toggle()}</figcaption></figure><div class="shortcut-sticker">${icon("scan")}<kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>T</kbd></div><span class="art-corner" aria-hidden="true">↳</span></div></section>
<div class="proof wrap"><p><strong>3 000<span>+</span></strong><span>${t.stats[0]}</span></p><p><strong>3</strong><span>${t.stats[1]}</span></p><p><strong>100<span>%</span></strong><span>${t.stats[2]}</span></p><a href="${repo}">${icon("star")} Open source<br><span>GPL-3.0 ${icon("arrow")}</span></a></div>
<section class="section demos wrap" id="how-it-works"><div class="section-intro"><div><p class="eyebrow">${t.demoKicker}</p><h2>${t.demoTitle}</h2></div><p>${t.demoLead}</p></div><div class="demo-tabs" role="tablist" aria-label="${t.nav[0]}">${t.modes.map((m, i) => `<button type="button" role="tab" id="tab-${i}" aria-controls="demo-${i}" aria-selected="${i === 0}" tabindex="${i === 0 ? "0" : "-1"}" data-demo-tab="${i}"><span class="tab-number">0${i + 1}</span>${m[0]}</button>`).join("")}</div>
${t.modes.map((m, i) => `<div class="demo-panel" id="demo-${i}" role="tabpanel" aria-labelledby="tab-${i}" tabindex="0" ${i ? "hidden" : ""}><div class="demo-description"><span class="section-number">0${i + 1} / 04</span><h3>${m[1]}</h3><p>${m[2]}</p><span class="key-label"><kbd>${shortcuts[i]}</kbd></span></div><div class="demo-picture"><img class="motion-image" ${i ? "data-src" : "src"}="${asset(recordings[i])}" width="900" height="514" alt="${m[3]}" loading="lazy">${placeholder(i === 0)}${toggle()}</div></div>`).join("")}</section>
<section class="dynamic-band"><div class="feature-row wrap"><div class="feature-copy"><p class="eyebrow">${t.dynamicKicker}</p><h2>${t.dynamicTitle}</h2><p>${t.dynamicText}</p><kbd>Ctrl + Alt + G</kbd><p class="caption">${t.dynamicNote}</p></div><a class="dynamic-picture" href="${asset("dynamic-regions.png")}" target="_blank" rel="noopener"><img src="${asset("dynamic-regions.png")}" width="1467" height="1351" alt="${t.dynamicAlt}" loading="lazy">${icon("arrow")}</a></div></section>
<section class="section companion wrap" id="companion"><div class="feature-row"><div class="companion-picture"><div class="theme-switch" role="group" aria-label="${t.companionNote}">${t.themes.map((label, i) => `<button type="button" aria-pressed="${i === 1}" data-theme-preview="${i === 0 ? "light" : "dark"}">${label}</button>`).join("")}</div><img id="companion-preview" src="${asset("mascot-dark.png")}" data-light="${asset("mascot-light.png")}" data-dark="${asset("mascot-dark.png")}" width="831" height="559" alt="${t.companionAlt}" loading="lazy"></div><div class="feature-copy"><img class="companion-character" src="${asset("companion.png")}" width="72" height="72" alt="" loading="lazy"><p class="eyebrow">${t.companionKicker}</p><h2>${t.companionTitle}</h2><p>${t.companionText}</p><p class="caption">${t.companionNote}</p></div></div></section>
<section class="section control wrap" id="privacy"><p class="eyebrow">${t.controlKicker}</p><h2>${lines(t.controlTitle)}</h2><div class="control-grid">${t.controls.map((c, i) => `<article>${icon(["scan", "globe", "lock"][i])}<h3>${c[0]}</h3><p>${c[1]}</p></article>`).join("")}</div><a class="text-link" href="${repo}/blob/main/PRIVACY.md">${t.privacy}${icon("arrow")}</a></section>
<section class="download-section" id="download"><div class="wrap"><div class="section-intro"><div><p class="eyebrow">${t.downloadKicker}</p><h2>${lines(t.downloadTitle)}</h2></div><div><p>${t.downloadLead}</p><span class="version-pill"><span class="status-dot"></span>${t.version} <span data-latest-version>v1.8.1</span></span></div></div><div class="download-grid"><article class="download-card">${icon("windows")}<h3>Windows</h3><p>${t.platform[0]}</p><div class="download-links">${downloadLink("windows", t.installer)}${downloadLink("portable", t.portable, "secondary-download")}</div><a class="guide-link" href="#setup-windows">${t.installGuide}${icon("arrow")}</a></article><article class="download-card">${icon("mac")}<h3>macOS</h3><p>${t.platform[1]}</p><div class="download-links">${downloadLink("mac-arm", t.silicon)}${downloadLink("mac-intel", t.intel, "secondary-download")}</div><a class="guide-link" href="#setup-macos">${t.installGuide}${icon("arrow")}</a></article><article class="download-card">${icon("linux")}<h3>Linux</h3><p>${t.platform[2]}</p><div class="download-links">${downloadLink("linux", t.appimage)}<p class="linux-note">${t.linuxNote}</p></div><a class="guide-link" href="${repo}/blob/main/docs/LINUX.md">${t.installGuide}${icon("arrow")}</a></article></div><div class="download-footnote"><p>${t.signing}</p><a href="${latest}">${t.allDownloads}${icon("arrow")}</a></div></div></section>
${setupSection}
<section class="section faq wrap" id="faq"><div><p class="eyebrow">FAQ</p><h2>${t.faqTitle}</h2></div><div class="faq-list">${t.faqs.map((f) => `<details><summary>${f[0]}<span aria-hidden="true">+</span></summary><p>${f[1]}</p></details>`).join("")}</div></section>
<section class="community wrap"><div class="community-symbol" aria-hidden="true">✳</div><div><h2>${lines(t.communityTitle)}</h2><p>${t.communityText}</p><div class="hero-actions"><a class="button" href="${repo}">${icon("star")}${t.star}</a><a class="text-link" href="https://t.me/jabrail_digital">${t.telegram}${icon("arrow")}</a></div></div></section></main>
<footer class="wrap"><div><a class="brand" href="#top"><img src="${asset("icon.png")}" width="28" height="28" alt="">Click’n’Translate.</a><p>${t.footer}</p></div><nav><a href="${repo}/issues">${t.issues}</a><a href="${repo}">${t.source}</a><a href="${repo}/blob/main/LICENSE">${t.license}</a><a href="#top">${t.top} ↑</a></nav></footer></body></html>`;
  const directory = lang === "en" ? root : join(root, lang);
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, "index.html"), html, "utf8");
  const guideDirectory = join(root, "..", "guides");
  await mkdir(guideDirectory, { recursive: true });
  const markdownSteps = (items) =>
    items
      .map(([title, text], i) => `### ${i + 1}. ${title}\n\n${text}\n`)
      .join("\n");
  const markdown = `<!-- Generated from docs/landing/tools/setup-content.mjs. -->\n# ${guide.title}\n\n${Object.entries(
    languages,
  )
    .map(([code, label]) =>
      code === lang ? `**${label}**` : `[${label}](setup.${code}.md)`,
    )
    .join(
      " · ",
    )}\n\n${guide.lead}\n\n${guide.trust}\n\n[${guide.official}](${latest})\n\n<a id="windows"></a>\n\n## ${guide.windows}\n\n${markdownSteps(guide.windowsSteps)}\n${guide.windowsNote}\n\n<a id="macos"></a>\n\n## ${guide.macos}\n\n${markdownSteps(guide.macSteps)}\n${guide.macNote}\n\n${guide.macWarning}\n\n## ${guide.use}\n\n${guide.useText}\n\n## ${guide.verify}\n\n${guide.verifyText}\n\nWindows · PowerShell:\n\n\`\`\`powershell\nGet-FileHash -LiteralPath "C:\\path\\to\\installer.exe" -Algorithm SHA256\n\`\`\`\n\nmacOS · Terminal:\n\n\`\`\`sh\nshasum -a 256 "/path/to/Click-n-Translate.dmg"\n\`\`\`\n\n[${guide.help}](${repo}/issues)\n\n## ${guide.sources}\n\n${setupSources.map((url, i) => `- [${guide.sourceLabels[i]}](${url})`).join("\n")}\n`;
  await writeFile(join(guideDirectory, `setup.${lang}.md`), markdown, "utf8");
}
console.log(`Generated ${Object.keys(content).length} localized pages.`);
