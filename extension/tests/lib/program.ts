/**
 * A script's program entry (#374 AC6): its last line is `asProgram(import.meta.main, work, ...)`.
 * Run by Node as its program, the work sets the exit status; imported, as a unit test imports the
 * script, nothing runs. The work and its arguments are passed, never wrapped in a function of the
 * script's own, so every line and function of the script runs in-process.
 */
export function asProgram<Args extends unknown[]>(
  isProgram: boolean | undefined,
  work: (...args: Args) => number,
  ...args: Args
): void {
  if (isProgram) {
    process.exitCode = work(...args);
  }
}
