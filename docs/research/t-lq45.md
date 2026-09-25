# T-LQ45: dated LQ45 membership, and whether steadyhand may ship it

**Ticket:** #26 (spec §12, T-LQ45). **Researched and accessed:** 2026-09-25. **Feeds:** the universe in spec §9.4, `universe.py`, and how far back the AC1 backtest (2016–2025) can run without a survivorship-bias warning.

This is engineering research, not legal advice. Every list below was read from an IDX document, and every legal point from a primary text, unless it is marked **inferred** or **unverified**. Quotes are verbatim in the original language.

## Sources

| Short name | Document | URL |
|---|---|---|
| **Review announcements, 2024–2026** | *Evaluasi Indeks IDX30, LQ45, IDX80, KOMPAS100, …*, one IDX announcement per review (11, listed in §3) | Search: `https://www.idx.co.id/id/berita/pengumuman/` (keyword `LQ45`). Files: `https://www.idx.co.id/StaticData/NewsAndAnnouncement/ANNOUNCEMENTSTOCK/Exchange/<file>`, e.g. `…/Exchange/Evaluasi%20Indeks%2027%20Jul%202026%20.Ind-No.%20Peng-00148BEI.POP07-2026.pdf` |
| **Review announcements, 2004–2018** | *Saham (Emiten) yang Masuk (dan Keluar) dalam Penghitungan Indeks LQ45*, the same announcement in its older form, one per half-year | IDX no longer serves them. Internet Archive copies of IDX's own files at `idx.co.id/Portals/0/StaticData/MarketInformation/ListOfSecurities/IndexConstituent/LQ45/<file>`, e.g. `https://web.archive.org/web/20211215181746/https://www.idx.co.id//portals/0/StaticData/MarketInformation/ListOfSecurities/IndexConstituent/LQ45/20160125_LQ45_Feb-Juli16.pdf` |
| **Fact-sheet booklets** | IDX Data Services Division, *IDX Company Fact Sheet LQ45* / *IDX LQ45* (one per half-year). The contents page lists the 45 constituents "in Period of" the half-year | Internet Archive copies of `idx.co.id/media/…` and `idx.co.id/Portals/0/StaticData/Publication/LQ45/…`. 14 found: Feb and Aug 2013, 2014 and 2018, Aug 2019, Feb and Aug 2020, Feb 2022, Aug 2023, Feb and Aug 2024, Feb 2025. Those in the 2016–2025 window are cited in §3 |
| **Mid-period replacement** | Peng-383/BEJ-DAG/U/10-2004: IDKM enters, IDSR leaves, from 4 Oct 2004 | `https://web.archive.org/web/20211021022119/https://www.idx.co.id/Portals/0/StaticData/MarketInformation/ListOfSecurities/IndexConstituent/LQ45/2004_LQ45_Aug04-Jan05.pdf` |
| **IDX Terms of Use** | *Syarat Penggunaan*, idx.co.id | `https://www.idx.co.id/id/syarat-penggunaan/` |
| **UU 28/2014** | Undang-Undang Nomor 28 Tahun 2014 tentang Hak Cipta. BPK lists it as *Berlaku* (in force) | `https://peraturan.bpk.go.id/Details/38690/uu-no-28-tahun-2014` (PDF `…/Download/28018/UU%20Nomor%2028%20Tahun%202014.pdf`) |

**How the sources were found.**
- **IDX's announcement search starts in July 2023.** Its API (`/primary/NewsAnnouncement/GetAllAnnouncement`) returned 6,287 items with an empty keyword for 1–28 July 2023. It returned 0 for each of January, March, May and June 2023 (the months tried), and 0 for each of 2017, 2019, 2021 and 2022. A keyword search for `LQ45` from 2015 finds nothing before 29 Dec 2023. The site's statistics archive offers only 2023–2026.
- **Older files came from the Internet Archive.** One CDX query for PDFs on `idx.co.id` with `lq45` in the URL found 70 distinct files. 57 of them were downloaded and parsed: the review announcements, the booklets and the monthly fact sheets. The rest are methodology guides, an ETF report and the separate IDX LQ45 Low Carbon Leaders index. A second query, for PDFs captured in 2019–2024 with `evaluasi`, `indeks`, `index`, `idx30`, `idx80` or `konstituen` in the name, found no LQ45 review announcement from 2019 to 2023.
- **Most 2007–2018 announcements are scans with no text layer.** They were read with the macOS Vision OCR engine.
- **Method caveat, for Shyden.** IDX's Terms of Use (quoted in §5) say *"tidak diperkenankan menggunakan metode web scrapping/crawling"*. This research sent about 45 scripted requests to IDX's announcement API and PDF paths from a browser session. T-RULES and T-PAY used the same technique. It stopped as soon as the clause was read. Whether it continues is Shyden's decision.

## 1. Where dated membership can be sourced (AC1)

IDX publishes each LQ45 review as an announcement. It carries the full list of 45 codes in force for the coming period, not only the changes. Each row has a status: *Tetap* (unchanged) or *Baru* (new). The 2026 announcements also give free-float and weight columns, marked *Naik*/*Turun* (up/down), and a separate table of the stocks leaving, *Konstituen yang keluar dari penghitungan indeks*. The 2024–2025 layouts were parsed for codes only.

- **2024 onward:** the announcement is titled *Evaluasi Indeks IDX30, LQ45, …*. Page 1 gives each index's review type (*Mayor*/*Minor*) and effective period. The LQ45 list is in its own appendix (*Lampiran*). The PDF sometimes comes inside a `.zip` (January and April 2024).
- **2004–2018:** the announcement is titled *Saham (Emiten) yang Masuk (dan Keluar) dalam Penghitungan Indeks LQ45*. The full list follows the cover letter; in 2016 it is on pages 2–3 under *Daftar Saham yang Masuk dalam Penghitungan Indeks LQ45, Periode …*.
- **Mid-period replacements** are separate announcements. In Peng-383/BEJ-DAG/U/10-2004, IDSR left and IDKM entered *"sejak tanggal 4 Oktober 2004"*, following IDKM's listing and IDSR's delisting (Peng-438/BEJ-PSR/P/10-2004). So membership can change between reviews. Only this one replacement was found, by chance, and **none were searched for systematically**.
- **The fact-sheet booklets** are an IDX publication but not an announcement. They list the constituents "in Period of" a half-year. Where a booklet and an announcement cover the same period, the lists are identical: 3 of 3 (Feb–Jul 2024, Aug 2024–Jan 2025 and Feb–Jul 2025). The 2013–2014 and 2018 booklets also match their OCR'd announcements, apart from the OCR errors listed in §3.
- **Not a source:** the monthly index fact sheets (`fs-lq45-YYYY-MM.pdf`) show the top 10 constituents only.

**Cadence.** Until January 2024, reviews were semi-annual, taking effect in February and August. From the April 2024 review they are quarterly, taking effect in February, May, August and November, and every LQ45 review since then is labelled *Mayor*. The January 2024 announcement set an effective period of *"1 Februari s.d. 31 Juli 2024"*. The April 2024 review replaced that list from 2 May 2024, so the stated end date did not hold. Two announcements titled *Penyesuaian Kriteria Evaluasi Indeks IDX30, LQ45 …* (adjusting the evaluation criteria) were also published: Peng-00058/BEI.POP/03-2024 (27 Mar 2024, between the January and April 2024 reviews) and Peng-00065/BEI.POP/04-2026 (21 Apr 2026). **Their contents were not read.**

## 2. The earliest list, and the gaps (AC2)

**The earliest primary list found is for February–July 2004:** Peng-08/BEJ-DAG/U/01-2004, dated 29 January 2004. It has a text layer and an appendix numbered to row 45, with a status column. The text layer splits letters apart, and 43 rows parsed cleanly. The index goes back further: the announcements checked (2004 and 2016–2018) cite *"Peng-114/BEJ.I/U/1997 tanggal 6 Februari 1997"* on the *"Indeks Likuiditas Bursa Efek Jakarta (Indeks LQ45)"*. That it set up the index is **inferred** from that title. **No list was found for 1997–2003.**

**Gaps between February 2004 and the latest review (effective 3 Aug 2026):**

| Review period | What was found |
|---|---|
| Aug 2004 – Jan 2005 | Only the 4 Oct 2004 replacement. The review it amends (Peng-317/BEJ-DAG/U/07-2004, 27 Jul 2004) was not found |
| Feb 2019 – Jul 2019 | Nothing |
| Feb 2021 – Jul 2021 | Nothing |
| Aug 2021 – Jan 2022 | Nothing |
| Aug 2022 – Jan 2023 | Nothing |
| Feb 2023 – Jul 2023 | Nothing |
| Every period | Mid-period replacements were not searched for (§1) |

Every other half-year from February 2004 to January 2024 has an archived announcement or booklet, and every quarter since then has an IDX announcement. Reviews from 2004 to 2015 were checked for completeness only: each archived announcement is numbered to row 45. They were not transcribed or cross-checked.

## 3. The review periods covering 2016–2025 (AC3)

Before 2024, the sources name the **month** a list takes effect, not the day. Its effective date is the first IDX trading day of that month (**inferred**; the announcements say *"periode perdagangan Februari sampai dengan Juli 2016"*). From 2024 the announcements give the exact day. "Announced" is the letter date, or for archived announcements the date in the file name. The two agreed where checked (25 Jan 2016). The OCR reads the division code *BEI* as *BEL*; the numbers below are corrected.

| Effective from | Primary list found? | Source (archive capture) | 45 codes read |
|---|---|---|---|
| Feb 2016 | Yes | Peng-00021/BEI.OPP/01-2016, 25 Jan 2016 (`20211215181746`) | 45 (OCR) |
| Aug 2016 | Yes | Peng-00671/BEI.OPP/07-2016, 27 Jul 2016 (`20180623005112`) | 45 (OCR) |
| Feb 2017 | Yes | Peng-00025/BEI.OPP/01-2017, 26 Jan 2017 (`20210507230610`) | 45 (OCR) |
| Aug 2017 | Yes | Peng-00728/BEI.OPP/07-2017, 24 Jul 2017 (`20220121192327`) | 44 (OCR; one row read as `ПCВP`, i.e. ICBP) |
| Feb 2018 | Yes | Peng-00028/BEI.OPP/01-2018, 25 Jan 2018 (`20180219111330`, a copy on `yuknabungsaham.idx.co.id`); booklet *IDX LQ45 February 2018* (`20180623005137`) | 45, both |
| Aug 2018 | Yes | Peng-00696/BEI.OPP/07-2018, 26 Jul 2018 (`20180920222057`); booklet *IDX LQ45 August 2018* (`20180920094819`) | 45, both |
| Feb 2019 | **No** | — | — |
| Aug 2019 | Yes, booklet only | *IDX LQ45 August 2019* company profiles (`20210614191119`). The cover says "August 2019"; the period is **inferred** | 45 |
| Feb 2020 | Yes, booklet only | *IDX Company Fact Sheet LQ45, February – July 2020* (`20260712200247`) | 45 |
| Aug 2020 | Yes, booklet only | *… LQ45, August 2020 – January 2021* (`20260712195632`) | 45 |
| Feb 2021 | **No** | — | — |
| Aug 2021 | **No** | — | — |
| Feb 2022 | Yes, booklet only | *… LQ45, February – July 2022* (`20260712200845`) | 45 |
| Aug 2022 | **No** | — | — |
| Feb 2023 | **No** | — | — |
| Aug 2023 | Yes, booklet only | *… LQ45, August 2023 – January 2024* (`20260712201024`) | 45 |
| 1 Feb 2024 | Yes | Peng-00020/BEI.POP/01-2024, 25 Jan 2024; booklet Feb–Jul 2024 (`20240901165608`) | 45, identical |
| 2 May 2024 | Yes | Peng-00078/BEI.POP/04-2024, 24 Apr 2024 | 45 |
| 1 Aug 2024 | Yes | Peng-00163/BEI.POP/07-2024, 25 Jul 2024; booklet Aug 2024–Jan 2025 (`20260712201244`) | 45, identical |
| 1 Nov 2024 | Yes | Peng-00220/BEI.POP/10-2024, published 27 Oct 2024 | 45 |
| 3 Feb 2025 | Yes | Peng-00012/BEI.POP/01-2025, 22 Jan 2025; booklet Feb–Jul 2025 (`20260712201348`) | 45, identical |
| 2 May 2025 | Yes | Peng-00073/BEI.POP/04-2025, 24 Apr 2025 | 45 |
| 1 Aug 2025 | Yes | Peng-00139/BEI.POP/07-2025, 25 Jul 2025 | 45 |
| 3 Nov 2025 | Yes | Peng-00198/BEI.POP/10-2025, 27 Oct 2025 | 45 |

Outside the window, 2026 has three more: 2 Feb (Peng-00014/BEI.POP/01-2026), 4 May (Peng-00067/BEI.POP/04-2026) and 3 Aug (Peng-00148/BEI.POP/07-2026). Each yields 45 codes.

**Controls.**
- **Every list from 2024 on** has 45 unique codes numbered 1–45.
- **The extractor finds what it is pointed at.** Pointed at IDX30 in the July 2026 announcement, it returns 30 codes, all inside the LQ45 list.
- **The changes match IDX's own tables.** The diff between consecutive lists matches the announcement's new (*Baru*) and leaving tables for July 2026: +INDY +NCKL, −SMGR −TOWR.
- **Every booklet list** is 45 unique codes in alphabetical order, as IDX prints them.

**The OCR is not good enough to transcribe from without a check.** Against the booklets for the same periods, the OCR misread 2 codes in each of February and August 2018 and still produced 45 unique codes. The misreads were BJBR→BJBK, INDF→INDE, PTPP→PIPP and TPIA→TPLA. In August 2013 it dropped BWPT. A count of 45 therefore does not validate an OCR'd list. Transcription must check each code against a second source. In this window the booklet is that source from February 2018 on; the four lists from 2016–2017 have no booklet, so each code needs a check against the scan by eye.

**What this means for AC1's backtest.** 19 of the 24 reviews taking effect in 2016–2025 have a primary list. The five gaps fall in 2019–2023. A 2016–2025 backtest therefore cannot use a gap-free survivorship-free universe from these sources alone. The per-date lookup in §4 carries the last known list across a gap, and that must be reported as a gap, not treated as the true membership.

## 4. The file format (AC4)

**Recommendation: one TOML record per IDX document, each carrying the full list in force from its effective date.** Membership on a date *d* is the list of the latest record whose `effective` is on or before *d*. There is no `to_date`: a record ends where the next begins, so two records cannot overlap or leave a hole by accident.

```toml
# lq45_members.toml: IDX LQ45 membership, one record per IDX document.
# Lists shortened here; the loader rejects a record without exactly 45 codes.
schema = 1

[[record]]
effective = 2026-05-04              # first trading day the list applies
announced = 2026-04-24
source = "Peng-00067/BEI.POP/04-2026"
kind = "review"                     # "review" or "replacement"
members = ["AADI", "ADMR", "ADRO", "SMGR", "TOWR"]

[[record]]
effective = 2026-08-03
announced = 2026-07-27
source = "Peng-00148/BEI.POP/07-2026"
kind = "review"
members = ["AADI", "ADMR", "ADRO", "INDY", "NCKL"]
```

**Why this shape:**
- **A full list per record checks itself.** The count must be 45, and each record maps one-to-one to the document cited in `source`. A change-only format would silently carry an early error into every later period.
- **Replacements use the same shape.** A mid-period replacement becomes a full `kind = "replacement"` record, so lookup stays a single rule.
- **The loader validates:** `effective` strictly increasing; exactly 45 unique codes of four capital letters; a non-empty `source`; `announced` on or before `effective`.
- **Gaps are visible.** A gap is a pair of consecutive records more than one review apart: 6 months before May 2024, 3 months after. The survivorship warning in spec §9.4 fires for a backtest that starts before the first record, *or that spans a gap*.

This replaces spec §9.4's `lq45_membership.csv` with (ticker, from_date, to_date) columns. §5 says why the file is supplied by the user rather than shipped.

## 5. Licensing (AC5)

**Position: steadyhand must not reproduce the lists in the Apache-2.0 repository. Each user supplies their own file.**

- **IDX's Terms of Use forbid commercial redistribution without permission.** *"Pengguna dilarang menggunakan atau menyebarluaskan Informasi dan atau data yang diperoleh dari Website kepada pihak lain untuk tujuan komersial tanpa izin tertulis terlebih dahulu dari Bursa Efek Indonesia"* (users may not use or pass on information or data from the website to others for a commercial purpose without IDX's prior written permission). Non-commercial use, including quoting, is allowed *"dengan menyebutkan sumbernya secara lengkap yang disertai tanggal akses"* (with the full source and the access date). Apache-2.0 grants every recipient the right to use and redistribute the Work, commercially included. So a list committed under it would pass on rights steadyhand does not hold.
- **The lists are probably a protected compilation.** UU 28/2014 Pasal 41 huruf b does not protect bare data (*"setiap ide, prosedur, sistem, metode, konsep, prinsip, temuan atau data"*). A single stock code is data. But Pasal 40 ayat (1) protects a *"basis data"* (huruf n) and a *"kompilasi Ciptaan atau data"* (huruf p). The elucidation of huruf n defines a *basis data* as a compilation *"yang karena alasan pemilihan atau pengaturan atas isi data itu merupakan kreasi intelektual"* (which, because of the selection or arrangement of its contents, is an intellectual creation). The LQ45 is a selection made by IDX's methodology. That makes a list plausibly protected, although no court ruling on index constituents was looked for. Pasal 42's list of works without copyright covers state bodies' meetings, legislation, state speeches, court rulings and scripture. IDX is a company, and its announcements are none of these.
- **The archive copies do not change who owns any copyright.** Whether the Terms, which bind *"data yang diperoleh dari Website"*, also reach a copy obtained from the Internet Archive is **unclear**. It changes nothing here: copyright does not depend on where the copy came from, and the 2024 onward lists come from the website itself.

**Consequences for M2/M3.**
- Ship the format, the loader, its validation and the gap warning. Ship no membership data. Tests use a synthetic file.
- **A built-in downloader would likely count as the scraping the Terms forbid.** So an importer, if one is built, reads PDFs the user saved themselves and never fetches from idx.co.id.
- Tell the user where each document is (§1, §3), and that the Terms require the source and access date when a list is quoted.
- **Alternative: ask IDX for written permission.** The booklets give IDX Data Services' contact as `idxdata@idx.co.id`. With permission, the lists could ship under a separate data licence, not Apache-2.0. Asking is Shyden's decision, and nothing in this ticket depends on it.

## 6. Not done under this ticket (AC6)

No membership was transcribed into any data file. The lists parsed during this research stayed in the session scratchpad, which is not in the repository.

## 7. Verdict for the spec

- **§9.4:** `lq45_membership.csv` becomes a user-supplied `lq45_members.toml` in the format of §4, outside the repository and not packaged.
- **The survivorship warning** covers gaps as well as the start date.
- **§4's package-data list** drops the file.
- **§9.5** gains `[universe] lq45_members`, the path to the user's file.
- **§12** marks T-LQ45 done.

These changes are made in the spec as Pass 9.

## Review log

- **Pass 1 (2026-09-25):** mechanical checks, then a full read. The checks: every AC (1–6) has a section; §3 has 24 rows (16 semi-annual periods, Feb 2016 to Aug 2023, then 8 quarterly ones); the TOML example parses with `tomllib` (2 records); the booklet count (14) and the 13 archive files not downloaded reconcile with the CDX listing. 10 findings, all fixed: (1) the backtest count read "17 of 23 … six gaps", and it is 19 of 24 with five gaps, because the draft counted 12 semi-annual periods; (2) the replacement's archive link was a wildcard, and it is now the exact capture `20211021022119`; (3) the Sources table said the 14 booklets were listed in §3, and §3 cites only those in the window, so the table now names all 14; (4) the July 2023 control covered 1–28 July, not the whole month; (5) "57 are review announcements or booklets" left out the monthly fact sheets that were also downloaded; (6) the scripted-request count was about 45, not about 20; (7) "from its trading operations and research divisions" held only for the 2016 signatories and was dropped; (8) the two criteria announcements' titles were paraphrased, and they are now quoted; (9) "every older announcement cites Peng-114/1997" rested on the 7 files checked, and now says so; (10) the elucidation quoted in §5 belongs to Pasal 40(1)(n), *basis data*, not to huruf p, and "row 18" in the Aug 2017 row was a guess and was removed.
- **Pass 2 (2026-09-25):** full read after the fixes. 9 findings, all fixed, each a sentence claiming more than was checked: (1) "since 2024" for the weight columns and leaving table, which were read in 2026 only; (2) "pages 2–3" for every older announcement, checked for 2016 only; (3) "after a delisting" for the 2004 replacement, which was a listing plus a delisting; (4) "45 numbered rows" for the 2004 list, of which 43 parsed; (5) the same wording for 2004–2015, which were checked only for numbering up to 45; (6) "IDX's list of stocks listed on that date" as a second source, which was not looked for, now replaced by what exists (booklets from Feb 2018, by-eye checks before); (7) "§9.4" in §4 was ambiguous between this doc and the spec; (8) Apache-2.0 licenses the Work, not only "the software"; (9) "would be the scraping" overstated a reading of the Terms, now "would likely count as". The spec changes of §7 were made as spec Pass 9, and the spec's §9.5 TOML block still parses.
- **Pass 3 (2026-09-25):** full read. 7 findings, all fixed: (1) the 2026 criteria announcement is not "in between" the 2024 reviews; (2) that Peng-114/1997 set up the index is inferred from its title, and is now marked so; (3) the empty-month control covered January, March, May and June 2023, not "January–June"; (4) the second archive query filtered on capture dates, not publication years; (5) the Feb 2018 row gave only the booklet's capture, not the announcement's; (6) the Aug 2018 booklet had no capture; (7) §7 did not list the new `[universe]` key or the §12 change that spec Pass 9 made.
- **Pass 4 (2026-09-25):** full read. 1 finding, fixed: the booklets cited for Feb 2024, Aug 2024 and Feb 2025 had no archive capture, unlike every other booklet row. A check of all 17 distinct capture timestamps in the doc against the CDX listing finds 17 of 17.
- **Pass 5 (2026-09-25):** full read of §4–§7. 1 finding, fixed: §5 said the Terms bind the archive copies, but they bind data obtained from the website; that reach is now marked unclear, and the position is shown not to depend on it.
- **Pass 6 (2026-09-25):** full read of the whole document, checking each claim against the session's extraction output: counts (11 announcements, 14 booklets, 24 periods, 19 found, 5 gaps), every Peng number and date in §3, every capture, and every quote against its source text. **0 findings. Loop closed.**
