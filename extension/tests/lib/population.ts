/**
 * What a guard proves it saw, for the guards that can pass by finding nothing (spec §14.2).
 *
 * Shyden's rule (2026-10-02): such a guard proves what it inspected, counted at the level it
 * judges. `searched` puts that count inside the verdict, so an empty finding never stands alone.
 * The Python guards' `tests/meta/population.py` is its twin.
 */

/** A verdict over a population of none: it says nothing, so it is refused. */
export class BlindGuardError extends Error {
  override name = "BlindGuardError";
}

/** `findings`, once `of` members of the population (`what`) were judged. */
export const searched = <T>(findings: T, { of, what }: { of: number; what: string }): T => {
  if (of < 1) {
    throw new BlindGuardError(`judged no ${what}: an empty finding over nothing proves nothing`);
  }
  return findings;
};
