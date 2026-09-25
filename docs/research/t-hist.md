# T-HIST: IDX holidays 2016–2024 and the older trading rules

**Ticket:** #37 (spec §12, T-HIST). **Researched:** 2026-09-25. **Feeds:** M2 (`data/holidays.toml`, `data/tick_sizes.toml`, `data/auto_reject.toml`).

This is engineering research, not legal advice. Every value comes from an IDX document unless it is marked **unverified**. Quotes are verbatim in the original language.

**Source order (Shyden, 2026-09-25).** The Internet Archive came first. idx.co.id was used only for documents the Archive does not hold in a readable copy; those rows say so under "Obtained".

## Sources

| Short name | Document | Issued | In force | Obtained |
|---|---|---|---|---|
| **Holidays 2016** | IDX, *Kalender Libur Bursa Tahun 2016* (PDF) | — | — | Archive, capture 20190917224753 of `idx.co.id/Portals/0/StaticData/NewsAndAnnouncement/TradingHoliday/2016.pdf` |
| **Holidays 2017** | IDX, *Kalender Libur Bursa Tahun 2017* (PDF) | — | — | Archive, 20170713123347 of `…/TradingHoliday/2017.pdf` |
| **Holidays 2018** | IDX, *Kalender Libur Bursa Tahun 2018* (image `2018ind.jpg`) | — | — | Archive, 20220307151816 of `idx.co.id/media/3054/2018ind.jpg` |
| **Holidays 2019** | IDX, *Kalender Libur Bursa Tahun 2019*, revised (`2019_rev.jpg`) | — | — | Archive, 20220307151816 of `idx.co.id/media/7181/2019_rev.jpg` |
| **Holidays 2020** | IDX, *Kalender Libur Bursa Tahun 2020*, version 3 (`2020_ind-v3.jpg`) | — | — | Archive, 20221007193429 of `idx.co.id/media/9396/2020_ind-v3.jpg` |
| **Holidays 2021** | IDX, *Kalender Libur Bursa Tahun 2021*, version 3 (`2021_ind-v3.jpg`) | — | — | Archive, 20221008133601 of `idx.co.id/media/9940/2021_ind-v3.jpg` |
| **Holidays 2022** | IDX, *Kalender Libur Bursa Tahun 2022*, version 2 (`2022_ind-v2.jpg`) | — | — | **idx.co.id**, `https://www.idx.co.id/media/10969/2022_ind-v2.jpg`, accessed 2026-09-25. The Archive indexes captures of it (20220610153228, 20221008000523) but returns 404 on replay |
| **Holidays 2023** | IDX, *Kalender Libur Bursa Tahun 2023*, version 3 (`2023_ind-v3_page-0001.jpg`) | — | — | **idx.co.id**, `https://www.idx.co.id/media/ivwpbnxq/2023_ind-v3_page-0001.jpg`, accessed 2026-09-25. No Archive capture exists |
| **Holidays 2024** | IDX, *Kalender Libur Bursa Tahun 2024*, version 3 (`2024_ind-v3_new.jpg`) | — | — | Archive, 20250830095302 of `idx.co.id/media/13tdjyy0/2024_ind-v3_new.jpg` |
| Holiday index | IDX `GetTradingHolidays` (JSON listing the calendar images for 2020–2025) | — | — | Archive, 20250830095302 of `idx.co.id/primary/AboutUs/GetTradingHolidays?lang=id` |
| **Peng-00504** | Peng-00504/BEI.OPP/06-2018, *Kegiatan Operasional Bursa Efek Indonesia pada Tanggal 27 Juni 2018* | 25 Jun 2018 | 27 Jun 2018 (the day it concerns) | Archive, 20180712200104 of `idx.co.id/media/2549/20180625_pengumuman-kegiatan-operasional-bei-27-juni-2018.pdf` (a scan, read as an image) |
| **Kep-00025** | Kep-00025/BEI/03-2020, *Perubahan Peraturan Nomor II-A tentang Perdagangan Efek Bersifat Ekuitas*, with II-A in full as its attachment | 12 Mar 2020 | 13 Mar 2020 | **idx.co.id**, `https://www.idx.co.id/media/8318/perubahan-peraturan-nomor-ii-a-tentang-perdagangan-efek.pdf`, accessed 2026-09-25, text read with pdf.js. The Archive's only capture (20210302224609) is cut off at exactly 1 MiB of a 2.2 MB file |
| Rules index 2020 | IDX `GetRegulationItem?nodeId=1520` (the trading-rules list as of June 2020, naming Kep-00025 as the current II-A) | — | — | Archive, 20200610055648 |
| **AR 2017** | IDX, *Laporan Tahunan dan Laporan Keuangan 2017* | 2018 | — | Archive, 20250914211553 of `idx.co.id/Media/5649/idx-ar-dan-lk-2017.pdf` |
| **AR 2023** | IDX, *Laporan Tahunan 2023* | 2024 | — | Archive, 20250912002616 of `idx.co.id/Media/njadghvc/ar-bei-2023.pdf` |
| AR 2024 | IDX, *Laporan Tahunan 2024* (`ar-bei-2024-20250710-final.pdf`) | 2025 | — | Archive, 20250910074631 |

The Yahoo checks used yfinance 1.7.0 (`uv run --no-project --with yfinance==1.7.0`) on 2026-09-25.

## 1. Holidays 2016–2024 (AC2)

Each list is the IDX calendar's final version for the year: a later version replaces an earlier one where IDX revised the calendar during the year (2019 `_rev`; 2020 went through `rev-1` to `v3`; 2021 `ver02` to `v3`; 2022 `v2`). Every calendar ends with a *Jumlah Hari Bursa* (number of trading days). A script recomputed that total as the year's weekdays minus the listed dates, and it matches the stated total in every year. No listed date falls on a weekend, and none is listed twice. The calendar images carry no announcement number of their own, so each year's source is named by its file and version.

Dates below are day-month, as in `t-rules.md` §4. The legal basis is the government's joint decree (SKB) on national holidays and collective leave that each calendar cites.

| Year | Holidays | Trading days (stated = recomputed) | Calendar's legal basis, as it states |
|---|---|---|---|
| 2016 | 15 | 246 | SKB 150/2015, 2/SKB/MEN/VI/2015, 01/2015 |
| 2017 | 22 | 238 | SKB 684/2016, 302/2016, SKB/02/MENPAN-RB/11/2016 (an amendment) |
| 2018 | 21 | 240 | SKB 223/2018, 46/2018, 13/2018, amending SKB 707/2017, 256/2017, 01/SKB/MENPANRB/09/2017 |
| 2019 | 16 | 245 | SKB 617/2018, 262/2018, 16/2018 |
| 2020 | 20 | 242 | SKB 744/2020, 05/2020, 06/2020 of 1 Dec 2020 (fourth amendment of SKB 728/2019, 213/2019, 01/2019) |
| 2021 | 14 | 247 | SKB 712/2021, 1/2021, 3/2021 of 18 Jun 2021 (second amendment of SKB 642/2020, 4/2020, 4/2020) |
| 2022 | 14 | 246 | SKB 375/2022, 1/2022, 1/2022 of 7 Apr 2022, amending SKB 963/2021, 3/2021, 4/2021 |
| 2023 | 21 | 239 | none stated |
| 2024 | 25 | 237 | none stated |

**2016:** 01-01 · 08-02 · 09-03 · 25-03 · 05-05 · 06-05 · 04-07 · 05-07 · 06-07 · 07-07 · 08-07 · 17-08 · 12-09 · 12-12 · 26-12.

**2017:** 02-01 · 15-02 · 28-03 · 14-04 · 19-04 · 24-04 · 01-05 · 11-05 · 25-05 · 01-06 · 23-06 · 26-06 · 27-06 · 28-06 · 29-06 · 30-06 · 17-08 · 01-09 · 21-09 · 01-12 · 25-12 · 26-12.

**2018:** 01-01 · 16-02 · 30-03 · 01-05 · 10-05 · 29-05 · 01-06 · 11-06 · 12-06 · 13-06 · 14-06 · 15-06 · 18-06 · 19-06 · 17-08 · 22-08 · 11-09 · 20-11 · 24-12 · 25-12 · 31-12.

**2019:** 01-01 · 05-02 · 07-03 · 03-04 · 17-04 · 19-04 · 01-05 · 30-05 · 03-06 · 04-06 · 05-06 · 06-06 · 07-06 · 24-12 · 25-12 · 31-12.

**2020:** 01-01 · 25-03 · 10-04 · 01-05 · 07-05 · 21-05 · 22-05 · 25-05 · 01-06 · 31-07 · 17-08 · 20-08 · 21-08 · 28-10 · 29-10 · 30-10 · 09-12 · 24-12 · 25-12 · 31-12.

**2021:** 01-01 · 12-02 · 11-03 · 02-04 · 12-05 · 13-05 · 14-05 · 26-05 · 01-06 · 20-07 · 11-08 · 17-08 · 20-10 · 31-12.

**2022:** 01-02 · 28-02 · 03-03 · 15-04 · 29-04 · 02-05 · 03-05 · 04-05 · 05-05 · 06-05 · 16-05 · 26-05 · 01-06 · 17-08.

**2023:** 23-01 · 22-03 · 23-03 · 07-04 · 19-04 · 20-04 · 21-04 · 24-04 · 25-04 · 01-05 · 18-05 · 01-06 · 02-06 · 28-06 · 29-06 · 30-06 · 19-07 · 17-08 · 28-09 · 25-12 · 26-12.

**2024:** 01-01 · 08-02 · 09-02 · 14-02 · 11-03 · 12-03 · 29-03 · 08-04 · 09-04 · 10-04 · 11-04 · 12-04 · 15-04 · 01-05 · 09-05 · 10-05 · 23-05 · 24-05 · 17-06 · 18-06 · 16-09 · 27-11 · 25-12 · 26-12 · 31-12.

**Revisions that matter.** The first 2022 calendar (`2022_ind.jpg`, 250 trading days) did not have the Eid collective leave of **29 Apr and 4–6 May 2022**. Version 2 adds them after the government's joint decree of 7 Apr 2022 (SKB 375/2022, 1/2022, 1/2022) and states 246. Using the first version would put four trading days into the calendar that never traded.

**27 June 2018 was a trading day.** It was a regional-election day, and a national holiday was declared for it. Peng-00504/BEI.OPP/06-2018 settles it: *"tanggal 27 Juni 2018 Bursa tetap beroperasi secara normal dan pada tanggal tersebut dinyatakan sebagai Hari Bursa."* The 2018 calendar does not list it, and Yahoo has bars for it.

## 2. Cross-check against Yahoo (AC6)

Five LQ45 stocks (BBCA.JK, BBRI.JK, TLKM.JK, ASII.JK, BMRI.JK) were read from Yahoo for 2016-01-01 to 2024-12-31. A weekday counts as **closed** when none of the five has a bar with volume above zero.

- **Every listed holiday is closed.** Not one of the 168 dates in §1 has trading in any of the five.
- **Every closed weekday is listed, except 16 days** in 2016–2018, all of them Yahoo defects: 2016-03-11, 03-14, 04-11, 04-13, 04-14, 04-15, 04-18, 04-19; 2017-04-05; 2018-04-16, 04-17, 04-19, 04-20, 04-25, 04-26, 04-27. On each of them `^JKSE` has a bar and INDF.JK traded on most, so IDX was open. IDX's own stated totals also count them as trading days.
- **Those gaps are placeholder rows, not missing rows.** Yahoo fills them with a flat bar at the previous close and volume 0. BBCA.JK on 2016-04-13 to 04-19 reads open = high = low = close = 2,610, volume 0. Over 2016–2024, each of the five stocks has 66–68 zero-volume rows: 50 on IDX holidays, none on weekends, and 16–18 on trading days.
- Three weekdays show some of the five trading and some not (2019-06-19, 2020-03-13, 2020-03-16). These are stock-level gaps, not market closures, and 13 Mar 2020 is also the day Kep-00025 took effect.

## 3. Tick table from 2016 (AC3)

**Verified from 13 Mar 2020.** The II-A attached to Kep-00025 has the same five tiers as today (`t-rules.md` §1), set by the *Harga Previous*: VI.5.2 *"… Harga Previous kurang dari Rp200,- … fraksi sebesar Rp1 …"*, then Rp2 from Rp200, Rp5 from Rp500, Rp10 from Rp2.000, and *"… Harga Previous Rp5.000,- (lima ribu rupiah) atau lebih, ditetapkan fraksi sebesar Rp25,- …"*. The round lot is 100 (VI.4.2). The II-A it amends is Kep-00168/BEI/11-2018 of 22 Nov 2018, whose own text was not found.

**2 May 2016 to 12 Mar 2020: five tiers, unverified but supported by data.** No IDX decision was found (the news reports name Kep-00023/BEI/04-2016). The Yahoo prices of the 23 sampled stocks with no split since 1 Jan 2015 were tested against both tables: a price that is legal under the old three-tier table but not under the five-tier one (for example 2,015, or 301) can only trade before the change.
- Such prices appear up to **29 Apr 2016** (1,922 open, high, low or close values from June 2015 on), and then once on 2 May 2016 (ELSA's opening print of 493). None appears after that.
- No whole-rupiah price from May 2016 to December 2020 breaks the five-tier table.

**6 Jan 2014 to 1 May 2016: three tiers, unverified.** IDX's own 2017 annual report lists *"6 JANUARI 2014 Penyesuaian Jumlah Lot & Fraksi Harga"* in its milestones, which dates a tick change but does not give the values. The values in `t-rules.md` §1 (1 below Rp500, 5 from Rp500, 25 from Rp5,000) come from the news, and every whole-rupiah sampled price from June 2015 to April 2016 fits them.

Some Yahoo prices are not whole rupiah even for stocks with no split (ANTM and SMGR among the 23), so Yahoo also adjusts for events it does not report as splits. Those rows were left out of the tick test (§6 carries this to M2).

## 4. Auto-rejection bands and minimum price from 2016 (AC4)

| Effective from | Down band (all tiers) | Up band by tier (Rp50–200 / >200–5,000 / >5,000) | Minimum price | Status |
|---|---|---|---|---|
| before 9 Mar 2020 | 35 / 25 / 20 (symmetric), by the news | 35 / 25 / 20 | Rp50 | **unverified**; no IDX text found |
| 9 Mar 2020 (Kep-00023/BEI/03-2020) | 10% | 35 / 25 / 20 | Rp50 | **verified values, unverified start**: Kep-00025 quotes Kep-00023's text and gives its date, *"tanggal 9 Maret 2020"*, but not the day it took effect (the news says 10 Mar 2020) |
| **13 Mar 2020** (Kep-00025) | **7%** | 35 / 25 / 20 | Rp50 | verified |
| 7 Dec 2020 onwards | as `t-rules.md` §3 | | | verified there |

The text of Kep-00025, *Memutuskan* 1, replaces Kep-00023's *"lebih dari 35% … di atas atau 10% (sepuluh perseratus) di bawah acuan Harga untuk saham dengan rentang harga Rp50 … sampai dengan Rp200"* (and the 25/10 and 20/10 tiers) with *"lebih dari 35% … di atas atau 7% (tujuh perseratus) di bawah acuan Harga …"* (and 25/7, 20/7). VI.7.1.1 rejects any price *"lebih kecil dari Rp50"*. *Memutuskan* 2 also cuts the first-day IPO band from twice the normal percentage to once, and item 4 revokes Kep-00023.

The 7% down band ran until the 2023 normalisation. IDX's 2023 annual report confirms the steps in `t-rules.md` §3: *"pada 5 Juni 2023 ditetapkan menjadi 15% untuk seluruh rentang harga, sementara itu ditetapkan batasan Auto Rejection Simetris sesuai dengan rentang harga masing–masing sejak 4 September 2023."*

**The bands cannot be read back from Yahoo.** A down band of X% against the opening price keeps every low at or above (1 − X%) × the open. Yet lows more than 7% below the open appear on 20 Mar and 8 Apr 2020 (LPKR, BSDE), when the band was verifiably 7%. Yahoo's open is not always IDX's *Acuan Harga*: a stock with no pre-opening price is referenced to its previous close (§5).

## 5. The auto-rejection reference price (AC5)

| Period | Reference | Status |
|---|---|---|
| before 13 Mar 2020 | not found | **unverified** |
| **13 Mar 2020** onwards | *"Harga Pembukaan di Pasar Reguler"* (VI.7.3.1); *"Harga Previous apabila Harga Pembukaan tidak terbentuk"* (VI.7.3.2); the theoretical price after a corporate action; the IPO price | verified (Kep-00025 attachment) |
| 3 Apr 2023 | opening price, previous close as fallback | verified (II-A 2023, `t-rules.md` §3) |
| **9 Dec 2024** onwards | *Harga Previous* (the previous close) | verified (II-A 2025, which re-issues Kep-00196/BEI/12-2024, in force 9 Dec 2024; `t-rules.md` §3) |

**The switch lies between 3 Apr 2023 and 9 Dec 2024. It was not narrowed.** IDX's 2024 annual report names two II-A changes in 2024: *"perubahan Peraturan II-A dan II-P Perluasan Saham Pre-Opening"* (widening the set of stocks in the pre-opening auction), and the amendment *"yang diberlakukan pada tanggal 9 Desember 2024"*. Neither text was found, and IDX's announcement feed does not carry rule decisions (a search of it for 2023-07 to 2024-12 returned no rule decision).

## 6. Verdict for M2

| Data | Verified from | Unverified before |
|---|---|---|
| Holidays | **2016** (every year 2016–2027 now comes from an IDX calendar) | 2015 and earlier (not researched) |
| Tick table | 13 Mar 2020 | 2 May 2016 – 12 Mar 2020 five tiers (supported by Yahoo prices); 6 Jan 2014 – 1 May 2016 three tiers (date from IDX's annual report, values from the news, consistent with Yahoo) |
| Auto-rejection bands | 13 Mar 2020 | the 10% band's start (9 or 10 Mar 2020); everything before 9 Mar 2020 |
| Minimum price | 9 Mar 2020 (Rp50) | before 9 Mar 2020 |
| Reference price | 13 Mar 2020 (opening price) and 9 Dec 2024 (previous close) | before 13 Mar 2020; the switch between 3 Apr 2023 and 9 Dec 2024 |

**Open for the M2 plan** (decisions, not research gaps):
1. The acceptance backtest (spec §14 AC1) starts on 2016-01-01. Holidays now cover it. Ticks and bands are primary-verified only from 13 Mar 2020. The plan must decide between refusing a backtest before that date, or shipping the older rows marked unverified with the backtest report saying so.
2. The reference price matters to the band itself, so to both the "impossible data" check (spec §5 step 1), which compares close-to-close moves with the band, and to rejecting a fill outside the band (§5.1). With the opening price as reference, a genuine close can sit further from the previous close than the band, so over the untraced 2023–2024 window the check must not assume the previous close.
3. **Yahoo's zero-volume placeholder rows.** On 16–18 trading days in 2016–2024, each sampled stock has a flat bar at the previous close with volume 0 while the market traded. The spec (§5, §5.1) reads zero volume as "the stock did not trade" and rejects orders that day. The data source must decide whether a flat zero-volume bar is data or a gap.
4. **Yahoo's prices are adjusted even with `auto_adjust=False`.** BBCA.JK's 2016 bars read about 2,610: divided by 5 for its 5-for-1 split of 13 Oct 2021 (Yahoo's own split record), where the unadjusted price was about 13,050, and some stocks carry fractional prices from adjustments that are not listed as splits. Spec §4.3 needs **unadjusted** prices, so the data source must reverse the adjustments, and must detect the ones it cannot explain.

## Review log

- **Pass 1 (2026-09-25):** a full read against #37's AC1–AC8. Eight findings, all fixed. (1) The sources table had no in-force column, which AC1 asks for. (2) AC2 asks for the announcement behind each date, and the doc did not say the calendar images carry no number of their own. (3) §3 said the three-tier prices appear "on every month" up to April 2016, which the script never checked; it knows only the first and last. (4) §3 called 1,922 open, high, low and close values "prices". (5) §3's "no price breaks the five-tier table" had silently left out 14,700 non-integer values, so it now says whole-rupiah. (6) §4 called 11 Mar 2020 "verifiably 7%", but the 7% band began on 13 Mar; the examples are now 20 Mar and 8 Apr. (7) §6 said the reference price matters only to the impossible-data check, but fill rejection (spec §5.1) uses the band too. (8) The BBCA split was cited from memory; Yahoo's split record now dates it (13 Oct 2021, 5-for-1).
- **Pass 2 (2026-09-25):** mechanical. The holiday table and lists are generated from the transcription by a script that re-asserts each year's weekday arithmetic, and the counts in the prose (168 dates, 16 gap days, 66–68 and 16–18 placeholder rows, 23 stocks, 1,922 values) match the script outputs. Every Kep and Peng number cited was listed: the two in the sources table were read, and the four outside it are each flagged where they appear (Kep-00023/BEI/03-2020 read through Kep-00025's quotation, Kep-00023/BEI/04-2016 news only, Kep-00168/BEI/11-2018 not found, Kep-00196/BEI/12-2024 via `t-rules.md`). **0 findings.**
- **Pass 3 (2026-09-25):** a reread of every line changed by pass 1. Two findings, both fixed: §4 opened with a 10% band and then argued from 7%; and §6 item 4 gave "traded near 13,000" as if it were independent evidence, when it is 2,610 × 5.
- **Pass 4 (2026-09-25):** a reread of the two lines pass 3 changed, and of the spec text this ticket edits (§9.1, §12, Appendix A, Pass 10). **0 findings. Loop closed.**
