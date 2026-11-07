/** A lesson's Markdown file, bundled as its text (#244): esbuild's text loader in the build, and
 * the same transform in the test run. */
declare module "*.md" {
  const text: string;
  export default text;
}
