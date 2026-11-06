import { useEffect, useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
import { StateNotice, UI_STATES } from "../states.js";
import { NpcHostBanner } from "../components/NpcHostBanner.js";
import { PetPreview } from "../components/PetPreview.js";
import { extractPetId } from "../logic/habitat.js";
import {
  groupCatalogBySlot,
  itemAvailability,
  manifestFromCatalog,
  normaliseWallet,
  readEnvelope,
} from "../logic/shop.js";

export const SHOP_PLACEHOLDER_ITEMS = Object.freeze([
  { id: "placeholder.crown", name: "Binary Crown", slot: "head", priceBits: 2000 },
  { id: "placeholder.scarf", name: "Patch Scarf", slot: "front", priceBits: 350 },
  { id: "placeholder.aura", name: "Soft Static Aura", slot: "aura", priceBits: 700 },
]);

function stateForEnvelope(result) {
  if (!result || result.ok) return null;
  if (result.status === "auth_missing" || result.status === "unauthorized") {
    return UI_STATES.AUTH_MISSING;
  }
  if (
    result.status === "offline" ||
    result.status === "unavailable" ||
    result.status === "http_error" ||
    result.status === "not_allowed"
  ) {
    return UI_STATES.SERVICE_UNAVAILABLE;
  }
  return null;
}

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

function StubShop(props) {
  return jsxs("section", {
    className: "hg-shop",
    "data-tab": "shop",
    children: [
      jsx(StateNotice, { state: props.uiState }),
      jsx(NpcHostBanner, { surface: "shop" }),
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

export function ShopTab(props = {}) {
  const api = props.api;
  const hasApi = Boolean(api && typeof api.get === "function" && typeof api.post === "function");
  const requestedPetId = props.petId || (props.pet && props.pet.id) || "";
  const [wallet, setWallet] = useState(normaliseWallet(props.wallet));
  const [catalog, setCatalog] = useState(props.catalog || null);
  const [manifest, setManifest] = useState(
    props.manifest || props.assetManifest || null
  );
  const [pet, setPet] = useState(props.pet || null);
  const [loadout, setLoadout] = useState(props.loadout || {});
  const [owned, setOwned] = useState(new Set());
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [bridgeState, setBridgeState] = useState(null);

  useEffect(() => {
    if (!hasApi) return undefined;
    let alive = true;

    async function load() {
      setError("");
      let meData = null;
      let meEnvelope = null;

      const walletRequest = api.get("/wallet").catch(() => null);
      const catalogRequest = api.get("/catalog").catch(() => null);
      const meRequest =
        requestedPetId || props.pet
          ? Promise.resolve(null)
          : api.get("/me").catch(() => null);

      const [walletEnvelope, catalogEnvelope, meEnvelopeResult] = await Promise.all([
        walletRequest,
        catalogRequest,
        meRequest,
      ]);
      if (!alive) return;

      const walletResult = readEnvelope(walletEnvelope);
      if (walletResult.ok) {
        setWallet(normaliseWallet(walletResult.data));
      } else {
        setBridgeState(stateForEnvelope(walletResult));
        if (walletResult.message) setError(walletResult.message);
      }

      const catalogResult = readEnvelope(catalogEnvelope);
      if (catalogResult.ok) {
        setCatalog(catalogResult.data);
        const fromCatalog = manifestFromCatalog(catalogResult.data);
        if (fromCatalog) setManifest((current) => current || fromCatalog);
        const seeded = new Set();
        const items =
          catalogResult.data && Array.isArray(catalogResult.data.items)
            ? catalogResult.data.items
            : [];
        for (const item of items) {
          if (item && item.id && (item.owned || item.inventory_owned)) seeded.add(item.id);
        }
        if (seeded.size) setOwned(seeded);
      } else {
        setBridgeState(stateForEnvelope(catalogResult));
        if (catalogResult.message) setError(catalogResult.message);
      }

      let petId = requestedPetId;
      if (meEnvelopeResult) {
        meEnvelope = readEnvelope(meEnvelopeResult);
        if (meEnvelope.ok) {
          meData = meEnvelope.data;
          petId = requestedPetId || extractPetId(meData);
          if (!petId && meData && meData.pet && meData.pet.id) {
            petId = meData.pet.id;
            setPet(meData.pet);
          }
        }
      }

      if (petId && !(props.pet && props.pet.id === petId)) {
        try {
          const petResult = readEnvelope(
            await api.get("/pets/" + encodeURIComponent(petId))
          );
          if (alive && petResult.ok && petResult.data) setPet(petResult.data);
        } catch (_error) {
          // The catalog and wallet remain usable without a pet preview.
        }
      }
    }

    load();
    return function cleanup() {
      alive = false;
    };
  }, [api, hasApi, requestedPetId]);

  const uiState = props.state || props.uiState || bridgeState || UI_STATES.READY;
  if (!hasApi) {
    return jsx(StubShop, { uiState });
  }

  const walletView = normaliseWallet(wallet);
  const petId = requestedPetId || (pet && pet.id) || "";
  const groups = groupCatalogBySlot(catalog).map((group) => ({
    ...group,
    items: group.items.map((item) => ({
      ...item,
      owned: Boolean(item.owned || owned.has(item.id)),
    })),
  }));

  async function buy(item) {
    setBusy("buy:" + item.id);
    setError("");
    try {
      const result = readEnvelope(
        await api.post("/shop/purchases", { item_id: item.id })
      );
      if (!result.ok) {
        if (result.code === "item_already_owned") {
          setOwned((current) => new Set(current).add(item.id));
        } else {
          setBridgeState(stateForEnvelope(result));
          setError(result.message);
        }
        return;
      }
      if (result.data && result.data.wallet) {
        setWallet(normaliseWallet(result.data.wallet));
      }
      setOwned((current) => new Set(current).add(item.id));
    } catch (_error) {
      setError("Purchase could not be completed.");
    } finally {
      setBusy("");
    }
  }

  async function equip(item) {
    if (!petId) {
      setError("Choose a pet before equipping an item.");
      return;
    }
    setBusy("equip:" + item.id);
    setError("");
    try {
      const result = readEnvelope(
        await api.post(
          "/pets/" + encodeURIComponent(petId) + "/equip",
          { item_id: item.id, slot: item.slot }
        )
      );
      if (!result.ok) {
        setBridgeState(stateForEnvelope(result));
        setError(result.message);
        return;
      }
      setLoadout((result.data && result.data.loadout) || {});
      setOwned((current) => new Set(current).add(item.id));
    } catch (_error) {
      setError("Equip could not be completed.");
    } finally {
      setBusy("");
    }
  }

  async function unequip(slot) {
    if (!petId) {
      setError("Choose a pet before removing an item.");
      return;
    }
    setBusy("unequip:" + slot);
    setError("");
    try {
      const result = readEnvelope(
        await api.post(
          "/pets/" + encodeURIComponent(petId) + "/unequip",
          { slot }
        )
      );
      if (!result.ok) {
        setBridgeState(stateForEnvelope(result));
        setError(result.message);
        return;
      }
      setLoadout((result.data && result.data.loadout) || {});
    } catch (_error) {
      setError("Unequip could not be completed.");
    } finally {
      setBusy("");
    }
  }

  return jsxs("section", {
    className: "hg-shop",
    "data-tab": "shop",
    children: [
      jsx(StateNotice, { state: uiState }),
      jsx(NpcHostBanner, { surface: "shop" }),
      error
        ? jsx("p", { className: "hg-error", role: "alert", children: error })
        : null,
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Wallet" }),
          jsxs("p", {
            children: [
              jsx("span", { className: "hg-label", children: "Bits balance" }),
              jsx("strong", {
                "data-placeholder": "bits-balance",
                children: walletView.balance + " Bits",
              }),
            ],
          }),
          jsx("p", {
            className: "hg-muted",
            children:
              "Purchases debit Bits on the server. The desktop bridge never sees or returns session tokens.",
          }),
        ],
      }),
      jsxs("div", {
        className: "hg-card",
        children: [
          jsx("h3", { children: "Pet preview" }),
          jsx(PetPreview, {
            pet,
            loadout,
            catalog,
            manifest,
            assetBaseUrl: props.assetBaseUrl,
            label: (pet && pet.name ? pet.name : "Pet") + " loadout preview",
          }),
        ],
      }),
      groups.length === 0
        ? jsx("p", {
            className: "hg-muted",
            children: "No catalog items are available yet.",
          })
        : null,
      groups.map((group) =>
        jsxs(
          "div",
          {
            className: "hg-card",
            "data-slot": group.slot,
            children: [
              jsx("h3", { children: group.label }),
              jsxs("table", {
                className: "hg-table",
                children: [
                  jsx("thead", {
                    children: jsxs("tr", {
                      children: [
                        jsx("th", { children: "Item" }),
                        jsx("th", { children: "Rarity" }),
                        jsx("th", { children: "Price" }),
                        jsx("th", { children: "Action" }),
                      ],
                    }),
                  }),
                  jsx("tbody", {
                    children: group.items.map((item) => {
                      const availability = itemAvailability({
                        item,
                        wallet: walletView,
                        petId,
                        loadout,
                      });
                      return jsxs(
                        "tr",
                        {
                          className: availability.equipped ? "hg-row--equipped" : undefined,
                          children: [
                            jsx("td", {
                              children: [
                                item.name,
                                availability.equipped
                                  ? jsx("span", {
                                      className: "hg-badge",
                                      children: "Equipped",
                                    })
                                  : null,
                              ],
                            }),
                            jsx("td", { children: item.rarity }),
                            jsx("td", { children: item.priceBits + " Bits" }),
                            jsx("td", {
                              className: "hg-row",
                              children: [
                                jsx("button", {
                                  type: "button",
                                  className: "hg-btn hg-btn--primary",
                                  "data-action": "buy",
                                  "data-item-id": item.id,
                                  disabled:
                                    Boolean(busy) || item.owned || !availability.affordable,
                                  onClick: function () {
                                    buy(item);
                                  },
                                  children: item.owned
                                    ? "Owned"
                                    : busy === "buy:" + item.id
                                      ? "Buying..."
                                      : "Buy",
                                }),
                                availability.equipped
                                  ? jsx("button", {
                                      type: "button",
                                      className: "hg-btn",
                                      "data-action": "unequip",
                                      "data-item-id": item.id,
                                      disabled: Boolean(busy) || !petId,
                                      onClick: function () {
                                        unequip(item.slot);
                                      },
                                      children:
                                        busy === "unequip:" + item.slot
                                          ? "Removing..."
                                          : "Unequip",
                                    })
                                  : jsx("button", {
                                      type: "button",
                                      className: "hg-btn",
                                      "data-action": "equip",
                                      "data-item-id": item.id,
                                      disabled: Boolean(busy) || !petId,
                                      onClick: function () {
                                        equip(item);
                                      },
                                      children:
                                        busy === "equip:" + item.id
                                          ? "Equipping..."
                                          : "Equip",
                                    }),
                              ],
                            }),
                          ],
                        },
                        item.id
                      );
                    }),
                  }),
                ],
              }),
            ],
          },
          group.slot
        )
      ),
    ],
  });
}
