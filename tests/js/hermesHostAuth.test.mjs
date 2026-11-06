import test from "node:test";
import assert from "node:assert/strict";
import {
  HERMES_SESSION_HEADER,
  WEBAPP_SESSION_KEY_PREFIX,
  hermesHostAuthHeaders,
  readHermesWebappSessionToken,
} from "../../desktop/src/ui/logic/hermesHostAuth.js";

function fakeStorage(entries) {
  const map = new Map(Object.entries(entries));
  return {
    get length() {
      return map.size;
    },
    key(i) {
      return [...map.keys()][i] ?? null;
    },
    getItem(k) {
      return map.has(k) ? map.get(k) : null;
    },
  };
}

test("readHermesWebappSessionToken returns empty when storage missing", () => {
  assert.equal(readHermesWebappSessionToken({ sessionStorage: null }), "");
  assert.deepEqual(hermesHostAuthHeaders({ sessionStorage: null }), {});
});

test("readHermesWebappSessionToken finds the webapp launch grant", () => {
  const store = fakeStorage({
    unrelated: "nope",
    [WEBAPP_SESSION_KEY_PREFIX + '["http://127.0.0.1:9120",""]']: "tok_abc",
  });
  assert.equal(readHermesWebappSessionToken({ sessionStorage: store }), "tok_abc");
  assert.deepEqual(hermesHostAuthHeaders({ sessionStorage: store }), {
    [HERMES_SESSION_HEADER]: "tok_abc",
  });
});
