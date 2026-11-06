import { jsx, jsxs } from "react/jsx-runtime";

export function CareMeter(props = {}) {
  const label = props.label || "Care";
  const max = Number(props.max) > 0 ? Number(props.max) : 100;
  const value = Math.max(0, Math.min(Number(props.value) || 0, max));
  const percent = Math.round((value / max) * 100);

  return jsxs("div", {
    className: "hg-meter",
    "data-meter": label.toLowerCase(),
    role: "meter",
    "aria-label": label,
    "aria-valuemin": "0",
    "aria-valuemax": String(max),
    "aria-valuenow": String(value),
    children: [
      jsxs("div", {
        className: "hg-meter__head",
        children: [
          jsx("span", { children: label }),
          jsx("span", { children: value + " / " + max }),
        ],
      }),
      jsx("div", {
        className: "hg-meter__track",
        children: jsx("div", {
          className: "hg-meter__fill",
          style: { width: percent + "%" },
        }),
      }),
    ],
  });
}
