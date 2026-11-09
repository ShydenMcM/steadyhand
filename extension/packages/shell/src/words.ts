/** The panel's words in English and Indonesian (#251 AC1): every string the panel writes, by
 * key. A `{name}` in a text is a slot `fill` puts a value in; both languages have the same
 * slots. The language names are each in their own language and are not translated. */

import { CHOICE_LINE, DISCLAIMER } from "./advice-view.ts";

/** The languages the panel speaks, each named in its own language. */
export const LANGUAGES = [
  ["en", "English"],
  ["id", "Bahasa Indonesia"],
] as const;
export type Language = (typeof LANGUAGES)[number][0];

const ENGLISH = {
  tabAdvice: "Advice",
  tabSettings: "Settings",
  tabHistory: "History",
  tabLessons: "Lessons",
  disclaimer: DISCLAIMER,
  choiceLine: CHOICE_LINE,

  read: "Read this page",
  resumeLabel: "Type the strategy's name to resume buying",
  resume: "Resume",
  pasteLabel: "Or paste a broker page you saved",
  readPaste: "Read the pasted page",
  importLabel: "Or open a broker page you saved",
  answerNone: "No deposits or withdrawals since {day}",

  languageLabel: "Language",
  saveLanguage: "Save language",
  strategyLabel: "Strategy",
  saveStrategy: "Save strategy",
  goalLabel: "Monthly income goal, in rupiah",
  saveGoal: "Save goal",
  limitMaxWeight: "The largest share of one stock, in percent",
  limitMinLots: "The smallest buy, in lots",
  limitDailyLoss: "The one-day fall that halts ordering, in percent",
  limitMaxDrawdown: "The fall from the high that halts ordering, in percent",
  saveLimits: "Save risk limits",
  presetLabel: "Broker fee preset",
  savePreset: "Save fee preset",
  deposit: "Deposit",
  withdrawal: "Withdrawal",
  movementKindLabel: "Deposit or withdrawal",
  movementDayLabel: "Day, such as 2025-06-16",
  movementAmountLabel: "Amount, in rupiah",
  addMovement: "Keep this deposit or withdrawal",
  noMovements: "No deposits or withdrawals typed.",
  depositLine: "{day}: deposit of {amount}",
  withdrawalLine: "{day}: withdrawal of {amount}",
  universeLabel: "Universe: the stocks to choose from",
  saveUniverse: "Save universe",
  exclusionsLabel: "Excluded stocks: one per line, the code and then your reason",
  saveExclusions: "Save exclusions",

  recordingNote: "steadyhand records a broker page only while this panel is open beside it.",
  nothingRecorded: "Nothing is recorded yet.",
  stockLine: "{symbol}: {days} recorded, {chartReads}, {dividends}",
  dayOne: "{count} day",
  dayMany: "{count} days",
  chartReadOne: "{count} chart read",
  chartReadMany: "{count} chart reads",
  dividendOne: "{count} dividend",
  dividendMany: "{count} dividends",
  forget: "Forget everything",
  forgetWarning:
    "This deletes everything steadyhand has recorded and every setting. It cannot be undone.",
  forgetYes: "Yes, forget everything",
  forgetKeep: "Keep everything",

  noLessons: "The lessons come in a later release.",

  notABrokerTab: "This tab shows no broker page steadyhand reads.",
  pageNotRead: "This page was not read: {reason}",
  pageRead: "Read {page}.",
  pagePortfolio: "the portfolio page",
  pageWatchlist: "the watchlist page",
  pageFlags: "the flags page",
  pageCashMovements: "the cash movement page",
  pageCorporateActions: "the corporate action page",
  pageDividends: "the dividend page",
  pageStockDetail: "the stock's page",
  nothingPasted: "Nothing is pasted.",
  noFileChosen: "No file was chosen.",
  answeredNone: "Kept: no deposits or withdrawals since {day}.",
  notResumed: "Not resumed: {reason}",
  resumed: "Buying resumed: {strategy}.",
  universeNotSaved: 'Universe not saved: "{code}" is not a four-letter IDX stock code.',
  universeSaved: "Universe saved: {count} stocks.",
  strategyNotSaved: "Strategy not saved: {reason}",
  strategySaved: "Strategy saved: {strategy}.",
  goalCleared: "Income goal cleared.",
  goalSaved: "Income goal saved.",
  goalNotSaved: 'Income goal not saved: type whole rupiah, such as 5.000.000, got "{typed}"',
  limitsNotSaved: "Risk limits not saved: {reason}",
  limitsSaved: "Risk limits saved.",
  presetSaved: "Fee preset saved: {preset}.",
  dayNotKept: 'Not kept: type the day as a date such as 2025-06-16, got "{typed}"',
  amountNotKept: 'Not kept: type whole rupiah above 0, such as 1.000.000, got "{typed}"',
  depositKept: "Deposit of {amount} on {day} kept.",
  withdrawalKept: "Withdrawal of {amount} on {day} kept.",
  exclusionsNotCode: 'Exclusions not saved: "{code}" is not a four-letter IDX stock code.',
  exclusionsTwice: "Exclusions not saved: {symbol} is listed twice.",
  exclusionsSavedOne: "Exclusions saved: {count} stock.",
  exclusionsSavedMany: "Exclusions saved: {count} stocks.",
  forgotten: "Everything is forgotten.",
  wentWrong: "Something went wrong: {failure}",
  languageSaved: "Language saved.",
  languageRefused: "The kept language is not one steadyhand has; English is shown.",
} as const;

export type Words = Readonly<Record<keyof typeof ENGLISH, string>>;

const INDONESIAN: Words = {
  tabAdvice: "Saran",
  tabSettings: "Pengaturan",
  tabHistory: "Riwayat",
  tabLessons: "Pelajaran",
  disclaimer:
    "steadyhand adalah perangkat lunak contoh yang Anda jalankan sendiri, di akun Anda sendiri, " +
    "dan keputusan yang Anda buat dengannya adalah keputusan Anda sendiri. Ini bukan nasihat " +
    "keuangan. Anda bisa kehilangan uang.",
  choiceLine:
    "steadyhand menghitung apa yang tersirat dari strategi yang Anda pilih; pilihan dan " +
    "semua pesanannya adalah milik Anda",

  read: "Baca halaman ini",
  resumeLabel: "Ketik nama strategi untuk melanjutkan pembelian",
  resume: "Lanjutkan",
  pasteLabel: "Atau tempel halaman broker yang Anda simpan",
  readPaste: "Baca halaman yang ditempel",
  importLabel: "Atau buka halaman broker yang Anda simpan",
  answerNone: "Tidak ada setoran atau penarikan sejak {day}",

  languageLabel: "Bahasa",
  saveLanguage: "Simpan bahasa",
  strategyLabel: "Strategi",
  saveStrategy: "Simpan strategi",
  goalLabel: "Target pendapatan bulanan, dalam rupiah",
  saveGoal: "Simpan target",
  limitMaxWeight: "Porsi terbesar untuk satu saham, dalam persen",
  limitMinLots: "Pembelian terkecil, dalam lot",
  limitDailyLoss: "Penurunan dalam satu hari yang menghentikan order, dalam persen",
  limitMaxDrawdown: "Penurunan dari titik tertinggi yang menghentikan order, dalam persen",
  saveLimits: "Simpan batas risiko",
  presetLabel: "Preset biaya broker",
  savePreset: "Simpan preset biaya",
  deposit: "Setoran",
  withdrawal: "Penarikan",
  movementKindLabel: "Setoran atau penarikan",
  movementDayLabel: "Tanggal, misalnya 2025-06-16",
  movementAmountLabel: "Jumlah, dalam rupiah",
  addMovement: "Catat setoran atau penarikan ini",
  noMovements: "Belum ada setoran atau penarikan yang diketik.",
  depositLine: "{day}: setoran sebesar {amount}",
  withdrawalLine: "{day}: penarikan sebesar {amount}",
  universeLabel: "Semesta: saham-saham yang boleh dipilih",
  saveUniverse: "Simpan semesta",
  exclusionsLabel: "Saham yang dikecualikan: satu per baris, kodenya lalu alasan Anda",
  saveExclusions: "Simpan pengecualian",

  recordingNote: "steadyhand hanya mencatat halaman broker selama panel ini terbuka di sampingnya.",
  nothingRecorded: "Belum ada yang tercatat.",
  stockLine: "{symbol}: {days} tercatat, {chartReads}, {dividends}",
  dayOne: "{count} hari",
  dayMany: "{count} hari",
  chartReadOne: "{count} pembacaan grafik",
  chartReadMany: "{count} pembacaan grafik",
  dividendOne: "{count} dividen",
  dividendMany: "{count} dividen",
  forget: "Lupakan semuanya",
  forgetWarning:
    "Ini menghapus semua yang telah dicatat steadyhand dan setiap pengaturan. Tindakan ini " +
    "tidak dapat dibatalkan.",
  forgetYes: "Ya, lupakan semuanya",
  forgetKeep: "Pertahankan semuanya",

  noLessons: "Pelajaran hadir di rilis berikutnya.",

  notABrokerTab: "Tab ini tidak menampilkan halaman broker yang dibaca steadyhand.",
  pageNotRead: "Halaman ini tidak dibaca: {reason}",
  pageRead: "Sudah membaca {page}.",
  pagePortfolio: "halaman portofolio",
  pageWatchlist: "halaman daftar pantauan",
  pageFlags: "halaman notasi khusus",
  pageCashMovements: "halaman mutasi kas",
  pageCorporateActions: "halaman aksi korporasi",
  pageDividends: "halaman dividen",
  pageStockDetail: "halaman saham tersebut",
  nothingPasted: "Belum ada yang ditempel.",
  noFileChosen: "Tidak ada berkas yang dipilih.",
  answeredNone: "Tercatat: tidak ada setoran atau penarikan sejak {day}.",
  notResumed: "Tidak dilanjutkan: {reason}",
  resumed: "Pembelian dilanjutkan: {strategy}.",
  universeNotSaved: 'Semesta tidak disimpan: "{code}" bukan kode saham BEI empat huruf.',
  universeSaved: "Semesta disimpan: {count} saham.",
  strategyNotSaved: "Strategi tidak disimpan: {reason}",
  strategySaved: "Strategi disimpan: {strategy}.",
  goalCleared: "Target pendapatan dihapus.",
  goalSaved: "Target pendapatan disimpan.",
  goalNotSaved:
    'Target pendapatan tidak disimpan: ketik rupiah bulat, misalnya 5.000.000; Anda mengetik "{typed}"',
  limitsNotSaved: "Batas risiko tidak disimpan: {reason}",
  limitsSaved: "Batas risiko disimpan.",
  presetSaved: "Preset biaya disimpan: {preset}.",
  dayNotKept: 'Tidak disimpan: ketik tanggal seperti 2025-06-16; Anda mengetik "{typed}"',
  amountNotKept:
    'Tidak disimpan: ketik rupiah bulat di atas 0, misalnya 1.000.000; Anda mengetik "{typed}"',
  depositKept: "Setoran sebesar {amount} pada {day} dicatat.",
  withdrawalKept: "Penarikan sebesar {amount} pada {day} dicatat.",
  exclusionsNotCode: 'Pengecualian tidak disimpan: "{code}" bukan kode saham BEI empat huruf.',
  exclusionsTwice: "Pengecualian tidak disimpan: {symbol} tercantum dua kali.",
  exclusionsSavedOne: "Pengecualian disimpan: {count} saham.",
  exclusionsSavedMany: "Pengecualian disimpan: {count} saham.",
  forgotten: "Semuanya sudah dilupakan.",
  wentWrong: "Terjadi kesalahan: {failure}",
  languageSaved: "Bahasa disimpan.",
  languageRefused:
    "Bahasa yang tersimpan bukan bahasa yang dimiliki steadyhand; yang ditampilkan bahasa Inggris.",
};

export const WORDS: Readonly<Record<Language, Words>> = { en: ENGLISH, id: INDONESIAN };

const SLOT = /\{(\w+)\}/gu;

/** The slots in `text`, each once, sorted. */
export const slotsOf = (text: string): readonly string[] =>
  [...new Set([...text.matchAll(SLOT)].flatMap((match) => match.slice(1, 2)))].sort();

/** `text` with each slot filled from `values`; a slot with no value, or a value for no slot,
 * is refused by name. */
export const fill = (text: string, values: Readonly<Record<string, string>>): string => {
  const slots = slotsOf(text);
  const unused = Object.keys(values).find((name) => !slots.includes(name));
  if (unused !== undefined) {
    throw new Error(`the text has no slot {${unused}}`);
  }
  return text.replaceAll(SLOT, (slot, name: string) => {
    const value = values[name];
    if (value === undefined) {
      throw new Error(`the text has a slot ${slot} with no value`);
    }
    return value;
  });
};

/** Words that read the same in every language: the product's name, codes in capitals, numbers
 * and dates, and slots. */
const SAME_IN_EVERY_LANGUAGE = /^(?:steadyhand|[A-Z]{2,}|[\d.,:-]+|\{\w+\})$/u;

/** Whether `text` may read the same in Indonesian as in English: every word in it is one that
 * reads the same in every language (the derived list, #251 AC2). */
export const identicalAllowed = (text: string): boolean => {
  const words = text.split(/[\s:,;]+/u).filter((word) => word !== "");
  return words.length > 0 && words.every((word) => SAME_IN_EVERY_LANGUAGE.test(word));
};
