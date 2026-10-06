import * as history from "@steadyhand/history";
import * as readers from "@steadyhand/readers";

// EXT S14a builds the panel. Until then the page records the packages it was built from, which
// shows the bundle carries the whole workspace: a bare package import would not load in Chrome.
const packages = new Set([
  ...readers.BUILT_ON,
  readers.PACKAGE,
  ...history.BUILT_ON,
  history.PACKAGE,
]);
document.documentElement.dataset["packages"] = [...packages].join(" ");
