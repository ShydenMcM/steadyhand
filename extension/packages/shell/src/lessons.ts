/** The lesson catalogue the Lessons tab renders (spec §13): modules in order, each with its
 * lessons in order. The lessons themselves are EXT S17's (#244); until then none ship. */

export interface Lesson {
  /** The lesson's key, such as `idx.lots`. */
  readonly id: string;
  readonly title: string;
  readonly summary: string;
  /** The lesson's text, a paragraph each, as plain text. */
  readonly paragraphs: readonly string[];
}

export interface LessonModule {
  readonly title: string;
  readonly lessons: readonly Lesson[];
}

/** The lessons this release ships. */
export const LESSONS: readonly LessonModule[] = [];
