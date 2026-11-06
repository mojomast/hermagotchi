(function () {
  "use strict";
  var SDK = window.__HERMES_PLUGIN_SDK__;
  var PLUGINS = window.__HERMES_PLUGINS__;
  if (!SDK || !PLUGINS) return;
  var React = SDK.React;
  var hooks = SDK.hooks || {};
  var useMemo = hooks.useMemo || function (fn) { return fn(); };

  function HermagotchiPage() {
    var tab = useMemo(function () {
      try {
        var sp = new URLSearchParams(window.location.search);
        return sp.get("hgTab") || sp.get("tab") || "habitat";
      } catch (_e) {
        return "habitat";
      }
    }, []);
    var base =
      (typeof window.HERMES_BASE_PATH === "string" && window.HERMES_BASE_PATH) ||
      "";
    var src =
      base +
      "/dashboard-plugins/hermagotchi/pane.html?tab=" +
      encodeURIComponent(tab);
    return React.createElement("iframe", {
      title: "Hermagotchi",
      src: src,
      style: {
        width: "100%",
        height: "calc(100vh - 56px)",
        border: 0,
        display: "block",
        background: "#0b0d16",
      },
    });
  }

  PLUGINS.register("hermagotchi", HermagotchiPage);
})();
