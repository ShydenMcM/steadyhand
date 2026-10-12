/**
 * Prints every unit file's load, heaviest first, at the end of each run (#285). A unit file with
 * no load recorded means the clock did not run for it, so the run fails rather than report less.
 */
import type { Reporter, TestModule } from "vitest/node";
import { type Load, report } from "./lib/load-clock.ts";

export default class LoadReport implements Reporter {
  onTestRunEnd(testModules: readonly TestModule[]): void {
    const unit = testModules.filter((module) => module.project.name === "unit");
    const loads: Load[] = [];
    for (const module of unit) {
      const { load } = module.meta();
      if (load === undefined) {
        console.error(`LOAD CLOCK: no load recorded for ${module.moduleId}`);
        process.exitCode = 1;
      } else {
        loads.push(load);
      }
    }
    console.log(report(loads).join("\n"));
  }
}
