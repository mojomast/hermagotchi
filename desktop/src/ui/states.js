import { jsx, jsxs } from "react/jsx-runtime";

export const UI_STATES = Object.freeze({
  READY: "ready",
  BACKEND_DISABLED: "backend_disabled",
  NETWORK_OFF: "network_off",
  AUTH_MISSING: "auth_missing",
  SERVICE_UNAVAILABLE: "service_unavailable",
});

export const UI_STATE_COPY = Object.freeze({
  ready: {
    label: "Ready",
    detail: "Local sources loaded. Live data appears when the backend and network are enabled.",
    action: "",
  },
  backend_disabled: {
    label: "Backend disabled",
    detail: "The Hermagotchi Python backend is off. Enable it in Hermes before loading game data.",
    action: "Open Settings to review the backend toggle.",
  },
  network_off: {
    label: "Network off",
    detail: "Multiplayer is disabled by your owner policy. Local habitat features remain available.",
    action: "Review Settings to opt in to multiplayer.",
  },
  auth_missing: {
    label: "Auth missing",
    detail: "This device is not paired. Pair it before using multiplayer, shop or social actions.",
    action: "Pair this device from Settings.",
  },
  service_unavailable: {
    label: "Service unavailable",
    detail: "The game service cannot be reached right now. Local state is unchanged.",
    action: "Retry later or check the service status in Settings.",
  },
});

export function resolveUiState(options = {}) {
  const backendEnabled = options.backendEnabled !== false;
  const networkEnabled = options.networkEnabled !== false;
  const authenticated = options.authenticated !== false;
  const serviceReachable = options.serviceReachable !== false;

  if (!backendEnabled) {
    return UI_STATES.BACKEND_DISABLED;
  }
  if (!networkEnabled) {
    return UI_STATES.NETWORK_OFF;
  }
  if (!authenticated) {
    return UI_STATES.AUTH_MISSING;
  }
  if (!serviceReachable) {
    return UI_STATES.SERVICE_UNAVAILABLE;
  }
  return UI_STATES.READY;
}

export function StateNotice(props = {}) {
  const state = props.state || UI_STATES.READY;
  const copy = UI_STATE_COPY[state] || UI_STATE_COPY.ready;

  if (state === UI_STATES.READY) {
    return jsx("p", {
      className: "hg-state hg-state--ready",
      "data-ui-state": state,
      children: copy.detail,
    });
  }

  return jsxs("section", {
    className: "hg-state hg-state--" + state,
    role: "status",
    "data-ui-state": state,
    children: [
      jsx("strong", { children: copy.label }),
      jsx("p", { children: copy.detail }),
      copy.action
        ? jsx("span", { className: "hg-state__hint", children: copy.action })
        : null,
    ],
  });
}
