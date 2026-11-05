/**
 * The messages between the broker page's content script and the side panel (spec §10.2), with
 * `chrome.runtime` stood in: a unit test has no browser.
 */
import { expect, test } from "vitest";
import { isAsk, isSnapshot, sendSnapshot, serveSnapshots, type Snapshot } from "../src/messages.ts";

const snapshot: Snapshot = {
  kind: "snapshot",
  url: "https://broker.steadyhand.test/portfolio",
  html: "<html><body>page</body></html>",
};

type Listener = (message: unknown, sender: unknown, respond: (answer: unknown) => void) => boolean;

/** A runtime that records what is sent and keeps the listeners added. */
const runtime = (send: (message: unknown) => Promise<unknown>) => {
  const sent: unknown[] = [];
  const listeners: Listener[] = [];
  return {
    sent,
    listeners,
    api: {
      sendMessage: (message: unknown) => {
        sent.push(message);
        return send(message);
      },
      onMessage: {
        addListener: (listener: Listener) => {
          listeners.push(listener);
        },
      },
    },
  };
};

test("an ask is a message of kind ask, and nothing else is", () => {
  expect(isAsk({ kind: "ask" })).toBe(true);
  expect(isAsk({ kind: "snapshot" })).toBe(false);
  expect(isAsk(null)).toBe(false);
  expect(isAsk("ask")).toBe(false);
});

test("a snapshot is a message of kind snapshot with a url and the page's text", () => {
  expect(isSnapshot(snapshot)).toBe(true);
  expect(isSnapshot({ kind: "snapshot", url: "u" })).toBe(false);
  expect(isSnapshot({ kind: "snapshot", html: "h" })).toBe(false);
  expect(isSnapshot({ kind: "ask", url: "u", html: "h" })).toBe(false);
  expect(isSnapshot(undefined)).toBe(false);
});

test("a snapshot is sent to the panel as it is", async () => {
  const { sent, api } = runtime(() => Promise.resolve(undefined));
  await sendSnapshot(api, snapshot);
  expect(sent).toEqual([snapshot]);
});

test("a send with no panel open is dropped without an error", async () => {
  const { api } = runtime(() =>
    Promise.reject(new Error("Could not establish connection. Receiving end does not exist.")),
  );
  await expect(sendSnapshot(api, snapshot)).resolves.toBeUndefined();
});

test("any other failure to send is not hidden", async () => {
  const failure = new Error("Extension context invalidated.");
  const { api } = runtime(() => Promise.reject(failure));
  await expect(sendSnapshot(api, snapshot)).rejects.toBe(failure);
});

test("served, the page is sent once at once and again on each ask, read fresh each time", async () => {
  const { sent, listeners, api } = runtime(() => Promise.resolve(undefined));
  const pages = [snapshot, { ...snapshot, html: "<html>later</html>" }];
  let reads = 0;
  await serveSnapshots(api, () => pages[reads++] ?? snapshot);
  expect(sent).toEqual([snapshot]);
  expect(listeners).toHaveLength(1);
  const answers: unknown[] = [];
  const [listener] = listeners;
  expect(listener?.({ kind: "ask" }, {}, (answer) => answers.push(answer))).toBe(false);
  expect(answers).toEqual([{ ...snapshot, html: "<html>later</html>" }]);
});

test("served, a message that is not an ask gets no answer and the page is not read", async () => {
  const { listeners, api } = runtime(() => Promise.resolve(undefined));
  let reads = 0;
  await serveSnapshots(api, () => {
    reads += 1;
    return snapshot;
  });
  const answers: unknown[] = [];
  expect(listeners[0]?.({ kind: "other" }, {}, (answer) => answers.push(answer))).toBe(false);
  expect(answers).toEqual([]);
  expect(reads).toBe(1);
});
