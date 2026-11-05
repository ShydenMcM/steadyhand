// The content script (spec §10.2): it sends the panel the broker page as it is, on load and when
// the panel asks. It parses nothing, changes nothing, listens to no input and keeps no state.
import { serveSnapshots } from "./messages.ts";

void serveSnapshots(chrome.runtime, () => ({
  kind: "snapshot",
  url: location.href,
  html: document.documentElement.outerHTML,
}));
