import { jsx } from "react/jsx-runtime";
import { HermagotchiPane } from "./pane.js";
import { createApiClient } from "./api.js";

export const PANE_ID = "hermagotchi";
export const PANE_TITLE = "Hermagotchi";

export function createPaneContribution() {
  return {
    id: PANE_ID,
    title: PANE_TITLE,
    area: "panes",
    render: function renderPane(props) {
      const p = Object.assign({}, props || {});
      if (!p.api && p.live !== false) {
        p.api = createApiClient({ basePath: p.apiBasePath });
      }
      return jsx(HermagotchiPane, p);
    },
  };
}

export function registerHermagotchiPane(ctx) {
  if (!ctx || typeof ctx.register !== "function") {
    return false;
  }
  ctx.register(createPaneContribution());
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
