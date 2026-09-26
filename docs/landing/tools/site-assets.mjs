import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const digest = (data) =>
  createHash("sha256").update(data).digest("hex").slice(0, 12);
export async function siteAssets() {
  const names = [
    "styles.css",
    "app.js",
    "tools/content.mjs",
    "tools/setup-content.mjs",
    "tools/generate-locales.mjs",
  ];
  const inputs = await Promise.all(
    names.map((name) => readFile(join(root, name))),
  );
  return {
    style: `styles.${digest(inputs[0])}.css`,
    script: `app.${digest(inputs[1])}.js`,
    revision: digest(Buffer.concat(inputs)),
  };
}
