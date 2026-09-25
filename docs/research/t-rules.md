# T-RULES: IDX market rules from primary documents

**Ticket:** #24 (spec §12, T-RULES). **Researched:** 2026-09-25. **Feeds:** M2 (`rules.py`, `data/tick_sizes.toml`, `data/auto_reject.toml`, `data/holidays.toml`, `data/sessions.toml`).

This is engineering research, not legal advice. Every value below comes from an IDX document unless it is marked **unverified**. Quotes are verbatim in the original language. idx.co.id refuses scripted downloads (HTTP 403), so the documents were opened in a browser and their text was extracted with pdf.js. They were accessed on 2026-09-25.

## Sources

| Short name | Document | Issued | In force | URL |
|---|---|---|---|---|
| **II-A 2026** | Kep-00136/BEI/09-2026, Perubahan Peraturan Nomor II-A tentang Perdagangan Efek Bersifat Ekuitas | 21 Sep 2026 | **28 Sep 2026** | https://www.idx.co.id/Media/bgqhucr0/signed_perubahan_peraturan_nomor-_ii_a__tentang_perdagangan_efek_bersifat_ekuitas.pdf |
| **II-A 2025** | Kep-00003/BEI/04-2025, Peraturan Nomor II-A (re-issues Kep-00196/BEI/12-2024 of 6 Dec 2024, in force 9 Dec 2024) | 8 Apr 2025 | 8 Apr 2025 to 27 Sep 2026 | https://www.idx.co.id/Media/mrekbmz3/signed_peraturan_ii_a_perdagangan_efek_bersifat_ekuitas.pdf |
| II-A 2023 | Kep-00055/BEI/03-2023 | 30 Mar 2023 | 3 Apr 2023 | https://www.idx.co.id/Media/y0vjxqur/signed_peraturan_ii_a_perdagangan_efek_bersifat_ekuitas.pdf |
| II-A 2021 | Kep-00061/BEI/07-2021 | 23 Jul 2021 | 26 Jul 2021 | https://www.idx.co.id/media/10022/peraturan_ii_a_perdagangan_efek_bersifat_ekuitas.pdf |
| II-A 2020 | Kep-00108/BEI/12-2020, Perubahan Peraturan Nomor II-A | 4 Dec 2020 | 7 Dec 2020 | https://www.idx.co.id/media/9410/perubahan_peraturan_ii_a_perdagangan_efek_bersifat_ekuitas.pdf |
| **Holidays 2026** | Peng-00171/BEI.POP/09-2025, Kalender Libur Bursa Tahun 2026 | 23 Sep 2025 | | https://www.idx.co.id/StaticData/NewsAndAnnouncement/ANNOUNCEMENTSTOCK/Exchange/Peng-00171%20Libur%20Bursa%202026-No.%20Peng-00171BEI.POP09-2025.pdf |
| **Holidays 2027** | Peng-00169/BEI.POP/09-2026, Trading Holiday Calendar of 2027 | 16 Sep 2026 | | https://www.idx.co.id/StaticData/NewsAndAnnouncement/ANNOUNCEMENTSTOCK/Exchange/Libur%20Bursa%20Peng-00169%20ENG-No.%20Peng-00169BEI.POP09-2026.pdf |
| Holidays 2027 fix | Peng-00171/BEI.POP/09-2026, a correction to one description only | 17 Sep 2026 | | https://www.idx.co.id/StaticData/NewsAndAnnouncement/ANNOUNCEMENTSTOCK/Exchange/Penyesuaian%20Kalender%20Bursa%20Peng-00171%20ENG-No.%20Peng-00171BEI.POP09-2026.pdf |

The IDX rules page lists II-A 2026 and II-A 2025 under Peraturan BEI › Peraturan Perdagangan. II-A 2026 item 4 revokes II-A 2025: *"Keputusan Direksi … Nomor: Kep-00003/BEI/04-2025 … dicabut dan dinyatakan tidak berlaku."*

## 1. Tick table (AC2)

These values are identical in II-A 2020, 2021, 2023, 2025 and 2026. II-A 2026 VI.5.2:

> VI.5.2.1. untuk Efek Bersifat Ekuitas dengan Harga Previous kurang dari Rp200,00 (dua ratus rupiah) ditetapkan Fraksi Harga sebesar Rp1,00 (satu rupiah) dengan jenjang perubahan harga maksimum yang diperkenankan adalah Rp10,00 (sepuluh rupiah);
> VI.5.2.2. … dalam rentang Rp200,00 (dua ratus rupiah) sampai dengan kurang dari Rp500,00 (lima ratus rupiah) ditetapkan Fraksi Harga sebesar Rp2,00 … maksimum … Rp20,00;
> VI.5.2.3. … Rp500,00 … sampai dengan kurang dari Rp2.000,00 … Rp5,00 … maksimum … Rp50,00;
> VI.5.2.4. … Rp2.000,00 … sampai dengan kurang dari Rp5.000,00 … Rp10,00 … maksimum … Rp100,00;
> VI.5.2.5. … Harga Previous Rp5.000,00 (lima ribu rupiah) atau lebih, ditetapkan Fraksi Harga sebesar Rp25,00 … maksimum … Rp250,00.

| Price (Rp) | Lower bound | Upper bound | Tick | Maximum step per order change |
|---|---|---|---|---|
| < 200 | (min price) | exclusive 200 | 1 | 10 |
| 200 – < 500 | **inclusive** 200 | exclusive 500 | 2 | 20 |
| 500 – < 2,000 | **inclusive** 500 | exclusive 2,000 | 5 | 50 |
| 2,000 – < 5,000 | **inclusive** 2,000 | exclusive 5,000 | 10 | 100 |
| ≥ 5,000 | **inclusive** 5,000 | none | 25 | 250 |

**Which price picks the tier.** VI.5.2 names the Harga Previous, but VI.5.4 then says the tier moves with the order price:

> VI.5.4. Besaran Fraksi Harga dan jenjang perubahan harga maksimum … berubah secara seketika (real time) berdasarkan harga penawaran jual dan/atau permintaan beli yang dimasukkan ke JATS sesuai dengan rentang harga sebagaimana dimaksud dalam ketentuan VI.5.2.

**For M2:** validate a price against the tier of the price itself. That means 200 must be a multiple of 2, 199 a multiple of 1, and 5,000 a multiple of 25. The boundary tests are 199/200, 499/500, 1,995/2,000 and 4,990/5,000. The "maximum step" (jenjang) limits how far one order amendment can move the price. VI.5.5 says it applies *"sepanjang tidak melampaui batasan persentase Auto Rejection"*. It matters to an order router but not to a daily-bar backtester.

**Lot:** II-A 2023 VI.4.2 has *"Satu satuan perdagangan (round lot) Efek Bersifat Ekuitas ditetapkan 100 (seratus) Efek Bersifat Ekuitas."* That agrees with spec §3.6.

**Before 7 Dec 2020 (unverified):** news reports say this five-tier table took effect on 2 May 2016 under Kep-00023/BEI/04-2016 (detik.com d-3200275). Before that there were three tiers under Kep-00071/BEI/11-2013: below Rp500 the tick was 1, from Rp500 to below Rp5,000 it was 5, and from Rp5,000 it was 25. No IDX document was found for either, so the M2 data file must not claim a tick table before 2020-12-07 as verified. Spec AC1 backtests from 2016-01-01, so this gap needs a decision in the M2 plan (see "Open for M2").

## 2. Minimum price

| In force | Minimum price (shares) | Source |
|---|---|---|
| up to 27 Sep 2026 | Rp50 | II-A 2025 VI.6.1: *"Rp50,00 (lima puluh rupiah), untuk saham dan Efek lain yang mengacu pada Peraturan ini"* (the same in II-A 2023; II-A 2020 and 2021 start their lowest auto-reject tier at Rp50, but their VI.6 text was not read) |
| **from 28 Sep 2026** | **Rp1** | II-A 2026 VI.6: *"Batasan harga terendah (minimum) Efek yang dimasukkan ke JATS untuk diperdagangkan di Pasar Reguler dan Pasar Tunai adalah Rp1,00 (satu rupiah)."* |

## 3. Auto-rejection bands (AC3, AC4)

An order is rejected if its price is **more than** the stated percentage above or below the Acuan Harga (reference price), so a price exactly on the band is accepted. Every version here uses the wording *"lebih dari X% … di atas atau … di bawah Acuan Harga"*. II-A states no rounding rule for the band. Because an order must also sit on the tick grid (VI.5.1), the highest price that can be accepted is the highest tick-valid price at or below the reference × (1 + X%), and the lowest is the lowest tick-valid price at or above the reference × (1 − X%). This is derived from the two rules together, not quoted, and M2's boundary tests should say so.

**Reference price.** II-A 2025 and II-A 2026 VI.7.3.1 give *"Harga Previous untuk saham yang sudah diperdagangkan di Bursa"*, and I.14 defines it as *"Harga Previous adalah Harga Penutupan pada Hari Bursa sebelumnya."* The exceptions are the theoretical price after a corporate action (VI.7.3.2), the IPO price (VI.7.3.3), and a valuer's fair value (VI.7.3.4). **II-A 2023 used the opening price instead.** VI.7.3.1 there reads *"Harga Pembukaan di Pasar Reguler …"*, and VI.7.3.2 falls back to the Harga Previous only when there is no opening price. The switch to the previous close appears in the II-A 2025 text, which re-issues Kep-00196/BEI/12-2024. When between 3 Apr 2023 and 9 Dec 2024 the switch happened was not traced.

**Bands by period.** Up and down percentages, by price tier:

| Effective from | Effective to | Rp1–10 | Rp50/11 – 200 | > 200 – 5,000 | > 5,000 | Source |
|---|---|---|---|---|---|---|
| 7 Dec 2020 (earliest verified) | 2 Apr 2023 | n/a (min 50) | 35 / 7 | 25 / 7 | 20 / 7 | II-A 2020 and 2021, Memutuskan: *"lebih dari 35% … di atas atau 7% … di bawah acuan Harga …"* |
| 3 Apr 2023 | 31 May 2023 | n/a | 35 / 7 | 25 / 7 | 20 / 7 | II-A 2023 Memutuskan 4.a |
| 5 Jun 2023 | 1 Sep 2023 | n/a | 35 / 15 | 25 / 15 | 20 / 15 | II-A 2023 Memutuskan 4.b |
| 4 Sep 2023 | 7 Apr 2025 | n/a | 35 / 35 | 25 / 25 | 20 / 20 | II-A 2023 Memutuskan 4.c → VI.7.1.2 |
| **8 Apr 2025** | 27 Sep 2026 | n/a | 35 / 15 | 25 / 15 | 20 / 15 | II-A 2025 Memutuskan 2 |
| **28 Sep 2026** | 31 Dec 2026 | ±Rp1 | 35 / 15 | 25 / 15 | 20 / 15 | II-A 2026 Memutuskan 2–3 |
| **1 Jan 2027** | — | ±Rp1 | 35 / 35 | 25 / 25 | 20 / 20 | II-A 2026 VI.7.1.1 |

Tier bounds as written:
- **Up to 27 Sep 2026:** *"rentang harga Rp50,00 … sampai dengan Rp200,00"* (200 inclusive), *"lebih dari Rp200,00 … sampai dengan Rp5.000,00"* (5,000 inclusive), and *"di atas Rp5.000,00"*.
- **From 28 Sep 2026:** *"rentang harga Rp1,00 … sampai dengan Rp10,00"*, *"Rp11,00 … sampai dengan Rp200,00"*, *"lebih dari Rp200,00 … sampai dengan Rp5.000,00"*, and *"di atas Rp5.000,00"*. The Rp1–10 band is an absolute Rp1 either way: *"lebih dari Rp1,00 (satu rupiah) di atas atau di bawah Acuan Harga"*.

**The tier edges differ between the two tables.** In the auto-rejection table, 200 and 5,000 sit in the **lower** tier (inclusive upper bound). In the tick table, 200 and 5,000 sit in the **higher** tier (inclusive lower bound). `rules.py` must keep the two tables separate and must not share one tier function between them.

**The 2027 revision (spec §3.6, AC4).** The proposed revision is now **adopted and scheduled**. II-A 2026 was issued on 21 Sep 2026. It puts the Rp1 minimum and the Rp1–10 band in force from 28 Sep 2026, and it makes the bands symmetric from 1 Jan 2027 (Memutuskan 2: *"belum diberlakukan sampai dengan 31 Desember 2026"*). The band percentages match the proposal the spec recorded: 35/25/20. The low tier now starts at Rp11, not Rp10.

**Before 7 Dec 2020 (unverified):** news reports say the down band went to 10% around 10 Mar 2020 and to 7% around 13 Mar 2020, and was a symmetric 35/25/20 before that. No IDX document was found for this.

**Out of scope here:** the Special Monitoring Board (Papan Pemantauan Khusus), which trades in a full call auction, and the Acceleration Board have rules of their own. The spec excludes the Special Monitoring Board by default (§3.2). It says nothing about the Acceleration Board, so the M2 plan must decide whether to exclude that too. The II-A text above covers neither board.

## 4. Holidays (AC5)

Days with no trading and no settlement. In IDX's English, "Commemoration of X" is the collective-leave day (cuti bersama). A check script recomputed the monthly trading-day totals from these dates, and both match the announcements: **239 for 2026 and 241 for 2027**. No holiday falls on a weekend in either list.

**2026** (Peng-00171/BEI.POP/09-2025, 22 days):
01-01 New Year · 16-01 Isra Mikraj · 16-02 collective leave, Chinese New Year · 17-02 Chinese New Year 2577 · 18-03 collective leave, Nyepi · 19-03 Nyepi 1948 · 20-03, 23-03, 24-03 collective leave, Eid al-Fitr 1447 · 03-04 Good Friday · 01-05 Labour Day · 14-05 Ascension Day · 15-05 collective leave, Ascension Day · 27-05 Eid al-Adha 1447 · 28-05 collective leave, Eid al-Adha · 01-06 Pancasila Day · 16-06 Islamic New Year 1448 · 17-08 Independence Day · 25-08 Prophet's Birthday · 24-12 collective leave, Christmas · 25-12 Christmas · 31-12 exchange holiday.
Eid al-Fitr itself (21–22 Mar) and Easter (5 Apr) fall on weekends, and the announcement's notes name them. Vesak (31 May 2026) is a Sunday and is not a trading holiday either.

**2027** (Peng-00169/BEI.POP/09-2026, 20 days):
01-01 New Year · 05-01 Isra Mikraj 1448 · 05-02 collective leave, Chinese New Year 2578 · 08-03 Nyepi 1949 · 09-03 collective leave, Eid al-Fitr 1448 · 10-03, 11-03 Eid al-Fitr 1448 · 12-03, 15-03 collective leave, Eid al-Fitr · 25-03 collective leave, Good Friday · 26-03 Good Friday · 06-05 Ascension Day · 17-05 Eid al-Adha 1448 · 18-05 collective leave, Eid al-Adha · 19-05 collective leave, Vesak · 20-05 Vesak 2571 · 01-06 Pancasila Day · 17-08 Independence Day · 24-12 collective leave, Christmas · 31-12 exchange holiday.
Peng-00171/BEI.POP/09-2026 corrects only the wording "Ascension Day of Jesus Christ (Easter)". It *"does not affect the day and date previously determined."*

A search of the IDX announcement list on 2026-09-25 for "Holiday" found no amendment to the 2026 calendar. Both announcements say the calendar can change if Bank Indonesia's clearing calendar or the government's holidays change. `holidays.toml` should therefore record the announcement number next to each year, so that a later amendment is a visible data edit.

## 5. Sessions (AC6)

The regular market, from II-A 2026 IV.2. The times are identical in II-A 2025.

| | Monday to Thursday | Friday |
|---|---|---|
| Pre-opening, order entry | 08:45:00 – 08:57:59 | same |
| Pre-opening, no amend or cancel / no amend / matching | 08:56:00–08:57:59 / 08:56:00–08:59:59 / 08:58:00–08:59:59 | same |
| **Session I** | **09:00:00 – 12:00:00** | **09:00:00 – 11:30:00** |
| **Session II** | **13:30:00 – 15:49:59** | **14:00:00 – 15:49:59** |
| Pre-closing, order entry (random closing 15:58:00–15:59:59) | 15:50:00 – 15:59:59 | same |
| Matching at the closing price | 16:00:00 – 16:01:59 | same |
| Post-closing | 16:02:00 – 16:15:00 | same |

II-A 2023 had the same Session I and Session II hours. The auction windows are what moved: in 2023, pre-opening ran 08:45:00–08:59:00 plus 08:59:01–08:59:59, pre-closing ran 15:50:00–16:00:00, closing-price matching ran 16:00:01–16:00:59, and post-closing ran 16:01:00–16:15:00. II-A 2020 set the IV.2–IV.4 hours to apply from 26 Jul 2021 and ran a different schedule before that. That schedule was not transcribed.

**Correction to spec §3.6.** The spec says *"Trading hours changed on 15 Dec 2025 (Kep-00003/BEI/04-2025)"*. The primary texts do not support that. Kep-00003/BEI/04-2025 took effect on **8 Apr 2025**, and the continuous-session hours were already the same in the 3 Apr 2023 text. The date and the claim came from a news source. The spec is corrected in this PR.

## 6. Verdict for M2

| Data file | Verified from | Unverified before |
|---|---|---|
| `tick_sizes.toml` | 2020-12-07 (5-tier table, unchanged since) | 2016-05-02 five-tier start; the three-tier table before it |
| `auto_reject.toml` | 2020-12-07 (the seven periods above) | the March 2020 COVID changes; the pre-2020 bands |
| `holidays.toml` | 2026 and 2027 | every year before 2026 (not researched in this ticket) |
| `sessions.toml` | 2023-04-03 onwards | before 2023-04-03 |

**Open for M2** (decisions for the M2 plan, not research gaps in this ticket):
1. The AC1 backtest starts on 2016-01-01, but verified rules start on 2020-12-07 and verified holidays start in 2026. For earlier years the M2 plan must do one of two things: source them (IDX holiday announcements are listed back to 2024 on the announcements page, and older ones may need TICMI), or have the backtester refuse dates it has no rules for, as §9.1 already requires for holidays.
2. The reference price (previous close or opening price) changed at some date between 2023-04-03 and 2024-12-09. It only matters if the backtester models auto-rejection before 2025.

## Review log

- **Pass 1 (2026-09-25):** a full read against the extracted texts. Two findings, both fixed. (1) The doc claimed the spec excludes the Acceleration Board; §3.2 names only the Special Monitoring Board. (2) The doc claimed the 2026 announcement's notes name Vesak; the notes as read name Eid al-Fitr and Easter.
- **Pass 2 (2026-09-25):** mechanical checks. Each of #24's AC1–AC8 is addressed: AC1 is the Sources table, AC2 §1, AC3–AC4 §3, AC5 §4, AC6 §5, AC7 is the unverified markers in §1, §3 and §6, and AC8 is the spec edits to §3.6, §9.1, §12 and Appendix A. The 2026 and 2027 monthly trading-day counts were recomputed by script: 239 and 241, matching IDX. A script compared every Kep and Peng number in the doc against the Sources table. **One finding:** Kep-00023/BEI/04-2016 and Kep-00071/BEI/11-2013 are cited but not listed. Both are the news-only decisions in §1, and both are already marked unverified. The fix is this note, not the table, because the table lists only documents that were read.
- **Pass 3 (2026-09-25):** the same script re-run: every document cited as a source is in the table, and the only two absent are the unverified pair above. The whole doc was re-read against #24's ACs. **0 findings. Loop closed.**
