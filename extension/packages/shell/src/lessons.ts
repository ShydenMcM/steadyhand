/** The lesson catalogue the Lessons tab renders (spec §13): modules in order, each with its
 * lessons in order. */

import type { Lesson } from "./lesson-text.ts";

export interface LessonModule {
  readonly title: string;
  readonly lessons: readonly Lesson[];
}

/** The lessons this release ships. */
export const LESSONS: readonly LessonModule[] = [];
