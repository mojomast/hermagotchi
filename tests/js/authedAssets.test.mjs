import test from "node:test";
import assert from "node:assert/strict";
import {
  clearAuthedAssetCache,
  resolveAuthedAssetUrl,
  authedAssetCacheSize,
  assetDataPath,
  isAuthedFetchSafeUrl,
} from "../../desktop/src/ui/logic/authedAssets.js";

test("resolveAuthedAssetUrl passes through data and blob URLs", async () => {
  clearAuthedAssetCache();
  assert.equal(await resolveAuthedAssetUrl("data:image/png;base64,aaa"), "data:image/png;base64,aaa");
  assert.equal(await resolveAuthedAssetUrl("blob:http://localhost/1"), "blob:http://localhost/1");
  assert.equal(authedAssetCacheSize(), 0);
});

test("resolveAuthedAssetUrl fetches without any host token and returns an object URL", async () => {
  clearAuthedAssetCache();
  const calls = [];
  const blob = new Blob([Uint8Array.from([1, 2, 3])], { type: "image/png" });
  const url = await resolveAuthedAssetUrl("/api/plugins/hermagotchi/assets/px3/npcs/don_piedro_portrait.png", {
    fetchImpl: async (input, init) => {
      calls.push({ input, init });
      return { ok: true, status: 200, async blob() { return blob; } };
    },
  });
  assert.match(url, /^blob:/);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].init.method, "GET");
  assert.equal(calls[0].init.headers, undefined);
  assert.equal(authedAssetCacheSize(), 1);
  const again = await resolveAuthedAssetUrl("/api/plugins/hermagotchi/assets/px3/npcs/don_piedro_portrait.png", {
    fetchImpl: async () => {
      throw new Error("should not fetch again");
    },
  });
  assert.equal(again, url);
  clearAuthedAssetCache();
});

test("Desktop assets load through ctx.rest /assets-data and become blob URLs", async () => {
  clearAuthedAssetCache();
  const calls = [];
  const rest = async (path, opts) => {
    calls.push({ path, opts });
    return { ok: true, status: "ok", mime: "image/png", data_b64: "AQID" };
  };
  const url = await resolveAuthedAssetUrl("/api/plugins/hermagotchi/assets/px3/x.png", { rest });
  assert.match(url, /^blob:/);
  assert.equal(calls[0].path, "/assets-data/px3/x.png");
  assert.equal(calls[0].opts.method, "GET");
  clearAuthedAssetCache();
});

test("assetDataPath refuses traversal", () => {
  assert.equal(assetDataPath("/api/plugins/hermagotchi/assets/../secret"), "");
  assert.equal(assetDataPath("/nope"), "");
  assert.equal(assetDataPath("/api/plugins/hermagotchi/assets/a/b.png?x=1"), "/assets-data/a/b.png");
});

test("resolveAuthedAssetUrl returns empty string on 401 and does not keep a bad cache entry", async () => {
  clearAuthedAssetCache();
  const url = await resolveAuthedAssetUrl("/api/plugins/hermagotchi/assets/px3/x.png", {
    fetchImpl: async () => ({ ok: false, status: 401, async blob() { return new Blob(); } }),
  });
  assert.equal(url, "");
  assert.equal(authedAssetCacheSize(), 0);
});

test("isAuthedFetchSafeUrl allows only the plugin assets route", () => {
  assert.equal(isAuthedFetchSafeUrl("/api/plugins/hermagotchi/assets/px3/x.png"), true);
  assert.equal(isAuthedFetchSafeUrl("/api/plugins/hermagotchi/assets-data/px3/x.png"), true);
  assert.equal(isAuthedFetchSafeUrl("/assets-data/px3/x.png"), true);
  assert.equal(isAuthedFetchSafeUrl("https://other.host/x.png"), false);
  assert.equal(isAuthedFetchSafeUrl("http://127.0.0.1/assets/x.png"), false);
  assert.equal(isAuthedFetchSafeUrl("//evil.example/x.png"), false);
  assert.equal(isAuthedFetchSafeUrl("javascript:alert(1)"), false);
  assert.equal(isAuthedFetchSafeUrl("/api/plugins/hermagotchi/other/x.png"), false);
  assert.equal(isAuthedFetchSafeUrl("px3/x.png"), false);
  assert.equal(isAuthedFetchSafeUrl("data:image/png;base64,aaa"), false);
});

test("resolveAuthedAssetUrl never calls authedFetch with an absolute URL", async () => {
  clearAuthedAssetCache();
  const calls = [];
  const fetchImpl = async (input) => {
    calls.push(input);
    return { ok: true, status: 200, async blob() { return new Blob([Uint8Array.from([1])]); } };
  };
  for (const url of [
    "https://other.host/x.png",
    "http://other.host/x.png",
    "//other.host/x.png",
    "javascript:alert(1)",
    "/api/plugins/other/file.png",
  ]) {
    const resolved = await resolveAuthedAssetUrl(url, { fetchImpl, authedFetch: fetchImpl });
    assert.equal(resolved, "", url);
  }
  assert.equal(calls.length, 0);
  assert.equal(authedAssetCacheSize(), 0);
  clearAuthedAssetCache();
});
