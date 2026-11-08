import { jsx } from "react/jsx-runtime";
import { HermagotchiPane } from "./pane.js";
import { createApiClient } from "./api.js";
import { setHostTransport } from "./logic/hostTransport.js";

export const PANE_ID = "hermagotchi";
export const PANE_TITLE = "Hermagotchi";

export function createPaneContribution(options) {
  const transport = options || {};
  return {
    id: PANE_ID,
    title: PANE_TITLE,
    area: "panes",
    render: function renderPane(props) {
      const p = Object.assign({}, props || {});
      if (!p.api && p.live !== false) {
        p.api = createApiClient({
          basePath: p.apiBasePath,
          rest: transport.rest,
          authedFetch: transport.authedFetch,
        });
      }
      return jsx(HermagotchiPane, p);
    },
  };
}

/**
 * Desktop entry. Every bridge call (JSON and art) goes through `ctx.rest`
 * (Desktop plugin SDK, Hermes >= 0.23.0); the pane never touches a host token.
 */
export function registerHermagotchiPane(ctx) {
  if (!ctx || typeof ctx.register !== "function") {
    return false;
  }
  const rest =
    typeof ctx.rest === "function"
      ? function hermagotchiRest(path, opts) {
          return ctx.rest(path, opts);
        }
      : undefined;
  setHostTransport(rest ? { rest: rest } : null);
  ctx.register(createPaneContribution({ rest: rest }));
  return true;
}

export function createDesktopPlugin() {
  return {
    id: PANE_ID,
    name: PANE_TITLE,
    defaultEnabled: false,
    register: registerHermagotchiPane,
  };
}
