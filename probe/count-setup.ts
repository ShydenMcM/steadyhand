// #570 probe: after each test, the assertions it executed, as Vitest counts them.
import { appendFileSync } from "node:fs";
import { afterEach, expect } from "vitest";

afterEach((context) => {
  appendFileSync(
    process.env["VITEST_COUNT_OUT"] ?? "vitest-counts.jsonl",
    `${JSON.stringify({
      file: context.task.file.name,
      test: context.task.name,
      assertions: expect.getState().assertionCalls,
    })}\n`,
  );
});
