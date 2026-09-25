# T-PAY: the IDX dividend pay lag, measured from KSEI schedules

**Ticket:** #27 (spec §12, T-PAY). **Researched and accessed:** 2026-09-25. **Feeds:** the pay-date model in spec §5 step 2 (`ex_date + pay_lag_trading_days`), the `[dividends]` config default, `dividend_pay_dates.csv`, and `income.py`'s reinvestment deadline (spec §6.2, `docs/research/t-tax.md` §3).

This is engineering research, not legal advice. Every date in the sample comes from a KSEI letter, and every rule from a regulation text, unless it is marked **unverified**. Quotes are verbatim in the original language.

## Sources

| Short name | Document | URL |
|---|---|---|
| **KSEI letters** | *Jadwal Pelaksanaan Pembagian Dividen*, one letter per dividend from PT Kustodian Sentral Efek Indonesia to its account holders (47 letters, listed in the Appendix) | `https://web.ksei.co.id/Announcement/Files/{TICKER}_DIV_{recording date YYYYMMDD}_ID.pdf` |
| **Holidays 2025** | Peng-00213/BEI.POP/10-2024, Kalender Libur Bursa Tahun 2025 (16 Oct 2024) | https://www.idx.co.id/StaticData/NewsAndAnnouncement/ANNOUNCEMENTSTOCK/Exchange/Libur%20Bursa%20Peng-00213-No.%20Peng-00213BEI.POP10-2024.pdf |
| **Holidays 2025 change** | Peng-00149/BEI.POP/08-2025, Perubahan Kalender Libur Bursa Tahun 2025 (8 Aug 2025) | https://www.idx.co.id/StaticData/NewsAndAnnouncement/ANNOUNCEMENTSTOCK/Exchange/Libur%20Bursa%20Peng-00149-No.%20Peng-00149BEI.POP08-2025.pdf |
| Holidays 2026 | Peng-00171/BEI.POP/09-2025 (already verified in `t-rules.md` §4) | see `t-rules.md` |
| **POJK 15/2020** | Peraturan OJK Nomor 15/POJK.04/2020 tentang Rencana dan Penyelenggaraan RUPS Perusahaan Terbuka (set 20 Apr 2020, promulgated 21 Apr 2020). BPK's database lists it as *Berlaku* (in force) with no amending or revoking regulation | https://peraturan.bpk.go.id/Details/143035/peraturan-ojk-no-15pojk042020-tahun-2020 |

**How the letters were found.** KSEI's schedule list (`/publications/corporate-action-schedules/cash-dividend`) shows only the most recent letters. Its month and year filter returned HTTP 500 for every query shape tried on 2026-09-25, so older letters were found by name instead. KSEI names each file after the ticker and the recording date, and the recording date is one trading day after the regular-market ex date, which Yahoo supplies. For each issuer, every Yahoo ex date in the window was probed at ex + 1 to ex + 7 calendar days, and all 47 resolved to a letter. The letters are served to plain `curl`, unlike idx.co.id. The IDX holiday announcements were read in a browser through the IDX announcement API, as `t-rules.md` describes.

## 1. The sample (AC1)

**Selection.** Eighteen large, long-listed dividend payers were chosen *before* any dates were looked at: ADRO, ASII, BBCA, BBNI, BBRI, BMRI, HMSP, ICBP, INDF, ITMG, JSMR, KLBF, PGAS, PTBA, SMGR, TLKM, UNTR and UNVR. **Every** cash dividend of theirs with a Yahoo ex date from 1 Jan 2025 to 25 Sep 2026 is included, so none was picked or dropped for its lag. That gives 47 dividends: 25 with an ex date in 2025 and 22 in 2026. KSEI titles 38 of them *Dividen Tunai* and 9 *Dividen Interim*.

**Controls that ran on every row.**
- The ex date printed in each letter equals the Yahoo ex date that located it: 47 of 47.
- On the IDX calendar, cum to ex is exactly 1 trading day and ex to recording is exactly 1 trading day (T+2 settlement): 47 of 47. This also checks the holiday calendar on 94 date pairs. BBNI's 2026 dividend is the hard case: cum 17 Mar, ex 25 Mar, with five holidays between them, and it counts as 1.
- Every payment date is an IDX trading day: 47 of 47.

**Limits.**
- The sample is large caps only. Smaller issuers may pay later, which the percentile chosen in §4 partly allows for.
- Completeness rests on Yahoo listing every dividend. A dividend missing from Yahoo is also missing from this sample.
- One payment date is still ahead of today: BMRI's interim is due on 2 Oct 2026. It is the date KSEI announced, not an observed payment.

The full sample, with every date and the source letter, is in the Appendix.

## 2. The lag in trading days (AC2)

Lag *n* means the payment date is the *n*th IDX trading day after the regular-market ex date, so `pay_date = ex_date + n trading days`. That is the quantity spec §5 needs. The trading days come from the IDX announcements: 25 holidays in 2025 (Peng-00213/10-2024 plus 18 Aug 2025 from Peng-00149/08-2025) and 22 in 2026 (Peng-00171/09-2025).

**2025** (Peng-00213/BEI.POP/10-2024 as changed by Peng-00149/BEI.POP/08-2025, 25 days): 01-01 · 01-27 · 01-28 · 01-29 · 03-28 · 03-31 · 04-01 · 04-02 · 04-03 · 04-04 · 04-07 · 04-18 · 05-01 · 05-12 · 05-13 · 05-29 · 05-30 · 06-06 · 06-09 · 06-27 · 08-18 · 09-05 · 12-25 · 12-26 · 12-31. Peng-00149 adds only 18 Aug: *"Bursa Menetapkan tanggal 18 Agustus 2025 sebagai Hari Libur Bursa, merevisi Pengumuman Bursa sebelumnya nomor Peng-00213/BEI.POP/10-2024"*. Its table gives *Jumlah Hari Bursa* 236, which is 261 weekdays less these 25. A search of the IDX announcement list on 2026-09-25 for "Libur Bursa", over July 2024 to 25 Sep 2026, found no other change to the 2025 or 2026 calendars. This extends `t-rules.md` §4, so M2's `holidays.toml` can carry 2025 as verified.

The 2025 list was cross-checked against Yahoo `^JKSE` daily bars, and the weekdays with no bar are exactly those 25 dates. The same check over 2026 up to 24 Sep found one weekday with no `^JKSE` bar, **22 Sep 2026**. That day is not an IDX holiday, and BBCA.JK and TLKM.JK both have bars for it. **Yahoo's index series has gaps, so it must never be used to derive the trading calendar.** This matters for M2's `holidays.toml`.

| Group | n | Min | Median | 75th pct | 90th pct | Max |
|---|---|---|---|---|---|---|
| **All** | 47 | **6** | **12** | 13 | **14** | **16** |
| *Dividen Tunai* | 38 | 6 | 12 | 13 | 14.3 | 16 |
| *Dividen Interim* | 9 | 6 | 10 | 12 | 13 | 13 |
| Ex date in 2025 | 25 | 6 | 11 | 13 | 13.6 | 15 |
| Ex date in 2026 | 22 | 6 | 12 | 12.75 | 14.8 | 16 |

Percentiles are Python's `statistics.quantiles(..., method="inclusive")`. The distribution of all 47 is: 6 ×3, 7 ×4, 8 ×3, 9 ×4, 10 ×4, 11 ×4, 12 ×9, 13 ×10, 14 ×2, 15 ×2, 16 ×2.

From recording date to payment the gap is 7 to 21 **calendar** days (median 15), or 5 to 15 trading days (median 11).

## 3. The rule on when a dividend is paid (AC3)

**No IDX or KSEI rule was found that fixes the gap between recording date and payment date.** The KSEI letters state the issuer's schedule and cite no rule for it. The rule that binds is OJK's, and it is anchored on the announcement of the RUPS minutes, not on the recording date.

POJK 15/2020 Pasal 58:

> Dalam hal terdapat keputusan RUPS terkait dengan pembagian dividen tunai, Perusahaan Terbuka wajib melaksanakan pembayaran dividen tunai kepada pemegang saham yang berhak paling lambat 30 (tiga puluh) hari setelah diumumkannya ringkasan risalah RUPS yang memutuskan pembagian dividen tunai.

POJK 15/2020 Pasal 51(2) sets when that announcement is made:

> Ringkasan risalah RUPS sebagaimana dimaksud dalam Pasal 49 ayat (1) wajib diumumkan kepada masyarakat paling lambat 2 (dua) hari kerja setelah RUPS diselenggarakan.

Pasal 51(1)(i) also requires the minutes summary to state *"pelaksanaan pembayaran dividen tunai kepada pemegang saham yang berhak"*, so the schedule is public from that announcement onward.

**What this means for the engine.**
- A dividend approved at a RUPS is paid within **30 days** of the minutes announcement, which comes at most 2 working days after the RUPS. Pasal 58 says *hari*, while the same regulation says *hari kerja* wherever it means working days (Pasal 51(2), Pasal 53), so the 30 are read as calendar days. That reading is an inference from the drafting, not a definition quoted from the text.
- The schedule, and so the recording date, is set in the RUPS decision that the minutes announce (Pasal 51(1)(i)), so the recording date comes after the RUPS and the rule caps recording to payment at roughly 30 calendar days or less. This is an inference, because the sample does not record RUPS dates. The sample's maximum is 21.
- Pasal 58 covers only dividends decided by a RUPS. An interim dividend is decided by the directors under UU 40/2007 Pasal 72. That article was not re-read for this ticket and is **unverified** here, so no timing rule is claimed for interim dividends. In the sample they were paid no later than the *Dividen Tunai* ones (maximum 13 trading days against 16).

## 4. The recommended default (AC4)

**Recommendation: `pay_lag_trading_days = 14`, the 90th percentile of the sample, not the median of 12.**

AC4's reasoning holds for the income figures. A modelled pay date later than the real one credits the cash later, so income and the cash available for reinvestment are understated, never overstated. At 14, the modelled date is on or after the real one for 43 of 47 dividends. The 4 exceptions are early by 1 or 2 trading days. At the median of 12, 16 of 47 would be credited early, which overstates. The maximum of 16 is never early in this sample, but it delays all 47 to suit the two slowest, and a sample maximum jumps with any single new slow payer, while the 90th percentile of 47 moves only when several do. **At 14, no modelled date is ever more than 2 trading days early** in this sample.

**That reasoning reverses for the reinvestment deadline, and the sample shows it.** The exemption deadline is 31 March of the year after the dividend is *received* (`t-tax.md` §3). A later modelled pay date can push a December payment into January, which moves the deadline a whole year later. That overstates the time the investor has. UNVR's interim dividend went ex on 15 Dec 2025 and was paid on 30 Dec 2025, which gives a real deadline of 31 Mar 2026. Its real lag was 9, and at any lag from 10 upward the model pays it in January 2026, which would make the deadline 31 Mar 2027.

So the engine should date the two things differently:
1. **Credit the cash** at `ex_date + 14` trading days, unless `dividend_pay_dates.csv` has a row for the dividend.
2. **Date the reinvestment deadline from the ex date's year**, unless an override row gives the real pay date. Payment is never before the ex date, so the ex date's year is never later than the real payment year, and the deadline is never later than the real one. When it is wrong, it is early, which is the safe direction: BBRI and ADRO went ex on 30 Dec 2025 and were paid on 15 Jan 2026, so their real deadline is 31 Mar 2027, and the rule gives 31 Mar 2026. Only a dividend that goes ex in December can be affected: in 2025, one with an ex date on or after 5 Dec, at the sample's maximum lag of 16. An override row fixes it exactly.

The switch that uses the deadline, `dividend_reinvestment_exemption`, is off by default, so rule 2 matters only when an operator turns it on. It still belongs in the M4 plan, because a deadline that is a year late is exactly the error the exemption's conservative reading exists to prevent.

## 5. What Yahoo `.JK` data exposes (AC5)

**Yahoo gives the ex date only. It has no payment date and no recording date.** Checked on 2026-09-25 with yfinance 1.7.0 (`uv run --no-project --with yfinance`) for BBCA.JK, TLKM.JK and BBRI.JK:
- `Ticker.dividends` is a series indexed by the **ex date**. Every one of the 47 sample dates equals the ex date in its KSEI letter.
- `Ticker.calendar` has `Ex-Dividend Date` and earnings fields only.
- `Ticker.info` has `exDividendDate` and `lastDividendDate` (both the ex date), plus rates and yields. There is no `dividendDate` key for these tickers.
- `Ticker.get_actions()` has only `Dividends` and `Stock Splits` columns.

So the default lag is the only source of a pay date unless the operator supplies one. **An override has to come from outside Yahoo**, and the KSEI letter is the natural source: it is public, curl-readable, named predictably, and gives every date on one page. A later ticket could fill `dividend_pay_dates.csv` from these letters automatically. That would be a new data source, which is the operator's decision, so it is not assumed here.

Yahoo's TLKM amounts are not whole Rupiah (223.16588 for the 2026 dividend). That may be the issuer's own figure (a total divided by the share count) or a Yahoo adjustment. The 2026 KSEI letter says the ratio *"akan diumumkan pada saat Recording Date"*, so it does not settle which. Amounts are out of T-PAY's scope, and this is noted for M4, which books them.

## 6. Verdict for the spec and M4

- Spec §5 step 2: the default `pay_lag_trading_days` is **14** (the 90th percentile of 47 KSEI-scheduled dividends, 2025–2026), counted on the IDX holiday calendar.
- Spec §6.2 / M4: the reinvestment deadline is dated from the ex date's year unless an override row gives the real pay date (§4 above).
- M2: never derive trading days from `^JKSE` bars (§2).
- M2: `holidays.toml` can carry 2025 as verified, from the list in §2.
- Spec §12: T-PAY is done.

## Appendix: the sample

Ex→pay counts IDX trading days after the ex date up to and including the payment date. Kind is KSEI's own title: *Dividen Tunai* (tunai) or *Dividen Interim* (interim).

| # | Issuer | Kind | Cum (regular) | Ex (regular) | Recording | Payment | Ex→pay (trading days) | Recording→pay (calendar days) | KSEI letter |
|---|---|---|---|---|---|---|---|---|---|
| 1 | ADRO | tunai | 2025-06-12 | 2025-06-13 | 2025-06-16 | 2025-06-26 | 9 | 10 | [KSEI-13946/JKU/0625](https://web.ksei.co.id/Announcement/Files/ADRO_DIV_20250616_ID.pdf) |
| 2 | ADRO | interim | 2025-12-29 | 2025-12-30 | 2026-01-02 | 2026-01-15 | 10 | 13 | [KSEI-30344/JKU/1225](https://web.ksei.co.id/Announcement/Files/ADRO_DIV_20260102_ID.pdf) |
| 3 | ADRO | tunai | 2026-04-27 | 2026-04-28 | 2026-04-29 | 2026-05-08 | 7 | 9 | [KSEI-8397/JKU/0426](https://web.ksei.co.id/Announcement/Files/ADRO_DIV_20260429_ID.pdf) |
| 4 | ASII | tunai | 2025-05-20 | 2025-05-21 | 2025-05-22 | 2025-06-05 | 9 | 14 | [KSEI-10779/JKU/0525](https://web.ksei.co.id/Announcement/Files/ASII_DIV_20250522_ID.pdf) |
| 5 | ASII | interim | 2025-10-13 | 2025-10-14 | 2025-10-15 | 2025-10-31 | 13 | 16 | [KSEI-24482/JKU/1025](https://web.ksei.co.id/Announcement/Files/ASII_DIV_20251015_ID.pdf) |
| 6 | ASII | tunai | 2026-05-04 | 2026-05-05 | 2026-05-06 | 2026-05-25 | 12 | 19 | [KSEI-8900/JKU/0426](https://web.ksei.co.id/Announcement/Files/ASII_DIV_20260506_ID.pdf) |
| 7 | BBCA | tunai | 2025-03-20 | 2025-03-21 | 2025-03-24 | 2025-04-11 | 8 | 18 | [KSEI-5529/JKU/0325](https://web.ksei.co.id/Announcement/Files/BBCA_DIV_20250324_ID.pdf) |
| 8 | BBCA | interim | 2025-12-02 | 2025-12-03 | 2025-12-04 | 2025-12-22 | 13 | 18 | [KSEI-28273/JKU/1125](https://web.ksei.co.id/Announcement/Files/BBCA_DIV_20251204_ID.pdf) |
| 9 | BBCA | tunai | 2026-03-27 | 2026-03-30 | 2026-03-31 | 2026-04-08 | 6 | 8 | [KSEI-5564/JKU/0326](https://web.ksei.co.id/Announcement/Files/BBCA_DIV_20260331_ID.pdf) |
| 10 | BBCA | interim | 2026-06-15 | 2026-06-17 | 2026-06-18 | 2026-06-26 | 7 | 8 | [KSEI-14083/JKU/0626](https://web.ksei.co.id/Announcement/Files/BBCA_DIV_20260618_ID.pdf) |
| 11 | BBCA | tunai | 2026-08-28 | 2026-08-31 | 2026-09-01 | 2026-09-16 | 12 | 15 | [KSEI-21461/JKU/0826](https://web.ksei.co.id/Announcement/Files/BBCA_DIV_20260901_ID.pdf) |
| 12 | BBNI | tunai | 2025-04-14 | 2025-04-15 | 2025-04-16 | 2025-04-25 | 7 | 9 | [KSEI-7436/JKU/0425](https://web.ksei.co.id/Announcement/Files/BBNI_DIV_20250416_ID.pdf) |
| 13 | BBNI | tunai | 2026-03-17 | 2026-03-25 | 2026-03-26 | 2026-04-07 | 8 | 12 | [KSEI-4933/JKU/0326](https://web.ksei.co.id/Announcement/Files/BBNI_DIV_20260326_ID.pdf) |
| 14 | BBRI | tunai | 2025-04-10 | 2025-04-11 | 2025-04-14 | 2025-04-23 | 7 | 9 | [KSEI-7222/JKU/0325](https://web.ksei.co.id/Announcement/Files/BBRI_DIV_20250414_ID.pdf) |
| 15 | BBRI | interim | 2025-12-29 | 2025-12-30 | 2026-01-02 | 2026-01-15 | 10 | 13 | [KSEI-30252/JKU/1225](https://web.ksei.co.id/Announcement/Files/BBRI_DIV_20260102_ID.pdf) |
| 16 | BBRI | tunai | 2026-04-20 | 2026-04-21 | 2026-04-22 | 2026-05-08 | 12 | 16 | [KSEI-7824/JKU/0426](https://web.ksei.co.id/Announcement/Files/BBRI_DIV_20260422_ID.pdf) |
| 17 | BMRI | tunai | 2025-04-11 | 2025-04-14 | 2025-04-15 | 2025-04-23 | 6 | 8 | [KSEI-7432/JKU/0425](https://web.ksei.co.id/Announcement/Files/BMRI_DIV_20250415_ID.pdf) |
| 18 | BMRI | interim | 2026-01-05 | 2026-01-06 | 2026-01-07 | 2026-01-14 | 6 | 7 | [KSEI-30599/JKU/1225](https://web.ksei.co.id/Announcement/Files/BMRI_DIV_20260107_ID.pdf) |
| 19 | BMRI | tunai | 2026-05-08 | 2026-05-11 | 2026-05-12 | 2026-05-25 | 8 | 13 | [KSEI-9756/JKU/0526](https://web.ksei.co.id/Announcement/Files/BMRI_DIV_20260512_ID.pdf) |
| 20 | BMRI | interim | 2026-09-15 | 2026-09-16 | 2026-09-17 | 2026-10-02 | 12 | 15 | [KSEI-22701/JKU/0926](https://web.ksei.co.id/Announcement/Files/BMRI_DIV_20260917_ID.pdf) |
| 21 | HMSP | tunai | 2025-06-10 | 2025-06-11 | 2025-06-12 | 2025-06-26 | 11 | 14 | [KSEI-12988/JKU/0625](https://web.ksei.co.id/Announcement/Files/HMSP_DIV_20250612_ID.pdf) |
| 22 | HMSP | tunai | 2026-05-26 | 2026-05-29 | 2026-06-02 | 2026-06-19 | 13 | 17 | [KSEI-11753/JKU/0526](https://web.ksei.co.id/Announcement/Files/HMSP_DIV_20260602_ID.pdf) |
| 23 | ICBP | tunai | 2025-07-01 | 2025-07-02 | 2025-07-03 | 2025-07-22 | 14 | 19 | [KSEI-16016/JKU/0625](https://web.ksei.co.id/Announcement/Files/ICBP_DIV_20250703_ID.pdf) |
| 24 | ICBP | tunai | 2026-07-06 | 2026-07-07 | 2026-07-08 | 2026-07-28 | 15 | 20 | [KSEI-17005/JKU/0726](https://web.ksei.co.id/Announcement/Files/ICBP_DIV_20260708_ID.pdf) |
| 25 | INDF | tunai | 2025-07-01 | 2025-07-02 | 2025-07-03 | 2025-07-23 | 15 | 20 | [KSEI-16012/JKU/0625](https://web.ksei.co.id/Announcement/Files/INDF_DIV_20250703_ID.pdf) |
| 26 | INDF | tunai | 2026-07-06 | 2026-07-07 | 2026-07-08 | 2026-07-29 | 16 | 21 | [KSEI-17008/JKU/0726](https://web.ksei.co.id/Announcement/Files/INDF_DIV_20260708_ID.pdf) |
| 27 | ITMG | tunai | 2025-04-17 | 2025-04-21 | 2025-04-22 | 2025-05-07 | 11 | 15 | [KSEI-7778/JKU/0425](https://web.ksei.co.id/Announcement/Files/ITMG_DIV_20250422_ID.pdf) |
| 28 | ITMG | interim | 2025-11-12 | 2025-11-13 | 2025-11-14 | 2025-11-26 | 9 | 12 | [KSEI-26591/JKU/1125](https://web.ksei.co.id/Announcement/Files/ITMG_DIV_20251114_ID.pdf) |
| 29 | ITMG | tunai | 2026-04-27 | 2026-04-28 | 2026-04-29 | 2026-05-19 | 12 | 20 | [KSEI-9054/JKU/0426](https://web.ksei.co.id/Announcement/Files/ITMG_DIV_20260429_ID.pdf) |
| 30 | JSMR | tunai | 2025-05-19 | 2025-05-20 | 2025-05-21 | 2025-06-05 | 10 | 15 | [KSEI-10781/JKU/0525](https://web.ksei.co.id/Announcement/Files/JSMR_DIV_20250521_ID.pdf) |
| 31 | JSMR | tunai | 2026-06-02 | 2026-06-03 | 2026-06-04 | 2026-06-19 | 11 | 15 | [KSEI-11937/JKU/0526](https://web.ksei.co.id/Announcement/Files/JSMR_DIV_20260604_ID.pdf) |
| 32 | KLBF | tunai | 2025-06-03 | 2025-06-04 | 2025-06-05 | 2025-06-25 | 13 | 20 | [KSEI-12274/JKU/0525](https://web.ksei.co.id/Announcement/Files/KLBF_DIV_20250605_ID.pdf) |
| 33 | KLBF | tunai | 2026-06-03 | 2026-06-04 | 2026-06-05 | 2026-06-24 | 13 | 19 | [KSEI-12356/JKU/0526](https://web.ksei.co.id/Announcement/Files/KLBF_DIV_20260605_ID.pdf) |
| 34 | PGAS | tunai | 2025-06-11 | 2025-06-12 | 2025-06-13 | 2025-07-02 | 13 | 19 | [KSEI-13242/JKU/0625](https://web.ksei.co.id/Announcement/Files/PGAS_DIV_20250613_ID.pdf) |
| 35 | PGAS | tunai | 2026-06-04 | 2026-06-05 | 2026-06-08 | 2026-06-24 | 12 | 16 | [KSEI-12360/JKU/0526](https://web.ksei.co.id/Announcement/Files/PGAS_DIV_20260608_ID.pdf) |
| 36 | PTBA | tunai | 2025-06-20 | 2025-06-23 | 2025-06-24 | 2025-07-11 | 13 | 17 | [KSEI-14629/JKU/0625](https://web.ksei.co.id/Announcement/Files/PTBA_DIV_20250624_ID.pdf) |
| 37 | PTBA | tunai | 2026-06-22 | 2026-06-23 | 2026-06-24 | 2026-07-10 | 13 | 16 | [KSEI-15056/JKU/0626](https://web.ksei.co.id/Announcement/Files/PTBA_DIV_20260624_ID.pdf) |
| 38 | SMGR | tunai | 2025-06-04 | 2025-06-05 | 2025-06-10 | 2025-06-26 | 13 | 16 | [KSEI-12789/JKU/0525](https://web.ksei.co.id/Announcement/Files/SMGR_DIV_20250610_ID.pdf) |
| 39 | SMGR | tunai | 2026-05-20 | 2026-05-21 | 2026-05-22 | 2026-06-11 | 12 | 20 | [KSEI-10934/JKU/0526](https://web.ksei.co.id/Announcement/Files/SMGR_DIV_20260522_ID.pdf) |
| 40 | TLKM | tunai | 2025-06-10 | 2025-06-11 | 2025-06-12 | 2025-07-02 | 14 | 20 | [KSEI-13234/JKU/0625](https://web.ksei.co.id/Announcement/Files/TLKM_DIV_20250612_ID.pdf) |
| 41 | TLKM | tunai | 2026-06-17 | 2026-06-18 | 2026-06-19 | 2026-07-10 | 16 | 21 | [KSEI-15047/JKU/0626](https://web.ksei.co.id/Announcement/Files/TLKM_DIV_20260619_ID.pdf) |
| 42 | UNTR | tunai | 2025-05-06 | 2025-05-07 | 2025-05-08 | 2025-05-28 | 13 | 20 | [KSEI-9637/JKU/0425](https://web.ksei.co.id/Announcement/Files/UNTR_DIV_20250508_ID.pdf) |
| 43 | UNTR | tunai | 2025-10-07 | 2025-10-08 | 2025-10-09 | 2025-10-24 | 12 | 15 | [KSEI-23718/JKU/0925](https://web.ksei.co.id/Announcement/Files/UNTR_DIV_20251009_ID.pdf) |
| 44 | UNTR | tunai | 2026-04-24 | 2026-04-27 | 2026-04-28 | 2026-05-18 | 12 | 20 | [KSEI-8521/JKU/0426](https://web.ksei.co.id/Announcement/Files/UNTR_DIV_20260428_ID.pdf) |
| 45 | UNVR | tunai | 2025-06-13 | 2025-06-16 | 2025-06-17 | 2025-07-02 | 11 | 15 | [KSEI-13822/JKU/0625](https://web.ksei.co.id/Announcement/Files/UNVR_DIV_20250617_ID.pdf) |
| 46 | UNVR | interim | 2025-12-12 | 2025-12-15 | 2025-12-16 | 2025-12-30 | 9 | 14 | [KSEI-29171/JKU/1225](https://web.ksei.co.id/Announcement/Files/UNVR_DIV_20251216_ID.pdf) |
| 47 | UNVR | tunai | 2026-06-12 | 2026-06-15 | 2026-06-17 | 2026-06-30 | 10 | 13 | [KSEI-14068/JKU/0626](https://web.ksei.co.id/Announcement/Files/UNVR_DIV_20260617_ID.pdf) |

## Review log

- **Pass 1 (2026-09-25):** mechanical checks: every number in the text and every one of the 47 table rows was recomputed from the parsed letters (0 mismatches); every AC (1–5) maps to a section (§1 and the Appendix AC1; §2 AC2; §3 AC3; §4 AC4; §5 AC5); every cross-reference (`t-tax.md` §3, `t-rules.md` §4, spec §5, §6.2, §9.2, §9.5) exists. Year-boundary and early-credit claims were recomputed, and two were wrong and fixed: UNVR's December dividend crosses into January from a lag of 10, not 11, and the affected December window starts on 5 Dec. Then a full read, with 4 findings, all fixed: (1) the doc called Yahoo's fractional TLKM amounts "therefore adjusted", which nothing showed; (2) "final" was used where KSEI's title is *Dividen Tunai*, which also covers non-final dividends; (3) the case against the maximum rested on an unexplained "less sensitive to outliers"; (4) spec §5 said a lag at or above the typical one never credits early, but 4 of 47 are early at 14.
- **Pass 2 (2026-09-25):** mechanical: a script located all 5 quoted fragments in their source texts (POJK 15/2020, the TLKM letter, the Peng-00149 text), and its negative control (a 45-day version of Pasal 58) was correctly reported missing. Full read: 1 finding, fixed: the new wording claimed the 90th percentile does not move with a new slow payer, which overstates it.
- **Pass 3 (2026-09-25):** mechanical checks re-run (47 rows, 0 mismatches; 5 of 5 quotes found, negative control missing), then a full read. 1 finding, fixed: §3 said the recording date "always" falls inside Pasal 58's 30-day window, which the sample cannot show without RUPS dates; it is now marked as an inference.
- **Pass 4 (2026-09-25):** mechanical checks re-run after the Pass 3 fix (47 rows, 0 mismatches; 5 of 5 quotes found, negative control missing), then a read of the whole text, which had changed since Pass 3's read only in the §3 bullet. **0 findings. Loop closed.**
