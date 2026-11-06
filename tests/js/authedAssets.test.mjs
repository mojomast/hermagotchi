import test from "node:test";
import assert from "node:assert/strict";
import {
  clearAuthedAssetCache,
  resolveAuthedAssetUrl,
  authedAssetCacheSize,
} from "../../desktop/src/ui/logic/authedAssets.js";

test("resolveAuthedAssetUrl passes through data and blob URLs", async () => {
  clearAuthedAssetCache();
  assert.equal(await resolveAuthedAssetUrl("data:image/png;base64,aaa"), "data:image/png;base64,aaa");
  assert.equal(await resolveAuthedAssetUrl("blob:http://localhost/1"), "blob:http://localhost/1");
  assert.equal(authedAssetCacheSize(), 0);
});

test("resolveAuthedAssetUrl fetches with credentials and returns an object URL", async () => {
  clearAuthedAssetCache();
  const calls = [];
  const blob = new Blob([Uint8Array.from([1, 2, 3])], { type: "image/png" });
  const fakeSession = {
    length: 1,
    key(i) { return i === 0 ? 'hermes.webapp.session.v1:["http://127.0.0.1:9120",""]' : null; },
    getItem(k) { return k.startsWith("hermes.webapp.session.v1:") ? "tok_webapp" : null; },
  };
  const url = await resolveAuthedAssetUrl("/api/plugins/hermagotchi/assets/px3/npcs/don_piedro_portrait.png", {
    sessionStorage: fakeSession,
    fetchImpl: async (input, init) => {
      calls.push({ input, init });
      return {
        ok: true,
        status: 200,
        async blob() {
          return blob;
        },
      };
    },
  });
  assert.match(url, /^blob:/);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].input, "/api/plugins/hermagotchi/assets/px3/npcs/don_piedro_portrait.png");
  assert.equal(calls[0].init.credentials, "same-origin");
  assert.equal(calls[0].init.method, "GET");
  assert.equal(calls[0].init.headers["X-Hermes-Session-Token"], "tok_webapp");
  assert.equal(authedAssetCacheSize(), 1);
  // Second call hits cache (no extra fetch)
  const again = await resolveAuthedAssetUrl("/api/plugins/hermagotchi/assets/px3/npcs/don_piedro_portrait.png", {
    fetchImpl: async () => {
      throw new Error("should not fetch again");
    },
  });
  assert.equal(again, url);
  clearAuthedAssetCache();
});

test("resolveAuthedAssetUrl returns empty string on 401 and does not keep a bad cache entry", async () => {
  clearAuthedAssetCache();
  const url = await resolveAuthedAssetUrl("/api/plugins/hermagotchi/assets/px3/x.png", {
    fetchImpl: async () => ({ ok: false, status: 401, async blob() { return new Blob(); } }),
  });
  assert.equal(url, "");
  assert.equal(authedAssetCacheSize(), 0);
});
