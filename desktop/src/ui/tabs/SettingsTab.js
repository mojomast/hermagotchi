import { useCallback, useEffect, useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
import { StateNotice, UI_STATES } from "../states.js";
import { NpcHostBanner } from "../components/NpcHostBanner.js";
import {
  connectionRows,
  deriveConnectionStatus,
  resolveConnectionUiState,
} from "../logic/connection.js";
import {
  PAIRING_STATES,
  deviceRowsFromEnvelope,
  emptyPairingState,
  formatCountdown,
  pairingStateFromPoll,
  pairingStateFromStart,
  secondsRemaining,
} from "../logic/session.js";

export const SETTINGS_PLACEHOLDER = Object.freeze([
  { key: "backend", label: "Python backend", value: "Disabled" },
  { key: "network", label: "Multiplayer", value: "Off" },
  { key: "identity", label: "Identity", value: "Not paired" },
  { key: "chat", label: "Chat", value: "Off" },
  { key: "autonomy", label: "Agent autonomy", value: "Off" },
  { key: "service", label: "Multiplayer URL", value: "Not configured" },
]);

function SettingRow(props) {
  const setting = props.setting;
  return jsxs("div", {
    className: "hg-setting",
    "data-setting": setting.key,
    children: [
      jsx("span", { className: "hg-label", children: setting.label }),
      jsx("strong", { children: setting.value }),
    ],
  });
}

function noticeText(envelope, fallback) {
  if (envelope && envelope.error && envelope.error.message) {
    return envelope.error.message;
  }
  return fallback;
}

function callMaybe(fn) {
  try {
    const result = fn();
    return result && typeof result.catch === "function"
      ? result.catch(function () {
          return null;
        })
      : Promise.resolve(result);
  } catch (_error) {
    return Promise.resolve(null);
  }
}

function statusEnvelopeFor(api) {
  if (api && typeof api.status === "function") {
    return callMaybe(function () {
      return api.status();
    });
  }
  if (api && typeof api.get === "function") {
    return callMaybe(function () {
      return api.get("/status");
    });
  }
  return Promise.resolve(null);
}

function healthEnvelopeFor(api) {
  if (api && typeof api.health === "function") {
    return callMaybe(function () {
      return api.health();
    });
  }
  if (api && typeof api.get === "function") {
    return callMaybe(function () {
      return api.get("/health");
    });
  }
  return Promise.resolve(null);
}

function pairEnvelopeFor(api) {
  if (api && api.pair && typeof api.pair.poll === "function") {
    return callMaybe(function () {
      return api.pair.poll();
    });
  }
  return Promise.resolve(null);
}

function formatExpiry(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString();
}

function DeviceRow(props) {
  const row = props.row;
  const busy = props.busy;
  return jsxs("tr", {
    "data-device-id": row.id,
    children: [
      jsxs("td", {
        children: [
          jsx("strong", { children: row.name }),
          row.current
            ? jsx("span", {
                className: "hg-badge hg-badge--current",
                children: "This device",
              })
            : null,
          row.revoked
            ? jsx("span", {
                className: "hg-badge hg-badge--revoked",
                children: "Revoked",
              })
            : null,
        ],
      }),
      jsx("td", { className: "hg-muted", children: formatExpiry(row.lastSeenAt) }),
      jsx("td", {
        children: jsx("button", {
          type: "button",
          className: "hg-btn hg-btn--danger",
          disabled: Boolean(busy) || !row.canRevoke,
          onClick: function () {
            if (typeof props.onRevoke === "function") {
              props.onRevoke(row);
            }
          },
          children: row.canRevoke ? "Revoke" : "Revoked",
        }),
      }),
    ],
  });
}

function SettingsStub(props) {
  return jsxs("section", {
    className: "hg-settings",
    "data-tab": "settings",
    children: [
      props.uiState && props.uiState !== UI_STATES.READY
        ? jsx(StateNotice, { state: props.uiState })
        : null,
      jsx(NpcHostBanner, { surface: "settings" }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Settings" }),
          jsx("p", {
            className: "hg-muted",
            children:
              "Read-only placeholders. A later integration binds real owner toggles and persists changes through the gateway.",
          }),
          jsx("div", {
            className: "hg-settings__list",
            children: SETTINGS_PLACEHOLDER.map((setting) =>
              jsx(SettingRow, { setting }, setting.key)
            ),
          }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Diagnostics" }),
          jsx("p", {
            className: "hg-muted",
            children: "Version and connection diagnostics appear after backend wiring.",
          }),
        ],
      }),
    ],
  });
}

export function SettingsTab(props = {}) {
  const api = props.api;
  const uiState = props.uiState || props.state || UI_STATES.READY;
  const [view, setView] = useState(emptyPairingState());
  const [devices, setDevices] = useState([]);
  const [deviceName, setDeviceName] = useState("Desktop");
  const [userCode, setUserCode] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [now, setNow] = useState(Date.now());
  const [connection, setConnection] = useState(null);

  const loadDevices = useCallback(
    async function loadDevices() {
      if (!api) {
        return;
      }
      const envelope = await api.pair.devices();
      setDevices(deviceRowsFromEnvelope(envelope));
      if (!envelope.ok && envelope.status !== "auth_missing") {
        setNotice(noticeText(envelope, "Could not load paired devices."));
      }
    },
    [api]
  );

  useEffect(
    function tickClock() {
      if (!api) {
        return undefined;
      }
      const timer = setInterval(function () {
        setNow(Date.now());
      }, 1000);
      return function () {
        clearInterval(timer);
      };
    },
    [api]
  );

  useEffect(
    function pollConnection() {
      if (!api) {
        return undefined;
      }
      let cancelled = false;
      async function run() {
        const [statusEnvelope, healthEnvelope, pairEnvelope] = await Promise.all([
          statusEnvelopeFor(api),
          healthEnvelopeFor(api),
          pairEnvelopeFor(api),
        ]);
        if (cancelled) {
          return;
        }
        setConnection(
          deriveConnectionStatus({
            statusEnvelope: statusEnvelope,
            healthEnvelope: healthEnvelope,
            pairEnvelope: pairEnvelope,
          })
        );
      }
      run();
      const timer = setInterval(run, 10000);
      return function () {
        cancelled = true;
        clearInterval(timer);
      };
    },
    [api]
  );

  useEffect(
    function initialise() {
      if (!api) {
        return undefined;
      }
      let cancelled = false;
      async function run() {
        const envelope = await api.pair.poll();
        if (cancelled) {
          return;
        }
        const next = pairingStateFromPoll(envelope, emptyPairingState());
        setView(next);
        if (next.paired) {
          loadDevices();
        }
      }
      run();
      return function () {
        cancelled = true;
      };
    },
    [api, loadDevices]
  );

  useEffect(
    function pollPendingPairing() {
      if (!api || view.status !== PAIRING_STATES.PENDING) {
        return undefined;
      }
      let cancelled = false;
      const delay = Math.max(1000, (Number(view.intervalS) || 5) * 1000);
      const timer = setInterval(async function () {
        const envelope = await api.pair.poll();
        if (cancelled) {
          return;
        }
        setView(function (previous) {
          return pairingStateFromPoll(envelope, previous);
        });
        if (envelope.ok && envelope.data && envelope.data.paired === true) {
          setNotice("This device is paired.");
          loadDevices();
        }
      }, delay);
      return function () {
        cancelled = true;
        clearInterval(timer);
      };
    },
    [api, view.status, view.intervalS, loadDevices]
  );

  if (!api) {
    return jsx(SettingsStub, { uiState: uiState });
  }

  const liveRows = connection ? connectionRows(connection) : SETTINGS_PLACEHOLDER;
  const liveState = connection ? resolveConnectionUiState(connection) : uiState;

  async function startPairing() {
    setBusy("start");
    setNotice("");
    const envelope = await api.pair.start({
      device_name: deviceName || "Desktop",
      new_account: !isPaired,
    });
    const next = pairingStateFromStart(envelope);
    setView(next);
    if (!envelope.ok) {
      setNotice(noticeText(envelope, "Pairing could not start."));
    }
    setBusy("");
  }

  async function approveDevice() {
    setBusy("approve");
    setNotice("");
    const envelope = await api.pair.approve({ user_code: userCode });
    if (envelope.ok) {
      setUserCode("");
      setNotice("Device approved.");
      loadDevices();
    } else {
      setNotice(noticeText(envelope, "Could not approve that code."));
    }
    setBusy("");
  }

  async function revokeDevice(row) {
    setBusy("revoke:" + row.id);
    setNotice("");
    const envelope = await api.pair.revoke(row.id);
    if (envelope.ok) {
      setNotice(row.current ? "This device was revoked." : "Device revoked.");
      if (row.current) {
        setView(emptyPairingState());
        setDevices([]);
      } else {
        loadDevices();
      }
    } else {
      setNotice(noticeText(envelope, "Could not revoke that device."));
    }
    setBusy("");
  }

  async function logout() {
    setBusy("logout");
    setNotice("");
    const envelope = await api.pair.logout();
    if (envelope.ok || envelope.status === "auth_missing") {
      setView(emptyPairingState());
      setDevices([]);
      setNotice("Signed out on this device.");
    } else {
      setNotice(noticeText(envelope, "Could not sign out."));
    }
    setBusy("");
  }

  const remaining = view.expiresAtMs
    ? secondsRemaining(view.expiresAtMs, now)
    : 0;
  const isPending = view.status === PAIRING_STATES.PENDING;
  const isPaired = view.status === PAIRING_STATES.PAIRED;
  const expiryText = formatExpiry(view.expiresAt);

  return jsxs("section", {
    className: "hg-settings",
    "data-tab": "settings",
    children: [
      jsx(StateNotice, { state: liveState }),
      jsx(NpcHostBanner, { surface: "settings" }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Settings" }),
          jsx("p", {
            className: "hg-muted",
            children:
              "Pairing, device access and session controls are handled by the local Hermagotchi bridge.",
          }),
          jsx("div", {
            className: "hg-settings__list",
            "data-live-status": connection ? "true" : "false",
            children: liveRows.map((setting) =>
              jsx(SettingRow, { setting }, setting.key)
            ),
          }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        "data-section": "pairing",
        children: [
          jsx("h3", { children: "Pairing" }),
          isPending
            ? jsxs("div", {
                className: "hg-pairing hg-pairing--pending",
                children: [
                  jsx("p", { className: "hg-muted", children: "Enter this code on a paired device to approve this device." }),
                  jsx("p", {
                    className: "hg-pairing__code",
                    "data-pairing-code": view.userCodeDisplay,
                    children: view.userCodeDisplay,
                  }),
                  jsxs("p", {
                    className: "hg-muted",
                    children: [
                      "Expires ",
                      expiryText || "soon",
                      " (",
                      formatCountdown(remaining),
                      ")",
                    ],
                  }),
                  jsx("button", {
                    type: "button",
                    className: "hg-btn",
                    onClick: startPairing,
                    disabled: Boolean(busy),
                    children: "Restart pairing",
                  }),
                ],
              })
            : jsxs("div", {
                className: "hg-pairing",
                children: [
                  isPaired
                    ? jsx("p", {
                        className: "hg-muted",
                        children: "This device is paired. Enter a code from another device to approve it.",
                      })
                    : jsx("p", {
                        className: "hg-muted",
                        children: "This device is not paired yet. Start pairing to get a code.",
                      }),
                  jsxs("div", {
                    className: "hg-row",
                    children: [
                      jsx("label", {
                        className: "hg-field hg-col",
                        children: [
                          jsx("span", { children: "Device name" }),
                          jsx("input", {
                            className: "hg-input",
                            type: "text",
                            maxLength: "64",
                            value: deviceName,
                            onChange: function (event) {
                              setDeviceName(event.target.value);
                            },
                          }),
                        ],
                      }),
                      jsx("button", {
                        type: "button",
                        className: "hg-btn hg-btn--primary",
                        onClick: startPairing,
                        disabled: Boolean(busy),
                        children: isPaired ? "Pair another device" : "Start pairing",
                      }),
                    ],
                  }),
                ],
              }),
          jsxs("div", {
            className: "hg-pairing__approve",
            children: [
              jsx("label", {
                className: "hg-field",
                children: [
                  jsx("span", { children: "Approve another device" }),
                  jsx("input", {
                    className: "hg-input",
                    type: "text",
                    maxLength: "9",
                    placeholder: "BCDF-GHJK",
                    value: userCode,
                    onChange: function (event) {
                      setUserCode(event.target.value);
                    },
                  }),
                ],
              }),
              jsx("button", {
                type: "button",
                className: "hg-btn",
                onClick: approveDevice,
                disabled: Boolean(busy) || !userCode,
                children: "Approve device",
              }),
            ],
          }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        "data-section": "devices",
        children: [
          jsxs("header", {
            className: "hg-card__header",
            children: [
              jsx("h3", { children: "Paired devices" }),
              jsx("button", {
                type: "button",
                className: "hg-btn",
                onClick: loadDevices,
                disabled: Boolean(busy),
                children: "Refresh",
              }),
            ],
          }),
          notice
            ? jsx("p", { className: "hg-error", role: "status", children: notice })
            : null,
          jsxs("table", {
            className: "hg-table",
            children: [
              jsx("thead", {
                children: jsxs("tr", {
                  children: [
                    jsx("th", { children: "Device" }),
                    jsx("th", { children: "Last seen" }),
                    jsx("th", { children: "Action" }),
                  ],
                }),
              }),
              jsx("tbody", {
                children:
                  devices.length > 0
                    ? devices.map((row) =>
                        jsx(
                          DeviceRow,
                          { row: row, busy: busy, onRevoke: revokeDevice },
                          row.id
                        )
                      )
                    : jsx("tr", {
                        children: jsx("td", {
                          colSpan: "3",
                          className: "hg-muted",
                          children: "No paired devices loaded.",
                        }),
                      }),
              }),
            ],
          }),
          jsxs("div", {
            className: "hg-actions",
            children: [
              jsx("button", {
                type: "button",
                className: "hg-btn hg-btn--danger",
                onClick: logout,
                disabled: Boolean(busy) || !isPaired,
                children: "Sign out this device",
              }),
            ],
          }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Diagnostics" }),
          jsx("p", {
            className: "hg-muted",
            children: "Version and connection diagnostics appear after backend wiring.",
          }),
        ],
      }),
    ],
  });
}
