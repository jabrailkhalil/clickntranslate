import { copyFile, mkdir, rm } from "node:fs/promises";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const output = resolve(root, "dist");
if (relative(root, output) !== "dist") throw new Error("Refusing to clean an unexpected output directory.");

await rm(output, { recursive: true, force: true });

const files = [
  "index.html",
  "app.js",
  "styles.css",
  "robots.txt",
  "sitemap.xml",
  "ru/index.html",
  "es/index.html",
  "de/index.html",
  "fr/index.html",
  "zh-CN/index.html",
  "assets/icon.png",
  "assets/translation-demo.gif",
  "assets/area-ocr-demo.gif",
  "assets/selected-text-demo.gif",
  "assets/fullscreen-translation-demo.gif",
  "assets/update-demo.gif",
];

for (const file of files) {
  const source = join(root, file);
  const destination = join(output, file);
  await mkdir(dirname(destination), { recursive: true });
  await copyFile(source, destination);
}

console.log(`Built ${files.length} public files in ${output}`);
