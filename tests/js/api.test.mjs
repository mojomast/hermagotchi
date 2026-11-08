import test from "node:test";
import assert from "node:assert/strict";

import {
  createApiClient,
  uiStateFromEnvelope,
  DEFAULT_BASE_PATH,
  PROXY_PREFIX,
} from "../../desktop/src/ui/api.js";

function jsonResponse(body, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status: status,
    async json() {
      return body;
    },
  };
}

function recorder(body, status = 200) {
  const calls = [];
  async function fetchImpl(url, init) {
    calls.push({ url: url, init: init });
    return jsonResponse(body, status);
  }
  return { calls: calls, fetchImpl: fetchImpl };
}

test("client defaults to the local bridge base path", () => {
  assert.equal(DEFAULT_BASE_PATH, "/api/plugins/hermagotchi");
  assert.equal(PROXY_PREFIX, "/proxy/v1");
  const client = createApiClient({ fetchImpl: async () => jsonResponse({}) });
  assert.equal(client.basePath, DEFAULT_BASE_PATH);
});

test("get resolves the bridge envelope and prefixes the proxy path", async () => {
  const rec = recorder({ ok: true, status: "ok", data: { balance: 7 } });
  const client = createApiClient({ fetchImpl: rec.fetchImpl });

  const envelope = await client.get("/wallet");

  assert.deepEqual(envelope, { ok: true, status: "ok", data: { balance: 7 } });
  assert.equal(rec.calls.length, 1);
  assert.equal(rec.calls[0].url, "/api/plugins/hermagotchi/proxy/v1/wallet");
  assert.equal(rec.calls[0].init.method, "GET");
});

test("custom base path is honoured and trailing slashes are trimmed", async () => {
  const rec = recorder({ ok: true, status: "ok", data: {} });
  const client = createApiClient({
    fetchImpl: rec.fetchImpl,
    basePath: "/custom/bridge/",
  });

  await client.get("catalog");

  assert.equal(rec.calls[0].url, "/custom/bridge/proxy/v1/catalog");
});

test("post sends JSON and an explicit idempotency key", async () => {
  const rec = recorder({ ok: true, status: "ok", data: { bought: true } });
  const client = createApiClient({ fetchImpl: rec.fetchImpl });

  const envelope = await client.post(
    "/shop/purchases",
    { item_id: "item.crown" },
    { idempotencyKey: "idem-42" }
  );

  assert.equal(envelope.data.bought, true);
  const call = rec.calls[0];
  assert.equal(call.url, "/api/plugins/hermagotchi/proxy/v1/shop/purchases");
  assert.equal(call.init.method, "POST");
  assert.equal(call.init.headers["Content-Type"], "application/json");
  assert.equal(call.init.headers["Idempotency-Key"], "idem-42");
  assert.deepEqual(JSON.parse(call.init.body), { item_id: "item.crown" });
});

test("mutations generate an idempotency key when absent", async () => {
  const rec = recorder({ ok: true, status: "ok", data: {} });
  const client = createApiClient({ fetchImpl: rec.fetchImpl });

  await client.post("/goals/clear", {});
  await client.del("/blocks/block_1");

  const firstKey = rec.calls[0].init.headers["Idempotency-Key"];
  const secondKey = rec.calls[1].init.headers["Idempotency-Key"];
  assert.equal(typeof firstKey, "string");
  assert.ok(firstKey.length >= 8);
  assert.equal(typeof secondKey, "string");
  assert.ok(secondKey.length >= 8);
  assert.equal(rec.calls[1].init.method, "DELETE");
});

test("fetch failures resolve to an offline envelope", async () => {
  const client = createApiClient({
    fetchImpl: async () => {
      throw new Error("bridge down");
    },
  });

  const envelope = await client.get("/wallet");

  assert.equal(envelope.ok, false);
  assert.equal(envelope.status, "offline");
  assert.equal(envelope.error.code, "network_error");
  assert.equal(envelope.error.retry_after_s, 0);
});

test("non-envelope responses are wrapped as an http_error", async () => {
  const client = createApiClient({
    fetchImpl: async () => jsonResponse({ message: "nope" }, 404),
  });

  const envelope = await client.get("/wallet");

  assert.equal(envelope.ok, false);
  assert.equal(envelope.status, "http_error");
  assert.equal(envelope.error.code, "http_404");
});

test("pair methods call the bridge endpoints with the expected bodies", async () => {
  const rec = recorder({ ok: true, status: "ok", data: {} });
  const client = createApiClient({ fetchImpl: rec.fetchImpl, basePath: "/b" });

  await client.pair.start({ device_name: "Desktop", new_account: true });
  await client.pair.poll();
  await client.pair.approve({ user_code: "BCDF-GHJK" });
  await client.pair.devices();
  await client.pair.revoke("dev_1");
  await client.pair.logout();

  const urls = rec.calls.map((call) => call.url);
  assert.deepEqual(urls, [
    "/b/pair/start",
    "/b/pair/poll",
    "/b/pair/approve",
    "/b/pair/devices",
    "/b/pair/devices/dev_1/revoke",
    "/b/pair/logout",
  ]);
  assert.deepEqual(JSON.parse(rec.calls[0].init.body), {
    device_name: "Desktop",
    new_account: true,
  });
  assert.deepEqual(JSON.parse(rec.calls[2].init.body), {
    user_code: "BCDF-GHJK",
  });
  assert.equal(rec.calls[3].init.method, "GET");
});

test("pair.start accepts a device name string and camelCase alias", async () => {
  const rec = recorder({ ok: true, status: "ok", data: {} });
  const client = createApiClient({ fetchImpl: rec.fetchImpl });

  await client.pair.start("Laptop", { newAccount: true });

  assert.deepEqual(JSON.parse(rec.calls[0].init.body), {
    device_name: "Laptop",
    new_account: true,
  });
});

test("pair.approve accepts a bare user code", async () => {
  const rec = recorder({ ok: true, status: "ok", data: {} });
  const client = createApiClient({ fetchImpl: rec.fetchImpl });

  await client.pair.approve("bcdf-ghjk");

  assert.deepEqual(JSON.parse(rec.calls[0].init.body), {
    user_code: "bcdf-ghjk",
  });
});

test("uiStateFromEnvelope maps bridge failures onto existing UI states", () => {
  assert.equal(uiStateFromEnvelope({ ok: true, status: "ok" }), "ready");
  assert.equal(uiStateFromEnvelope(null), "ready");
  assert.equal(
    uiStateFromEnvelope({ ok: false, status: "auth_missing" }),
    "auth_missing"
  );
  assert.equal(
    uiStateFromEnvelope({ ok: false, status: "unauthorized" }),
    "auth_missing"
  );
  assert.equal(
    uiStateFromEnvelope({ ok: false, status: "offline" }),
    "service_unavailable"
  );
  assert.equal(
    uiStateFromEnvelope({ ok: false, status: "not_allowed" }),
    "service_unavailable"
  );
  assert.equal(
    uiStateFromEnvelope({ ok: false, status: "unavailable" }),
    "service_unavailable"
  );
});

test("createApiClient never attaches a host session header", async () => {
  const rec = recorder({ ok: true });
  const client = createApiClient({ fetchImpl: rec.fetchImpl });
  await client.health();
  assert.equal(rec.calls[0].init.headers["X-Hermes-Session-Token"], undefined);
  assert.equal(rec.calls[0].init.credentials, "same-origin");
});

test("Desktop transport routes every call through ctx.rest with namespace paths", async () => {
  const calls = [];
  const rest = async (path, opts) => {
    calls.push({ path, opts });
    return { ok: true, status: "ok", data: { path } };
  };
  const client = createApiClient({ rest });
  const got = await client.get("/wallet");
  assert.equal(got.ok, true);
  await client.post("/pets", { name: "x" }, { idempotencyKey: "k1" });
  await client.status();
  await client.pair.poll();
  assert.equal(calls[0].path, "/proxy/v1/wallet");
  assert.equal(calls[0].opts.method, "GET");
  assert.equal(calls[1].path, "/proxy/v1/pets?idempotency_key=k1");
  assert.deepEqual(calls[1].opts.body, { name: "x" });
  assert.equal(calls[2].path, "/status");
  assert.equal(calls[3].path, "/pair/poll");
});

test("ctx.rest failures resolve to an error envelope", async () => {
  const client = createApiClient({ rest: async () => { throw new Error("500"); } });
  const env = await client.get("/wallet");
  assert.equal(env.ok, false);
  assert.equal(env.status, "http_error");
});

test("dashboard transport uses SDK.authedFetch with full plugin URLs", async () => {
  const rec = recorder({ ok: true, status: "ok", data: 1 });
  const client = createApiClient({ authedFetch: rec.fetchImpl });
  await client.post("/pets", {}, { idempotencyKey: "k2" });
  assert.equal(rec.calls[0].url, "/api/plugins/hermagotchi/proxy/v1/pets");
  assert.equal(rec.calls[0].init.headers["Idempotency-Key"], "k2");
  assert.equal(rec.calls[0].init.headers["X-Hermes-Session-Token"], undefined);
});
