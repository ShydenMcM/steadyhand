// Measurement-only (#282, throwaway branch): the extension's config plus the probe setup file.
import base from "./vitest.config.ts";

export default { ...base, test: { ...base.test, setupFiles: ["./measure-282.setup.ts"] } };
