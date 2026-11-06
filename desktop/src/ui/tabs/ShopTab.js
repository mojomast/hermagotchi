import { useEffect, useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
import { StateNotice, UI_STATES } from "../states.js";
import { NpcHostBanner } from "../components/NpcHostBanner.js";
import { useAuthedAssetUrl } from "../components/AuthedImg.js";
import { PetPreview } from "../components/PetPreview.js";
import { extractPetId } from "../logic/habitat.js";
import {
  compareItemsByPrice,
  groupCatalogBySlot,
  itemAvailability,
  itemThumbUrl,
  manifestFromCatalog,
  normaliseWallet,
  RARITY_LABELS,
  readEnvelope,
} from "../logic/shop.js";

const SLOT_MARKS = Object.freeze({
  head: "HAT",
  face: "FACE",
  back: "BACK",
  front: "HAND",
  aura: "AURA",
  emote: "EMOTE",
  habitat: "HOME",
  title: "TITLE",
});

export const SHOP_PLACEHOLDER_ITEMS = Object.freeze([
  { id: "placeholder.crown", name: "Binary Crown", slot: "head", priceBits: 2000 },
  { id: "placeholder.scarf", name: "Patch Scarf", slot: "front", priceBits: 350 },
  { id: "placeholder.aura", name: "Soft Static Aura", slot: "aura", priceBits: 700 },
]);

export const SHOP_FILTERS = Object.freeze([
  { id: "all", label: "All" },
  { id: "head", label: "Hats" },
  { id: "face", label: "Face" },
  { id: "back", label: "Neck/Back" },
  { id: "front", label: "Hand props" },
  { id: "aura", label: "Auras" },
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
      props.uiState && props.uiState !== UI_STATES.READY
        ? jsx(StateNotice, { state: props.uiState })
        : null,
      jsx(NpcHostBanner, { surface: "shop", api: props.api, assetBaseUrl: props.assetBaseUrl }),
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

function itemInitial(name) {
  const text = String(name || "").trim();
  return text ? text.slice(0, 1).toUpperCase() : "?";
}

function RarityBadge(props) {
  const rarity = String((props.item && props.item.rarity) || "").toLowerCase();
  if (rarity !== "legendary" && rarity !== "mythic") return null;
  return jsx("span", {
    className: "hg-badge hg-badge--" + rarity,
    "data-rarity": rarity,
    children: RARITY_LABELS[rarity] || rarity,
  });
}

function ShopCard(props) {
  const item = props.item;
  const availability = props.availability;
  const busy = props.busy;
  const thumb = props.thumb;
  const equipped = availability.equipped;
  const selected = Boolean(props.selected);
  const authed = useAuthedAssetUrl(thumb || "");
  const [thumbState, setThumbState] = useState(
    thumb ? "loading" : "empty"
  );

  useEffect(() => {
    if (!thumb) {
      setThumbState("empty");
      return;
    }
    if (authed.status === "loading") {
      setThumbState("loading");
      return;
    }
    if (authed.status === "error" || !authed.url) {
      setThumbState("error");
      return;
    }
    // Keep "loading" until the img element fires onLoad so data-blank stays true
    // until pixels are actually painted.
    setThumbState(function (prev) {
      return prev === "loaded" ? "loaded" : "loading";
    });
  }, [thumb, authed.status, authed.url]);

  const showImage = Boolean(authed.url) && thumbState !== "error";
  const blank = thumbState === "loaded" ? "false" : "true";

  const fallback = jsxs("span", {
    className: "hg-shop-card__thumb-fallback",
    "data-slot": item.slot,
    role: "img",
    "aria-label": item.name + " (" + item.slotLabel + ") preview",
    children: [
      jsx("span", {
        className: "hg-shop-card__thumb-icon",
        "aria-hidden": "true",
        children: SLOT_MARKS[item.slot] || "ITEM",
      }),
      jsx("span", {
        className: "hg-shop-card__thumb-initial",
        "aria-hidden": "true",
        children: itemInitial(item.name),
      }),
      jsx("span", {
        className: "hg-shop-card__thumb-label",
        children: item.slotLabel,
      }),
    ],
  });

  return jsxs("article", {
    className:
      "hg-shop-card" +
      (item.owned ? " hg-shop-card--owned" : "") +
      (equipped ? " hg-shop-card--equipped" : "") +
      (selected ? " hg-shop-card--selected" : ""),
    "data-item-id": item.id,
    "data-slot": item.slot,
    "data-owned": item.owned ? "true" : "false",
    "data-equipped": equipped ? "true" : "false",
    "data-selected": selected ? "true" : "false",
    onClick: function () {
      if (typeof props.onSelect === "function") props.onSelect(item);
    },
    children: [
      jsx("div", {
        className: "hg-shop-card__thumb",
        "data-blank": blank,
        "data-thumb-state": thumbState,
        children: showImage
          ? jsx("img", {
              className: "hg-shop-card__image",
              src: authed.url,
              alt: item.name,
              "data-blank": blank,
              loading: "lazy",
              decoding: "async",
              draggable: "false",
              onLoad: function () {
                setThumbState("loaded");
              },
              onError: function () {
                setThumbState("error");
              },
            })
          : fallback,
      }),
      jsx("h4", { className: "hg-shop-card__name", children: item.name }),
      jsxs("div", {
        className: "hg-shop-card__meta",
        children: [
          jsx("span", { className: "hg-shop-card__slot", children: item.slotLabel }),
          jsx("span", {
            className: "hg-shop-card__price",
            children: item.priceBits + " Bits",
          }),
        ],
      }),
      jsxs("div", {
        className: "hg-shop-card__badges",
        children: [
          jsx(RarityBadge, { item }, "rarity"),
          item.owned
            ? jsx("span", { className: "hg-badge", children: "Owned" })
            : null,
          equipped
            ? jsx("span", {
                className: "hg-badge hg-badge--equipped",
                children: "Equipped",
              })
            : null,
        ],
      }),
      jsxs("div", {
        className: "hg-shop-card__actions",
        children: [
          jsx("button", {
            type: "button",
            className: "hg-btn hg-btn--primary",
            "data-action": "buy",
            "data-item-id": item.id,
            disabled: Boolean(busy) || item.owned || !availability.affordable,
            onClick: function () {
              props.onBuy(item);
            },
            children: item.owned
              ? "Owned"
              : busy === "buy:" + item.id
                ? "Buying..."
                : "Buy",
          }),
          equipped
            ? jsx("button", {
                type: "button",
                className: "hg-btn",
                "data-action": "unequip",
                "data-item-id": item.id,
                disabled: Boolean(busy) || !props.petId,
                onClick: function () {
                  props.onUnequip(item.slot);
                },
                children:
                  busy === "unequip:" + item.slot ? "Removing..." : "Unequip",
              })
            : jsx("button", {
                type: "button",
                className: "hg-btn",
                "data-action": "equip",
                "data-item-id": item.id,
                disabled: Boolean(busy) || !props.petId,
                onClick: function () {
                  props.onEquip(item);
                },
                children:
                  busy === "equip:" + item.id ? "Equipping..." : "Equip",
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
  const [selectedItem, setSelectedItem] = useState(null);
  const [owned, setOwned] = useState(new Set());
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [bridgeState, setBridgeState] = useState(null);
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");

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

  useEffect(() => {
    if (!hasApi || manifest) return undefined;
    if (!api.assets || typeof api.assets.manifest !== "function") return undefined;
    let alive = true;
    api.assets.manifest().then(
      function (envelope) {
        if (alive && envelope && envelope.ok && envelope.data) {
          setManifest(envelope.data);
        }
      },
      function () {}
    );
    return function cleanup() {
      alive = false;
    };
  }, [api, hasApi, manifest]);

  const uiState = props.state || props.uiState || bridgeState || UI_STATES.READY;
  if (!hasApi) {
    return jsx(StubShop, { uiState });
  }

  const assetBase =
    props.assetBaseUrl ||
    (api.assets && typeof api.assets.url === "function"
      ? api.assets.url("")
      : "");
  const walletView = normaliseWallet(wallet);
  const petId = requestedPetId || (pet && pet.id) || "";
  const groups = groupCatalogBySlot(catalog).map((group) => ({
    ...group,
    items: group.items.map((item) => ({
      ...item,
      owned: Boolean(item.owned || owned.has(item.id)),
    })),
  }));
  const allItems = groups.reduce((items, group) => items.concat(group.items), []);
  const needle = query.trim().toLowerCase();
  const visibleItems = allItems
    .filter(function (item) {
      if (filter !== "all" && item.slot !== filter) return false;
      if (!needle) return true;
      return (
        item.name.toLowerCase().includes(needle) ||
        item.id.toLowerCase().includes(needle) ||
        item.slot.toLowerCase().includes(needle)
      );
    })
    .sort(compareItemsByPrice);

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
      uiState && uiState !== UI_STATES.READY
        ? jsx(StateNotice, { state: uiState })
        : null,
      jsx(NpcHostBanner, { surface: "shop", api: api, assetBaseUrl: props.assetBaseUrl || assetBase }),
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
          jsx("div", {
              className: "hg-shop-preview",
              children: jsx(PetPreview, {
              pet,
              loadout: (function () {
                if (!selectedItem) return loadout;
                const next = Object.assign({}, loadout || {});
                next[selectedItem.slot] = selectedItem.id;
                return next;
              })(),
              catalog,
              manifest,
              assetBaseUrl: props.assetBaseUrl || assetBase,
              label: (pet && pet.name ? pet.name : "Pet") + " loadout preview",
            }),
            }),
        ],
      }),
      jsxs("div", {
        className: "hg-card hg-shop-catalog",
        children: [
          jsxs("header", {
            className: "hg-card__header",
            children: [
              jsx("h3", { children: "Merch" }),
              jsx("span", {
                className: "hg-muted",
                "data-shop-count": String(visibleItems.length),
                children:
                  visibleItems.length +
                  " item" +
                  (visibleItems.length === 1 ? "" : "s"),
              }),
            ],
          }),
          jsxs("div", {
            className: "hg-shop-tabs",
            role: "tablist",
            "aria-label": "Shop item slots",
            children: SHOP_FILTERS.map((option) =>
              jsx(
                "button",
                {
                  type: "button",
                  role: "tab",
                  "aria-selected": filter === option.id ? "true" : "false",
                  className:
                    "hg-shop-tab" +
                    (filter === option.id ? " hg-shop-tab--active" : ""),
                  "data-filter": option.id,
                  onClick: function () {
                    setFilter(option.id);
                  },
                  children: option.label,
                },
                option.id
              )
            ),
          }),
          jsx("label", {
            className: "hg-shop-search",
            children: [
              jsx("span", { className: "hg-label", children: "Search" }),
              jsx("input", {
                className: "hg-input hg-shop-search__input",
                type: "search",
                value: query,
                placeholder: "Find merch by name",
                "aria-label": "Search shop items",
                onChange: function (event) {
                  setQuery(event.target.value);
                },
              }),
            ],
          }),
          visibleItems.length === 0
            ? jsx("p", {
                className: "hg-muted hg-shop-empty",
                children:
                  allItems.length === 0
                    ? "No catalog items are available yet."
                    : "No merch matches that filter.",
              })
            : jsx("div", {
                className: "hg-shop-grid",
                children: visibleItems.map((item) => {
                  const availability = itemAvailability({
                    item,
                    wallet: walletView,
                    petId,
                    loadout,
                  });
                  return jsx(
                    ShopCard,
                    {
                      item,
                      availability,
                      busy,
                      petId,
                      thumb: itemThumbUrl(assetBase, item, manifest),
                      selected: selectedItem && selectedItem.id === item.id,
                      onSelect: setSelectedItem,
                      onBuy: buy,
                      onEquip: equip,
                      onUnequip: unequip,
                    },
                    item.id
                  );
                }),
              }),
        ],
      }),
    ],
  });
}
