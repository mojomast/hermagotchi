import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  ALLOWED_EXTERNAL_IMPORTS,
  DEFAULT_ROOT,
  buildBundle,
} from "../../scripts/build_desktop.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const BUILD_SCRIPT = path.join(ROOT, "scripts", "build_desktop.mjs");
const PLUGIN = path.join(ROOT, "desktop", "plugin.js");

function runBuild(args, cwd = ROOT) {
  return spawnSync(process.execPath, [BUILD_SCRIPT, ...args], {
    cwd,
    encoding: "utf8",
  });
}

test("checked-in plugin.js matches a fresh in-memory build", () => {
  assert.equal(DEFAULT_ROOT, ROOT);
  const generated = buildBundle({ root: ROOT });
  assert.equal(readFileSync(PLUGIN, "utf8"), generated);
  assert.equal(buildBundle({ root: ROOT }), generated);
});

test("plugin.js keeps only allowed external imports and no JSX or dynamic code", () => {
  const plugin = readFileSync(PLUGIN, "utf8");
  const imports = [...plugin.matchAll(/^import\s+.*?from\s+["']([^"']+)["'];$/gm)]
    .map((match) => match[1]);

  assert.ok(imports.length > 0);
  for (const specifier of imports) {
    assert.ok(
      ALLOWED_EXTERNAL_IMPORTS.includes(specifier),
      `unexpected external import ${specifier}`
    );
    assert.ok(!specifier.startsWith("."));
  }

  assert.doesNotMatch(plugin, /^import\s+.*?from\s+["']\./m);
  assert.doesNotMatch(plugin, /\bimport\s*\(/);
  assert.doesNotMatch(plugin, /\beval\s*\(/);
  assert.doesNotMatch(plugin, /\brequire\s*\(/);
  assert.doesNotMatch(plugin, /<[A-Za-z][^>\n]*>/);
});

test("plugin.js registers the pane and injects the stylesheet once", () => {
  const plugin = readFileSync(PLUGIN, "utf8");

  assert.match(plugin, /hermagotchi-desktop-styles/);
  assert.match(plugin, /function register\s*\(ctx\)/);
  assert.match(plugin, /export default __hgPlugin/);
  assert.match(plugin, /injectHermagotchiStyles\(\);/);
  assert.match(plugin, /document\.createElement\("style"\)/);
  assert.match(plugin, /getElementById\(HERMAGOTCHI_STYLE_ID\)/);
  assert.match(plugin, /image-rendering: pixelated/);
  assert.match(plugin, /children: message\.body/);
  assert.match(plugin, /\.hg-log__body/);
  assert.match(plugin, /\.hg-sprite/);
});

test("the build CLI reports the checked-in bundle as current", () => {
  const result = runBuild(["--check"]);
  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.match(result.stdout, /desktop\/plugin\.js is up to date/);
});

test("--check detects a stale bundle and a changed source tree", () => {
  const fixture = mkdtempSync(path.join(ROOT, "tests", "js", ".build-"));
  try {
    const ui = path.join(fixture, "desktop", "src", "ui");
    mkdirSync(ui, { recursive: true });
    writeFileSync(
      path.join(ui, "index.js"),
      [
        'import { jsx } from "react/jsx-runtime";',
        'export { Thing } from "./thing.js";',
        "export function createDesktopPlugin() {",
        '  return { id: "fixture", name: "Fixture", defaultEnabled: false, register: function () { return true; } };',
        "}",
        "export function registerHermagotchiPane() {",
        '  return "registered";',
        "}",
        "",
      ].join("\n")
    );
    writeFileSync(path.join(ui, "thing.js"), "export const Thing = 1;\n");
    writeFileSync(
      path.join(ui, "styles.css"),
      ".hg-sprite { image-rendering: pixelated; }\n"
    );

    const built = runBuild(["--root", fixture]);
    assert.equal(built.status, 0, built.stderr || built.stdout);

    const current = runBuild(["--root", fixture, "--check"]);
    assert.equal(current.status, 0, current.stderr || current.stdout);

    const pluginPath = path.join(fixture, "desktop", "plugin.js");
    writeFileSync(pluginPath, readFileSync(pluginPath, "utf8") + "\n// stale\n");
    const stale = runBuild(["--root", fixture, "--check"]);
    assert.notEqual(stale.status, 0);
    assert.match(stale.stderr, /stale/);

    writeFileSync(path.join(ui, "styles.css"), ".hg-sprite { color: red; }\n");
    const changed = runBuild(["--root", fixture, "--check"]);
    assert.notEqual(changed.status, 0);
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});

test("unknown imports fail the build instead of leaking into plugin.js", () => {
  const fixture = mkdtempSync(path.join(ROOT, "tests", "js", ".build-"));
  try {
    const ui = path.join(fixture, "desktop", "src", "ui");
    mkdirSync(ui, { recursive: true });
    writeFileSync(
      path.join(ui, "index.js"),
      'import { fetch } from "node:fetch";\nexport const value = 1;\n'
    );
    writeFileSync(path.join(ui, "styles.css"), ".hg-sprite {}\n");

    const result = runBuild(["--root", fixture]);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /Unsupported import/);
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});

test("dashboard bundle uses SDK React and never touches host tokens or remote code", async () => {
  const { readFileSync } = await import("node:fs");
  const text = readFileSync(new URL("../../dashboard/dist/index.js", import.meta.url), "utf8");
  assert.match(text, /SDK\.React/);
  assert.match(text, /authedFetch/);
  for (const bad of ["esm.sh", "__HERMES_SESSION_TOKEN__", "sessionStorage", "window.fetch =", "importmap", "iframe"]) {
    assert.equal(text.includes(bad), false, bad);
  }
  const desktop = readFileSync(new URL("../../desktop/plugin.js", import.meta.url), "utf8");
  for (const bad of ["__HERMES_SESSION_TOKEN__", "sessionStorage", "hermes.webapp.session"]) {
    assert.equal(desktop.includes(bad), false, bad);
  }
});
