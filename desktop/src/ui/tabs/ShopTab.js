import { jsx, jsxs } from "react/jsx-runtime";
import { StateNotice, UI_STATES } from "../states.js";

export const SHOP_PLACEHOLDER_ITEMS = Object.freeze([
  { id: "placeholder.crown", name: "Binary Crown", slot: "head", priceBits: 2000 },
  { id: "placeholder.scarf", name: "Patch Scarf", slot: "front", priceBits: 350 },
  { id: "placeholder.aura", name: "Soft Static Aura", slot: "aura", priceBits: 700 },
]);

function ItemRow(props) {
  const item = props.item;
  return jsxs("tr", {
    children: [
      jsx("td", { children: item.name }),
      jsx("td", { children: item.slot }),
      jsx("td", { children: item.priceBits + " Bits" }),
      jsx("td", {
        children: jsx("button", {
          type: "button",
          disabled: true,
          children: "Buy (disabled)",
        }),
      }),
    ],
  });
}

export function ShopTab(props = {}) {
  const uiState = props.uiState || UI_STATES.READY;

  return jsxs("section", {
    className: "hg-shop",
    "data-tab": "shop",
    children: [
      jsx(StateNotice, { state: uiState }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Wallet" }),
          jsxs("p", {
            children: [
              jsx("span", { className: "hg-label", children: "Bits balance" }),
              jsx("strong", { "data-placeholder": "bits-balance", children: "Not loaded" }),
            ],
          }),
          jsx("p", {
            className: "hg-muted",
            children:
              "Preview only. No Bits are spent in this stub; purchases stay disabled until the server confirms balance and ownership.",
          }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Catalog preview" }),
          jsxs("table", {
            className: "hg-table",
            children: [
              jsx("thead", {
                children: jsxs("tr", {
                  children: [
                    jsx("th", { children: "Item" }),
                    jsx("th", { children: "Slot" }),
                    jsx("th", { children: "Price" }),
                    jsx("th", { children: "Action" }),
                  ],
                }),
              }),
              jsx("tbody", {
                children: SHOP_PLACEHOLDER_ITEMS.map((item) =>
                  jsx(ItemRow, { item }, item.id)
                ),
              }),
            ],
          }),
        ],
      }),
    ],
  });
}
