import test from "node:test";
import assert from "node:assert/strict";

import {
  connectionRows,
  deriveConnectionStatus,
  resolveConnectionUiState,
} from "../../desktop/src/ui/logic/connection.js";

const STATUS_OK = {
  ok: true,
  status: "ok",
  health: { status: "ok", service: "hermagotchi" },
  me: { account: { id: "acct_1" } },
  policy: {
    network_enabled: true,
    chat_enabled: false,
    autonomy_enabled: true,
  },
  asset_base_path: "assets",
};

const PAIRED = {
  ok: true,
  status: "ok",
  data: { paired: true, account_id: "acct_1" },
};

test("status and pairing envelopes resolve to live connection labels", () => {
  const connection = deriveConnectionStatus({
    statusEnvelope: STATUS_OK,
    pairEnvelope: PAIRED,
  });

  assert.equal(connection.backendEnabled, true);
  assert.equal(connection.networkEnabled, true);
  assert.equal(connection.authenticated, true);
  assert.equal(connection.serviceReachable, true);
  assert.equal(resolveConnectionUiState(connection), "ready");

  const rows = connectionRows(connection);
  assert.deepEqual(
    rows.map((row) => row.key),
    ["backend", "network", "identity", "chat", "autonomy", "service"]
  );
  const values = Object.fromEntries(rows.map((row) => [row.key, row.value]));
  assert.equal(values.backend, "Enabled");
  assert.equal(values.network, "On");
  assert.equal(values.identity, "Paired");
  assert.equal(values.chat, "Off");
  assert.equal(values.autonomy, "On");
  assert.equal(values.service, "Reachable");
});

test("a wrapped status data envelope is accepted", () => {
  const connection = deriveConnectionStatus({
    statusEnvelope: { ok: true, status: "ok", data: STATUS_OK },
    pairEnvelope: PAIRED,
  });

  assert.equal(connection.backendEnabled, true);
  assert.equal(connection.serviceReachable, true);
  assert.equal(connection.authenticated, true);
});

test("an unpaired poll keeps identity honest and drives auth_missing", () => {
  const connection = deriveConnectionStatus({
    statusEnvelope: STATUS_OK,
    pairEnvelope: {
      ok: true,
      status: "ok",
      data: { paired: false, status: "idle" },
    },
  });

  assert.equal(connection.authenticated, false);
  assert.equal(resolveConnectionUiState(connection), "auth_missing");
  const identity = connectionRows(connection).find((row) => row.key === "identity");
  assert.equal(identity.value, "Not paired");
});

test("network policy off wins over a reachable backend", () => {
  const connection = deriveConnectionStatus({
    statusEnvelope: {
      ok: true,
      status: "ok",
      health: { status: "ok" },
      policy: { network_enabled: false },
    },
    pairEnvelope: PAIRED,
  });

  assert.equal(connection.backendEnabled, true);
  assert.equal(connection.networkEnabled, false);
  assert.equal(resolveConnectionUiState(connection), "network_off");
  const network = connectionRows(connection).find((row) => row.key === "network");
  assert.equal(network.value, "Off");
});

test("health alone can prove the backend and service are live", () => {
  const connection = deriveConnectionStatus({
    healthEnvelope: {
      ok: true,
      status: "ok",
      health: { status: "ok" },
      policy: { network_enabled: true },
    },
    pairEnvelope: PAIRED,
  });

  assert.equal(connection.backendEnabled, true);
  assert.equal(connection.serviceReachable, true);
  assert.equal(resolveConnectionUiState(connection), "ready");
});

test("offline envelopes report a disabled backend instead of stale paired state", () => {
  const connection = deriveConnectionStatus({
    statusEnvelope: {
      ok: false,
      status: "offline",
      error: { code: "network_error", message: "No bridge." },
    },
    pairEnvelope: { ok: false, status: "offline" },
  });

  assert.equal(connection.backendEnabled, false);
  assert.equal(connection.serviceReachable, false);
  assert.equal(resolveConnectionUiState(connection), "backend_disabled");
  const values = Object.fromEntries(
    connectionRows(connection).map((row) => [row.key, row.value])
  );
  assert.equal(values.backend, "Disabled");
  assert.equal(values.service, "Unavailable");
});

test("a successful pair poll proves the bridge is live without /status", () => {
  const connection = deriveConnectionStatus({ pairEnvelope: PAIRED });

  assert.equal(connection.backendEnabled, true);
  assert.equal(connection.serviceReachable, true);
  assert.equal(connection.authenticated, true);
  assert.equal(resolveConnectionUiState(connection), "ready");
});

test("missing status is unknown rather than falsely disabled", () => {
  const connection = deriveConnectionStatus({});

  assert.equal(connection.backendEnabled, null);
  assert.equal(connection.networkEnabled, null);
  assert.equal(connection.serviceReachable, null);
  assert.equal(connection.authenticated, null);
  assert.equal(resolveConnectionUiState(connection), "ready");
  const values = Object.fromEntries(
    connectionRows(connection).map((row) => [row.key, row.value])
  );
  assert.equal(values.backend, "Unknown");
  assert.equal(values.identity, "Not paired");
});
