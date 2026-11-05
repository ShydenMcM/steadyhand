/** The messages between the broker page's content script and the side panel (spec §10.2): the
 * content script sends the page as it is, and the panel asks for it again. Nothing else passes. */

/** The page as the browser shows it: its address and its whole text, unparsed. */
export interface Snapshot {
  readonly kind: "snapshot";
  readonly url: string;
  readonly html: string;
}

/** The panel asking the page's content script for a fresh snapshot. */
export interface Ask {
  readonly kind: "ask";
}

/** What Chrome says when a message is sent and no page of the extension listens. */
const NO_RECEIVER = "Receiving end does not exist";

/** The part of `chrome.runtime` the content script uses. */
export interface Runtime {
  sendMessage(message: Snapshot): Promise<unknown>;
  readonly onMessage: {
    addListener(
      listener: (message: unknown, sender: unknown, respond: (answer: Snapshot) => void) => boolean,
    ): void;
  };
}

const kindOf = (message: unknown): unknown =>
  typeof message === "object" && message !== null ? (message as { kind?: unknown }).kind : null;

export const isAsk = (message: unknown): message is Ask => kindOf(message) === "ask";

export const isSnapshot = (message: unknown): message is Snapshot =>
  kindOf(message) === "snapshot" &&
  typeof (message as { url?: unknown }).url === "string" &&
  typeof (message as { html?: unknown }).html === "string";

/** Send `snapshot` to the panel. With no panel open no one receives it, which is expected: that
 * send is dropped. Any other failure is not hidden. */
export const sendSnapshot = async (runtime: Runtime, snapshot: Snapshot): Promise<void> => {
  try {
    await runtime.sendMessage(snapshot);
  } catch (failure) {
    if (!String(failure).includes(NO_RECEIVER)) {
      throw failure;
    }
  }
};

/** Answer each ask with the page as `read` gives it at that moment, and send it once now. */
export const serveSnapshots = (runtime: Runtime, read: () => Snapshot): Promise<void> => {
  runtime.onMessage.addListener((message, _sender, respond) => {
    if (isAsk(message)) {
      respond(read());
    }
    return false;
  });
  return sendSnapshot(runtime, read());
};
