import { jsx, jsxs } from "react/jsx-runtime";
import { formatTurnLog } from "../logic/battle.js";

function TypeChip(props) {
  const type = props.type;
  if (!type) return null;
  return jsx("span", {
    className: "hg-type hg-type--" + type,
    "data-type": type,
    title: type + " type",
    children: type,
  });
}

function EffectivenessBadge(props) {
  const label = props.label;
  if (!label) return null;
  return jsx("span", {
    className: "hg-badge hg-badge--" + label,
    "data-effectiveness": label,
    title: props.text || label,
    children: props.text || label,
  });
}

export function TurnLog(props = {}) {
  const events = Array.isArray(props.events) ? props.events : [];
  const rows = formatTurnLog(events, { participants: props.participants });
  const emptyText = props.emptyText || "No turns yet.";

  if (!rows.length) {
    return jsx("p", {
      className: "hg-muted",
      "data-placeholder": "turn-log",
      children: emptyText,
    });
  }

  const items = rows.map((row) =>
    jsxs(
      "li",
      {
        className: "hg-log__item",
        "data-round": String(row.round),
        "data-actor": row.actor || "",
        children: [
          jsx("span", {
            className: "hg-log__round",
            "data-column": "round",
            children: jsx("span", { className: "hg-badge", children: "R" + row.round }),
          }),
          jsx("span", {
            className: "hg-log__actor",
            "data-column": "actor",
            children: row.actorName,
          }),
          jsx("span", {
            className: "hg-log__move",
            "data-column": "move",
            children: row.moveLabel,
          }),
          jsx("span", {
            className: "hg-log__damage",
            "data-column": "damage",
            children: row.damage > 0 ? "-" + row.damage + " HP" : "",
          }),
          jsxs("span", {
            className: "hg-log__types",
            "data-column": "types",
            children: [
              jsx(TypeChip, { type: row.actorType }),
              jsx(TypeChip, { type: row.defenderType }),
            ],
          }),
          jsx("span", {
            className: "hg-log__effect",
            "data-column": "effect",
            children: jsx(EffectivenessBadge, {
              label: row.effectiveness,
              text: row.effectivenessText,
            }),
          }),
          jsx("span", {
            className: "hg-muted hg-log__hp",
            "data-column": "hp",
            children: row.hpAfter
              ? "HP " + String(row.hpAfter.a) + " / " + String(row.hpAfter.b)
              : "",
          }),
        ],
      },
      String(row.index)
    )
  );

  return jsxs("div", {
    className: "hg-log",
    "data-turn-log": "true",
    children: [
      jsx("h4", { children: "Turn log" }),
      jsx("ol", { className: "hg-log__list", children: items }),
    ],
  });
}
