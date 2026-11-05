/**
 * The side panel's page, loaded in-process with the browser stood in (#238): it opens history on
 * the page's IndexedDB and starts the panel on the page's own document, Chrome and clock. The
 * built bundle loading in Chrome is the browser suite's (AC5).
 */
import { IDBFactory } from "fake-indexeddb";
import { afterEach, expect, test, vi } from "vitest";
import { DISCLAIMER } from "../src/advice-view.ts";

afterEach(() => {
  vi.unstubAllGlobals();
});

interface Element {
  id: string;
  textContent: string;
  children: Element[];
}

const element = (): Element & Record<string, unknown> => {
  const made: Element & Record<string, unknown> = {
    id: "",
    textContent: "",
    children: [],
    value: "",
    htmlFor: "",
    append: (...children: Element[]) => {
      made.children.push(...children);
    },
    replaceChildren: (...children: Element[]) => {
      made.children = children;
    },
    addEventListener: () => undefined,
  };
  return made;
};

const all = (root: Element): Element[] => [root, ...root.children.flatMap(all)];

test("the page starts the panel on the browser's document, Chrome and IndexedDB", async () => {
  const body = element();
  const listened: unknown[] = [];
  vi.stubGlobal("indexedDB", new IDBFactory());
  vi.stubGlobal("document", { body, createElement: element });
  vi.stubGlobal("chrome", {
    runtime: { onMessage: { addListener: (listener: unknown) => listened.push(listener) } },
    tabs: {},
  });
  const { opened } = await import("../src/side-panel.ts");
  await (await opened).settled();
  expect(listened).toHaveLength(1);
  expect(all(body).find((each) => each.id === "disclaimer")?.textContent).toBe(DISCLAIMER);
  expect(all(body).find((each) => each.id === "advice")?.children.length).toBeGreaterThan(0);
});
