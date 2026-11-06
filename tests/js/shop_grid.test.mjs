import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const UI = path.join(ROOT, "desktop", "src", "ui");

function source(relativePath) {
  return readFileSync(path.join(UI, relativePath), "utf8");
}

const SHOP = source("tabs/ShopTab.js");
const TURN_LOG = source("components/TurnLog.js");
const SETTINGS = source("tabs/SettingsTab.js");
const PANE = source("pane.js");
const STYLES = source("styles.css");

test("ShopTab keeps the stub table contract alongside the live grid", () => {
  assert.match(SHOP, /export const SHOP_PLACEHOLDER_ITEMS/);
  for (const needle of ["Bits balance", "Price", "Buy (disabled)", "Preview only"]) {
    assert.ok(SHOP.includes(needle), `missing stub copy: ${needle}`);
  }
  assert.ok(SHOP.includes("hg-table"), "stub mode must keep its table");
});

test("ShopTab renders a tiled merch grid with slot filters and search", () => {
  for (const className of [
    "hg-shop-grid",
    "hg-shop-card",
    "hg-shop-card__thumb",
    "hg-shop-card__name",
    "hg-shop-card__price",
    "hg-shop-card__actions",
    "hg-shop-tabs",
  ]) {
    assert.ok(SHOP.includes(className), `missing ${className}`);
  }
  for (const label of ["All", "Hats", "Face", "Neck/Back", "Hand props", "Auras"]) {
    assert.ok(SHOP.includes('"' + label + '"'), `missing filter label ${label}`);
  }
  assert.match(SHOP, /type:\s*"search"/);
  assert.ok(SHOP.includes("PetPreview"), "live shop keeps the composed pet preview");
  assert.ok(!SHOP.includes("logic/assets.js"), "ShopTab may not import assets.js");
});

test("TurnLog rows expose explicit, grid-addressable column wrappers", () => {
  assert.ok(TURN_LOG.includes("formatTurnLog"));
  for (const className of [
    "hg-log__round",
    "hg-log__actor",
    "hg-log__move",
    "hg-log__damage",
    "hg-log__types",
    "hg-log__effect",
    "hg-log__hp",
  ]) {
    assert.ok(TURN_LOG.includes(className), `missing turn-log column ${className}`);
  }
});

test("styles.css lays out the shop grid, turn log columns and portraits", () => {
  assert.match(
    STYLES,
    /\.hg-shop-grid\s*\{[^}]*grid-template-columns:\s*repeat\(auto-fill,\s*minmax\(/s
  );
  assert.match(STYLES, /\.hg-log__item\s*\{[^}]*display:\s*grid/s);
  assert.match(STYLES, /\.hg-log__item\s*\{[^}]*grid-template-areas/s);
  assert.match(STYLES, /\.hg-npc-host__portrait\s*\{[^}]*width:\s*(?:48|56|64)px/s);
  assert.match(STYLES, /\.hg-shop-card__thumb[^{]*\{[^}]*image-rendering:\s*pixelated/s);
});

test("SettingsTab and the pane derive live status from connection helpers", () => {
  assert.match(SETTINGS, /export const SETTINGS_PLACEHOLDER/);
  assert.ok(SETTINGS.includes("connectionRows"));
  assert.ok(SETTINGS.includes("deriveConnectionStatus"));
  assert.ok(PANE.includes("deriveConnectionStatus"));
  assert.ok(PANE.includes("resolveConnectionUiState"));
  assert.ok(PANE.includes("StateNotice"));
});
