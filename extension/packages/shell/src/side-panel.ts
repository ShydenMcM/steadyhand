// The side panel's page (spec §10.3): it opens the history record and starts the panel on the
// browser's own page, Chrome and clock.
import { openHistory } from "@steadyhand/history";
import { startPanel, type Panel } from "./panel.ts";

/** The panel once it is drawn; tests wait on it. */
export const opened: Promise<Panel> = openHistory(indexedDB).then((db) =>
  startPanel({
    page: document,
    db,
    runtime: chrome.runtime,
    tabs: chrome.tabs,
    clock: () => new Date(),
  }),
);
