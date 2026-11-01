/** "Forget everything" (spec §6.1, §11): delete the history database and the extension's storage,
 * then read both back, so the user is told it is gone only when it is. */

import { DATABASE, failure } from "./schema.ts";

/** The extension's own storage, as `chrome.storage.local` gives it. */
export interface ExtensionStorage {
  get(keys: null): Promise<Record<string, unknown>>;
  clear(): Promise<void>;
}

const deleted = (factory: IDBFactory): Promise<void> =>
  new Promise((resolve, reject) => {
    const request = factory.deleteDatabase(DATABASE);
    request.onsuccess = () => {
      resolve();
    };
    request.onerror = () => {
      reject(failure(request.error, `deleting ${DATABASE}`));
    };
  });

/** Close `db`, delete the database and clear `storage`; refuse, naming what is left, unless
 * both read back empty. */
export const forgetEverything = async (
  factory: IDBFactory,
  db: IDBDatabase,
  storage: ExtensionStorage,
): Promise<void> => {
  db.close();
  await deleted(factory);
  await storage.clear();
  if ((await factory.databases()).some((found) => found.name === DATABASE)) {
    throw new Error(`forget everything left the database ${DATABASE} in place`);
  }
  const left = Object.keys(await storage.get(null));
  if (left.length > 0) {
    throw new Error(`forget everything left the extension's storage holding: ${left.join(", ")}`);
  }
};
