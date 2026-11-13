// #568 probe: record every expect step Playwright runs, per test and browser.
import { writeFileSync } from "node:fs";
import type { Reporter, TestCase, TestResult, TestStep } from "@playwright/test/reporter";

export default class CountExpects implements Reporter {
  private readonly counts: Record<string, string[]> = {};
  private readonly outcomes: Record<string, string> = {};

  onStepEnd(test: TestCase, _result: TestResult, step: TestStep): void {
    if (step.category === "expect") {
      const key = test.titlePath().filter(Boolean).join(" > ");
      (this.counts[key] ??= []).push(`${String(step.location?.line)} ${step.title}`);
    }
  }

  onTestEnd(test: TestCase, result: TestResult): void {
    this.outcomes[test.titlePath().filter(Boolean).join(" > ")] = result.status;
  }

  onEnd(): void {
    writeFileSync(
      process.env["EXPECT_COUNT_OUT"] ?? "expects.json",
      JSON.stringify({ counts: this.counts, outcomes: this.outcomes }, null, 1),
    );
  }
}
