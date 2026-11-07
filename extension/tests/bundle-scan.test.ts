import { expect, test } from "vitest";
import { scan, webScripts, adviceWords } from "./lib/bundle-scan.ts";

// The scan of each built bundle (#240 AC1-AC4, spec §11, §12.3). Code is read as acorn's parse
// tree, never as text, so a name in a string, a comment or an object key is not code. Here each
// forbidden form is planted and found; tests/integration/bundle-scan.test.ts scans the real build.

/** What `scan` finds in `code`, the place cut off. */
const whats = (code: string, contentScript = false): string[] =>
  scan(code, contentScript).found.map((one) => one.what);

// AC1: no bundle reaches the network or runs code made from text.
test.each([
  ["fetch(url)", "fetch"],
  ["self.fetch(url)", "fetch"],
  ['self["fetch"](url)', "fetch"],
  ["new XMLHttpRequest()", "XMLHttpRequest"],
  ['new WebSocket("wss://a.test")', "WebSocket"],
  ["new EventSource(url)", "EventSource"],
  ["navigator.sendBeacon(url, data)", "sendBeacon"],
  ["new RTCPeerConnection(config)", "RTCPeerConnection"],
  ['importScripts("more.js")', "importScripts"],
  ['import("./more.js")', "import()"],
  ['new Worker("worker.js")', "new Worker"],
  ['eval("2 + 2")', "eval"],
  ['new Function("a", "return a")', "new Function"],
  ['setTimeout("tick()", 5)', "setTimeout with a string"],
  ["setInterval(`tick()`, 5)", "setInterval with a string"],
  ['tag.src = "https://cdn.a.test/x.js"', "src from the web"],
  ['tag.setAttribute("src", "http://cdn.a.test/x.js")', "src from the web"],
])("no bundle may hold %s", (code, what) => {
  expect(whats(code)).toEqual([what]);
});

// AC2: the content script drives nothing on the broker's page and writes nothing to it.
test.each([
  ["link.click()", "click()"],
  ['link["click"]()', "click()"],
  ["form.submit()", "submit()"],
  ["form.requestSubmit()", "requestSubmit()"],
  ["field.dispatchEvent(change)", "dispatchEvent()"],
  ["field.focus()", "focus()"],
  ["field.blur()", "blur()"],
  ['field.value = "9"', "value written"],
  ['field["value"] = "9"', "value written"],
  ['field.value += "9"', "value written"],
  ['cell.innerHTML = "<i>"', "innerHTML written"],
  ['cell.outerHTML = "<i>"', "outerHTML written"],
  ['cell.textContent = "9"', "textContent written"],
  ["box.checked = false", "checked written"],
  ['field.addEventListener("input", seen)', "listens for input"],
  ['field.addEventListener("keydown", seen)', "listens for keydown"],
  ['field.addEventListener("change", seen)', "listens for change"],
  ['form.addEventListener("submit", seen)', "listens for submit"],
  ["field.addEventListener(kind, seen)", "listens for an event it does not name"],
])("the content script may not hold %s", (code, what) => {
  expect(whats(code, true)).toEqual([what]);
});

test("the panel may click, focus, write values and listen for clicks", () => {
  expect(
    whats(
      'a.click(); a.focus(); a.value = "1"; a.textContent = "x"; a.addEventListener("click", f)',
    ),
  ).toEqual([]);
});

test("the content script may read the page and listen for its own load", () => {
  expect(
    whats('post(document.documentElement.outerHTML, a.value); addEventListener("load", f)', true),
  ).toEqual([]);
});

// AC3: what is not code is not read as code.
test("a forbidden name in a string, a template's text, a comment or a key is not code", () => {
  const code = [
    'const said = "fetch(url) eval(x) new Worker()";',
    'const shown = `setTimeout("x") import() ${said}`;',
    "// fetch(url); eval(code)",
    "/* new Function() */",
    "const table = { fetch: 1, eval: 2, method() {} };",
    "use(said, shown, table);",
  ].join("\n");
  expect(whats(code)).toEqual([]);
});

test("a computed key is code", () => {
  expect(whats("table[fetch](url); use({ [eval]: 1 });")).toEqual(["fetch", "eval"]);
});

test("a template with no substitution is read as its text", () => {
  expect(whats("tag.src = `https://cdn.a.test/x.js`")).toEqual(["src from the web"]);
  expect(whats("field.addEventListener(`input`, seen)", true)).toEqual(["listens for input"]);
});

test("a web address built in a template is still from the web", () => {
  expect(whats("tag.src = `https://${host}/x.js`")).toEqual(["src from the web"]);
});

test("a timer given a number is not given a string", () => {
  expect(whats("setTimeout(0, 5)")).toEqual([]);
});

test("a call of what a call returns names nothing", () => {
  expect(whats('make()("tick()")', true)).toEqual([]);
});

test("an assignment to a pattern names nothing", () => {
  expect(whats("[first] = rows; ({ last } = table);", true)).toEqual([]);
});

test("a timer given a function is allowed", () => {
  expect(whats("setTimeout(() => tick(), 5); setInterval(tick, 5);")).toEqual([]);
});

test("each finding names its line and column", () => {
  expect(scan('tick();\n   eval("1");', false).found).toEqual([
    { line: 2, column: 3, what: "eval" },
  ]);
});

test("the verdict counts the calls, constructions and assignments it judged", () => {
  expect(scan('tick(); new Date(); a = 1; b.c = 2; import("./x.js");', false).judged).toBe(5);
});

test("a scan that judged nothing is refused, never passed", () => {
  expect(() => scan("const a = 1;", false)).toThrow(
    "the scan judged no call, construction or assignment",
  );
});

test("the panel page's script tags from the web are found, its own script is not", () => {
  expect(
    webScripts(
      '<script src="side-panel.js"></script>' +
        '<script async src="https://cdn.a.test/x.js"></script>' +
        "<SCRIPT Src='http://cdn.a.test/y.js'></SCRIPT>",
    ),
  ).toEqual(["https://cdn.a.test/x.js", "http://cdn.a.test/y.js"]);
});

// AC4: shipped text never advises.
test.each([
  ["steadyhand would recommend it", ["recommend"]],
  ["Our RECOMMENDATION is", ["RECOMMEND"]],
  ["here we suggest BBCA", ["we suggest"]],
  ["We\nSuggest it", ["We\nSuggest"]],
])("the advice words in %j are found", (text, words) => {
  expect(adviceWords(text)).toEqual(words);
});

test("text that only says what a strategy implies has no advice words", () => {
  expect(adviceWords("What the strategy you chose implies, read from your broker's page.")).toEqual(
    [],
  );
});
