import { expect, test } from "vitest";
import * as history from "../src/index.ts";
import * as market from "../src/market.ts";
import * as record from "../src/record.ts";
import * as risk from "../src/risk.ts";
import * as schema from "../src/schema.ts";

// The panel records each read and reads the record back through the package (#238).
test.each([
  ["openHistory", schema.openHistory],
  ["STORES", schema.STORES],
  ["rowsOf", record.rowsOf],
  ["recordCloses", record.recordCloses],
  ["recordSeries", record.recordSeries],
  ["recordDividends", record.recordDividends],
  ["recordCashMovements", record.recordCashMovements],
  ["recordCorporateActions", record.recordCorporateActions],
  ["remember", record.remember],
  ["storedMemory", record.storedMemory],
  ["putSetting", record.putSetting],
  ["recordValuation", risk.recordValuation],
  ["riskRecord", risk.riskRecord],
  ["amountOf", risk.amountOf],
  ["recordedCloses", market.recordedCloses],
  ["dividendRecord", market.dividendRecord],
  ["corporateActionRecord", market.corporateActionRecord],
  ["settingOf", market.settingOf],
])("history gives the panel %s", (name, source) => {
  expect(Object.entries(history)).toContainEqual([name, source]);
});
