/**
 * Prints every unit file's load, heaviest first (#285), and the heaviest unit tests' own CPU and
 * wall (#323), at the end of each run. A unit file with no load recorded, or a test that ran with
 * no time recorded, means a clock did not run for it, so the run fails rather than report less.
 */
import type { Reporter, TestModule } from "vitest/node";
import { type Load, loadOf, report } from "./lib/load-clock.ts";
import { type Spent, spentOf, testReport } from "./lib/test-clock.ts";

const RAN = new Set(["passed", "failed"]);

export default class LoadReport implements Reporter {
  onTestRunEnd(testModules: readonly TestModule[]): void {
    const unit = testModules.filter((module) => module.project.name === "unit");
    const loads: Load[] = [];
    const spent: Spent[] = [];
    for (const module of unit) {
      const load = loadOf(module.meta());
      if (load === undefined) {
        console.error(`LOAD CLOCK: no load recorded for ${module.moduleId}`);
        process.exitCode = 1;
      } else {
        loads.push(load);
      }
      for (const testCase of module.children.allTests()) {
        if (!RAN.has(testCase.result().state)) continue;
        const one = spentOf(testCase.meta());
        if (one === undefined) {
          console.error(`TEST CLOCK: no time recorded for ${testCase.fullName}`);
          process.exitCode = 1;
        } else {
          spent.push(one);
        }
      }
    }
    console.log(report(loads).join("\n"));
    if (unit.length > 0) console.log(testReport(spent).join("\n"));
  }
}
