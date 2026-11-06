import test from "node:test";
import assert from "node:assert/strict";

import {
  PAIRING_STATES,
  buildPairingViewModel,
  countdownLabel,
  deviceRowsFromEnvelope,
  formatCountdown,
  formatUserCode,
  isValidUserCode,
  normalizeUserCode,
  pairingStateFromPoll,
  pairingStateFromStart,
  parseExpiry,
  secondsRemaining,
} from "../../desktop/src/ui/logic/session.js";

const START = {
  ok: true,
  status: "ok",
  data: {
    user_code: "BCDF-GHJK",
    expires_at: "2026-11-06T00:10:00Z",
    paired: false,
    interval_s: 5,
  },
};

test("user codes are normalised and displayed in XXXX-XXXX form", () => {
  assert.equal(normalizeUserCode(" bcdf - ghjk "), "BCDFGHJK");
  assert.equal(normalizeUserCode(null), "");
  assert.equal(formatUserCode("BCDFGHJK"), "BCDF-GHJK");
  assert.equal(isValidUserCode("bcdf-ghjk"), true);
  assert.equal(isValidUserCode("ABCDEFGH"), false);
  assert.equal(isValidUserCode("short"), false);
});

test("expiry parsing supports ISO strings and epoch values", () => {
  assert.equal(parseExpiry("2026-11-06T00:10:00Z"), Date.parse("2026-11-06T00:10:00Z"));
  assert.equal(parseExpiry(1762387800), 1762387800000);
  assert.equal(parseExpiry(1762387800000), 1762387800000);
  assert.equal(parseExpiry(""), 0);
  assert.equal(parseExpiry("not a date"), 0);
  assert.equal(secondsRemaining("2026-11-06T00:10:00Z", Date.parse("2026-11-06T00:09:30Z")), 30);
  assert.equal(secondsRemaining("2026-11-06T00:10:00Z", Date.parse("2026-11-06T00:11:00Z")), 0);
});

test("countdown formatting clamps and pads seconds", () => {
  assert.equal(formatCountdown(300), "5:00");
  assert.equal(formatCountdown(65), "1:05");
  assert.equal(formatCountdown(4), "0:04");
  assert.equal(formatCountdown(0), "Expired");
  assert.equal(formatCountdown(-3), "Expired");
});

test("pairing start produces a pending view with a live countdown", () => {
  const now = Date.parse("2026-11-06T00:05:00Z");
  const state = pairingStateFromStart(START, now);

  assert.equal(state.status, PAIRING_STATES.PENDING);
  assert.equal(state.paired, false);
  assert.equal(state.userCode, "BCDFGHJK");
  assert.equal(state.userCodeDisplay, "BCDF-GHJK");
  assert.equal(state.expiresAt, "2026-11-06T00:10:00Z");
  assert.equal(state.expiresAtMs, Date.parse("2026-11-06T00:10:00Z"));
  assert.equal(state.intervalS, 5);
  assert.equal(state.secondsRemaining, 300);
  assert.equal(state.countdown, "5:00");
});

test("a start that is already past its expiry becomes expired", () => {
  const now = Date.parse("2026-11-06T00:20:00Z");
  const state = pairingStateFromStart(START, now);

  assert.equal(state.status, PAIRING_STATES.EXPIRED);
  assert.equal(state.countdown, "Expired");
});

test("start failures become an error state", () => {
  const state = pairingStateFromStart({
    ok: false,
    status: "offline",
    error: { code: "network_error", message: "No bridge.", retry_after_s: 2 },
  });

  assert.equal(state.status, PAIRING_STATES.ERROR);
  assert.equal(state.error.code, "network_error");
  assert.equal(state.error.retryAfterS, 2);
});

test("poll keeps a pending pairing pending", () => {
  const now = Date.parse("2026-11-06T00:05:00Z");
  const prior = pairingStateFromStart(START, now);
  const state = pairingStateFromPoll(
    {
      ok: true,
      status: "ok",
      data: { paired: false, status: "pending", retry_after_s: 5 },
    },
    prior,
    now
  );

  assert.equal(state.status, PAIRING_STATES.PENDING);
  assert.equal(state.userCodeDisplay, "BCDF-GHJK");
  assert.equal(state.retryAfterS, 5);
});

test("poll reports paired with only an account id", () => {
  const prior = pairingStateFromStart(START, Date.parse("2026-11-06T00:05:00Z"));
  const state = pairingStateFromPoll(
    {
      ok: true,
      status: "ok",
      data: { paired: true, account_id: "acct_1" },
    },
    prior
  );

  assert.equal(state.status, PAIRING_STATES.PAIRED);
  assert.equal(state.paired, true);
  assert.equal(state.accountId, "acct_1");
  assert.equal(state.secondsRemaining, 0);
});

test("poll reports expiry from an expired_token error", () => {
  const prior = pairingStateFromStart(START, Date.parse("2026-11-06T00:05:00Z"));
  const state = pairingStateFromPoll(
    {
      ok: false,
      status: "expired",
      error: { code: "expired_token", message: "Expired.", retry_after_s: 0 },
    },
    prior
  );

  assert.equal(state.status, PAIRING_STATES.EXPIRED);
  assert.equal(state.countdown, "Expired");
  assert.equal(state.error.code, "expired_token");
});

test("device rows normalise server fields and revoke eligibility", () => {
  const rows = deviceRowsFromEnvelope({
    ok: true,
    status: "ok",
    data: {
      devices: [
        {
          device_id: "dev_1",
          device_name: "Desktop",
          created_at: "2026-11-06T00:00:00Z",
          last_seen_at: "2026-11-06T00:05:00Z",
          current: true,
          revoked: false,
        },
        {
          device_id: "dev_2",
          device_name: "Laptop",
          current: false,
          revoked: true,
        },
      ],
    },
  });

  assert.equal(rows.length, 2);
  assert.equal(rows[0].id, "dev_1");
  assert.equal(rows[0].deviceId, "dev_1");
  assert.equal(rows[0].name, "Desktop");
  assert.equal(rows[0].current, true);
  assert.equal(rows[0].canRevoke, true);
  assert.equal(rows[0].revokeLabel, "Revoke this device");
  assert.equal(rows[1].revoked, true);
  assert.equal(rows[1].canRevoke, false);
  assert.deepEqual(deviceRowsFromEnvelope({ ok: false, status: "offline" }), []);
});

test("view model combines pending state, countdown and device rows", () => {
  const now = Date.parse("2026-11-06T00:06:00Z");
  const view = buildPairingViewModel(
    {
      start: START,
      devices: {
        ok: true,
        status: "ok",
        data: { devices: [{ device_id: "dev_1", device_name: "Desktop" }] },
      },
    },
    now
  );

  assert.equal(view.status, PAIRING_STATES.PENDING);
  assert.equal(view.hasPending, true);
  assert.equal(view.isPaired, false);
  assert.equal(view.deviceCount, 1);
  assert.equal(view.hasDevices, true);
  assert.equal(view.countdownLabel, "4:00");
  assert.equal(countdownLabel(view, now), "4:00");
});

test("view model reports paired devices after a successful poll", () => {
  const view = buildPairingViewModel(
    {
      start: START,
      poll: { ok: true, status: "ok", data: { paired: true, account_id: "acct_9" } },
    },
    Date.parse("2026-11-06T00:05:00Z")
  );

  assert.equal(view.status, PAIRING_STATES.PAIRED);
  assert.equal(view.isPaired, true);
  assert.equal(view.accountId, "acct_9");
  assert.equal(view.canApprove, true);
  assert.equal(view.countdownLabel, "Paired");
});
