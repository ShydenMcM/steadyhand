# T-VERIFY: primary sources for the fee and rule rows from 13 Mar 2020

**Ticket:** #41 (spec §12, T-VERIFY). **Researched:** 2026-09-25. **Feeds:** M2 (`data/fees.toml`, `data/auto_reject.toml`, the backtest start date in spec §14 AC1).

This is engineering research, not legal or tax advice. Every value comes from a primary document (a law, a regulation, an SRO rule or decision, or an SRO's own audited annual report) unless it is marked **unverified** or **secondary**. Quotes are verbatim in the original language.

**Why this exists.** Shyden decided on 2026-09-25 that **a backtest refuses any date for which a rule or fee row is not primary-verified**: no `verified = false` rows ship. The rule rows were verified from 13 Mar 2020 (`t-hist.md` §6), but four gaps kept that date from holding across the whole window. This doc closes three of them and corrects three earlier findings on the way: the reference price (`t-hist.md` §5, `t-rules.md` §3), the end of the 2020 guarantee-fund cut, and the Rp10,000,000 stamp-duty threshold (both `t-fees.md`).

**Source order (Shyden, 2026-09-25).** Annual reports came from KSEI's and KPEI's own sites, and laws and regulations from BPK. The IDX rule decisions came from **idx.co.id as a fallback**. The Archive held no copy of Kep-00196 and nothing under Kep-00108's media folder. It went offline before Kep-00063 could be checked. Kep-00025, Kep-00061 and Kep-00055 were read on idx.co.id, as T-RULES and T-HIST did. The Archive supplied the three captures of IDX's rules page used in §4.1.

## Sources

All pages and files were accessed on 2026-09-25.

| Short name | Document | Issuer | In force | Where |
|---|---|---|---|---|
| **KSEI AR 2019** | *Laporan Tahunan 2019*, with audited statements | KSEI | FY2019 | `web.ksei.co.id/files/uploads/annual_reports/report_file/id-id/17_laporan_tahunan_2019_20200922110729.pdf` |
| **KSEI AR 2020** | *Laporan Tahunan 2020*, with audited statements | KSEI | FY2020 | `web.ksei.co.id/files/uploads/annual_reports/report_file/id-id/18_laporan_tahunan_2020_20210713155600.pdf` |
| **KPEI AR 2021** | *Annual Report KPEI 2021*, with audited statements (FY2021 and FY2020 comparatives) | KPEI | FY2021 | `assets-website.idclear.co.id/idclear/storage/6642/Annual-Report-KPEI-2021.pdf` |
| **SKB SRO 2020** | Joint decree Kep-00052/BEI/08-2020, Kep-022/DIR/KPEI/08-2020, Kep-0022/DIR/KSEI/08-2020 (negotiated-market fees) | IDX, KPEI, KSEI | 1 Sep 2020 | `web.ksei.co.id/files/SKB_SRO_-_Kebijakan_Keringanan_Biaya_Transaksi_di_Pasar_Negosiasi_final_Upload.pdf` |
| **Kep-00025** | Kep-00025/BEI/03-2020, II-A amendment | IDX | 13 Mar 2020 | idx.co.id (fallback, as in `t-hist.md`): `www.idx.co.id/media/8318/perubahan-peraturan-nomor-ii-a-tentang-perdagangan-efek.pdf` |
| **Kep-00063** | Kep-00063/BEI/09-2020, *Perubahan Acuan Harga di Pasar Reguler dan Pasar Tunai* | IDX | 7 Sep 2020 | idx.co.id (fallback): `www.idx.co.id/media/9051/sk-perubahan-acuan-harga-di-pasar-reguler-dan-pasar-tunai.pdf` |
| **Kep-00108** | Kep-00108/BEI/12-2020, *Perubahan Peraturan Nomor II-A* | IDX | 7 Dec 2020 | idx.co.id (fallback): `www.idx.co.id/media/9410/perubahan_peraturan_ii_a_perdagangan_efek_bersifat_ekuitas.pdf` |
| **Kep-00061** | Kep-00061/BEI/07-2021, *Perubahan Peraturan Nomor II-A* | IDX | 26 Jul 2021 | idx.co.id (fallback): `www.idx.co.id/media/10022/peraturan_ii_a_perdagangan_efek_bersifat_ekuitas.pdf` |
| **Kep-00055** | Kep-00055/BEI/03-2023, Peraturan Nomor II-A | IDX | 3 Apr 2023 | idx.co.id (fallback): `www.idx.co.id/Media/y0vjxqur/signed_peraturan_ii_a_perdagangan_efek_bersifat_ekuitas.pdf` |
| **Kep-00196** | Kep-00196/BEI/12-2024, *Perubahan Peraturan Nomor II-A* | IDX | 9 Dec 2024 | idx.co.id (fallback): `www.idx.co.id/Media/znjnnr22/signed_peraturan_ii_a_perdagangan_efek_bersifat_ekuitas-20241206.pdf` |
| **IDX rules page** | *Peraturan BEI* listing, captured 6 Apr 2024, 21 Jun 2024 and 24 Mar 2025 | IDX | — | Archive, `www.idx.co.id/id/peraturan/peraturan-bei/` at 20240406132709, 20240621052337, 20250324070844 |
| **PP 24/2000** | *PP Nomor 24 Tahun 2000*, stamp-duty tariffs under UU 13/1985 | Government | 1 May 2000 (Pasal 7) | BPK, `peraturan.bpk.go.id/Details/53201/pp-no-24-tahun-2000` |
| **UU 10/2020** | *UU Nomor 10 Tahun 2020 tentang Bea Meterai* | DPR and President | 1 Jan 2021 | BPK, `peraturan.bpk.go.id/Details/149748/uu-no-10-tahun-2020` |
| **PMK 151/2021** | *PMK Nomor 151/PMK.03/2021*, stamp-duty collectors | Minister of Finance | 27 Oct 2021 | BPK, `peraturan.bpk.go.id/Details/185215/pmk-no-151pmk032021` |
| **PP 3/2022** | *PP Nomor 3 Tahun 2022*, stamp-duty exemptions | Government | 12 Jan 2022 | BPK, `peraturan.bpk.go.id/Details/196160/pp-no-3-tahun-2022` |
| DJP clarification | *Klarifikasi DJP terkait Bea Meterai*, 19 Dec 2020 | DJP | — | `www.pajak.go.id/index.php/en/node/42688` |
| Tempo 2022 | *Berlaku Mulai Hari Ini, Bea Meterai untuk Transaksi Saham di Atas Rp 10 Juta*, 1 Mar 2022 | Tempo (news) | — | `www.tempo.co/ekonomi/berlaku-mulai-hari-ini-bea-meterai-untuk-transaksi-saham-di-atas-rp-10-juta-421432` |

## 1. The KSEI settlement fee, 13 Mar 2020 – 19 Jan 2021 (AC2)

**Verdict: 0.003%, verified** from KSEI's own audited statements for FY2019 and FY2020. It holds until KSEI Rule VI-A took over on 20 Jan 2021 (`t-fees.md` §1.1), at the same rate.

KSEI AR 2020, note 27a (PDF p. 336), names the circular T-FEES could not find and states its rate:

> "Berdasarkan Surat Edaran PT Kustodian Sentral Efek Indonesia No. SE-0002/DIR-EKS/KSEI/1211 Perihal Biaya Penyelesaian Transaksi Bursa Untuk Efek Bersifat Ekuitas di KSEI, porsi fee transaksi bursa untuk Perusahaan ditetapkan sebesar 0,003% (nol koma nol nol tiga per seratus) dari nilai per transaksi Bursa"

Its management discussion (PDF p. 115) gives the base: *"sebesar 0,003% (nol koma nol nol tiga perseratus) dari nilai kumulatif Transaksi Bursa per bulan"*. The accounting-policy note (PDF p. 280) reads *"Imbalan jasa penyelesaian transaksi bursa sebesar 0,003% dari nilai transaksi bursa"*. KSEI AR 2019 carries the same policy note (PDF p. 273) and the same note 27a (PDF p. 325).

- **A typo in the FY2019 Indonesian text.** Note 27a in AR 2019 reads *"ditetapkan sebesar 0,03% (nol koma nol tiga per seratus)"*, then says KSEI receives 10% of that fee. The FY2019 policy note and the FY2020 note both give 0.003%, which is 10% of 0.03%. The FY2019 wording is read as the whole fee, not KSEI's share.
- **The 2020 stimulus did not touch it.** KSEI AR 2020 (PDF p. 94) lists all of KEP-0020/DIR/KSEI/0620's stimulus: issuer registration fees, custody from 0.005% to 0.0045%, several S-INVEST fees, and VPN lines. The settlement fee is not among them.
- **The 2009 list's 0.006% did not apply in 2020.** SE-0002/DIR-EKS/KSEI/1211 is dated 29 Dec 2011, and KEP-0005 revoked it on 20 Jan 2021 (`t-fees.md` §1.2), so it was the rule in force for the whole window.
- **Corroboration:** the SKB SRO 2020 (in force 1 Sep 2020) splits the negotiated-market fee as *"Biaya Penyelesaian Transaksi Bursa sebesar 0,003%"*. It governs the negotiated market only, so it corroborates the rate without establishing it.

This also verifies the KSEI rate for FY2019. Earlier years were outside this ticket and were not re-read.

## 2. The KPEI guarantee fund, 13 Mar 2020 – 19 Jan 2021 (AC3)

**Verdict: 0.01%, except 0.005% from 18 Jun 2020 to 17 Dec 2020, verified** from KPEI's audited notes. This **corrects** `t-fees.md` §1.3, whose secondary source (Hukumonline) ended the window on 16 Dec 2020.

KPEI AR 2021, note on guarantee-fund receivables (PDF p. 441):

> "Berdasarkan Surat Keputusan Direksi No. KEP-019/DIR/KPEI/0620 tanggal 18 Juni 2020 tentang Persetujuan Relaksasi Kebijakan dan Stimulus SRO kepada Stakeholder dinyatakan bahwa besaran iuran Dana Jaminan menjadi 50% dari ketentuan transaksi atas Transaksi Bursa atas Efek bersifat ekuitas atau 0,005% (lima perseratus ribu) dari nilai setiap transaksi atas efek bersifat ekuitas. Surat Keputusan ini berlaku sejak 18 Juni 2020 sampai 17 Desember 2020."

The English half of the same note: *"This Decision Letter is applied from June 18, 2020 until December 17, 2020."* *"Sejak … sampai"* is read as inclusive at both ends, the usual reading of Indonesian decisions, so the first trading day back at 0.01% is 18 Dec 2020. The text does not say so in words.

## 3. Stamp duty on trade confirmations (AC4)

**Verdict for 13 Mar – 31 Dec 2020: unverified.** From 1 Jan 2021 the law is primary-verified, in two phases (§3.2).

### 3.1 Before 2021 (UU 13/1985 and PP 24/2000)

PP 24/2000 Pasal 1 lists the dutiable documents by category and never names a trade confirmation. Two categories could reach one, and they carry different amounts:

- (a) *"surat perjanjian dan surat-surat lainnya yang dibuat dengan tujuan untuk digunakan sebagai alat pembuktian mengenai perbuatan, kenyataan atau keadaan yang bersifat perdata"*, at a flat Rp6,000 (Pasal 2(1));
- (d) *"surat yang memuat jumlah uang"*, limited to four kinds (a receipt of money, a bank booking, a bank balance, an acknowledgement of a paid debt), at Rp3,000 or Rp6,000 by value, with nothing due up to Rp250,000 (Pasal 2(2)).

No primary text says which one a trade confirmation falls under, or that it was dutiable at all. UU 10/2020 creates an explicit category for it (§3.2), and the DJP clarification of 19 Dec 2020 speaks only of the new law. **Searched without a primary answer:** PP 24/2000, UU 10/2020 and its elucidation, the DJP clarification, Hukumonline's report of the Finance Minister's statement (22 Dec 2020), and a web search for a DJP ruling on trade confirmations under UU 13/1985.

### 3.2 From 2021

- **1 Jan 2021 – 11 Jan 2022: every trade confirmation, Rp10,000.** UU 10/2020 Pasal 3(2)e makes *"Dokumen transaksi surat berharga"* dutiable, and its elucidation names *"trade confirmation"* and places the liability at creation: *"Sebagai contoh adalah trade confirmation pembelian surat berharga saham di bursa efek yang berupa Dokumen elektronik, Bea Meterai terutang pada saat trade confirmation dibuat secara sistem oleh perusahaan."* No exemption for small confirmations existed yet.
- **From 12 Jan 2022: confirmations up to Rp10,000,000 are exempt.** PP 3/2022 Pasal 5 huruf b exempts *"transaksi surat berharga yang dilakukan di bursa efek berupa konfirmasi transaksi dengan nilai paling banyak Rp10.000.000,00 (sepuluh juta rupiah)"*, and Pasal 7: *"Peraturan Pemerintah ini mulai berlaku pada tanggal diundangkan"*, which was 12 Jan 2022. This is the primary source `t-fees.md` §3 could not find for the Rp10,000,000 threshold.
- **Collection by brokers came later, and it differs by broker.** PMK 151/2021 (in force 27 Oct 2021) makes an issuer of more than 1,000 such documents a month a collector, but only once DJP appoints it, and *"mulai berlaku terhitung sejak awal bulan berikutnya setelah tanggal surat penetapan"* (Pasal 4(2)). Indo Premier began deducting it on 1 Mar 2022 (Tempo 2022, **secondary**). Before a broker was appointed, the duty was still owed under the law. The broker simply did not collect it.

**Per confirmation, not per trade.** The duty attaches to the confirmation document. Stockbit and Ajaib issue one per day and charge on that day's total (`t-fees.md` §3). That is how the brokers issue the document, not a rule of the law.

## 4. The auto-rejection reference price (AC5)

**Verdict: verified for the whole window, and it corrects `t-hist.md` §5 and `t-rules.md` §3.** Those docs read the opening price in the II-A *attachments* of 2020, 2021 and 2023. Each cover decision from December 2020 on **holds that clause back** and sets the previous close as the interim rule.

| Period | Reference price | Source |
|---|---|---|
| 13 Mar 2020 – 6 Sep 2020 | opening price; the previous close when no opening price forms | Kep-00025 VI.7.3.1–2, confirmed as the rule then in force by Kep-00063's *"yang semula diatur"* |
| **7 Sep 2020 onwards** | **previous close** (*Harga Previous*), with the theoretical price after a corporate action, the IPO price, and from 7 Dec 2020 a valuer's fair value | Kep-00063, then the interim clauses of Kep-00108, Kep-00061 and Kep-00055, then Kep-00196 VI.7.3.1 |

### 4.1 The chain of decisions

Each link was read in the decision itself.

1. **Kep-00063** (issued 2 Sep 2020, in force 7 Sep 2020) replaces VI.7.3 of Kep-00025 *"sementara"* (temporarily). The old text, quoted in it, begins *"VI.7.3.1. Harga Pembukaan di Pasar Reguler untuk perdagangan saham di Pasar Reguler dan Pasar Tunai; VI.7.3.2. harga Previous apabila Harga Pembukaan tidak terbentuk"*. It is *"diubah menjadi: … VI.7.3.1. harga Previous"*, and item 4 runs it *"sampai dengan batas waktu yang ditetapkan kemudian"*.
2. **Kep-00108** (in force 7 Dec 2020) revokes Kep-00063 in item 8c, but item 6a holds its own attachment's VI.7.3 back: *"Ketentuan terkait acuan Harga sebagaimana dimaksud dalam ketentuan VI.7.3. … Lampiran Keputusan ini belum diberlakukan sampai dengan batas waktu yang akan ditetapkan kemudian."* Item 6b sets the interim rule: *"Acuan Harga … ditetapkan berdasarkan pada: 1) Harga Previous; 2) Harga Teoretis Hasil Tindakan Korporasi; 3) Harga perdana …; atau 4) nilai pasar wajar yang ditetapkan oleh penilai usaha …"*
3. **Kep-00061** (in force 26 Jul 2021) revokes Kep-00108 and repeats the hold-back and the same interim list, beginning *"1) Harga Previous"*.
4. **Kep-00055** (in force 3 Apr 2023) revokes Kep-00061, again holds VI.7.3 back (*"belum diberlakukan sampai ditetapkan kemudian oleh Bursa"*), and again sets *"1) Harga Previous"*.
5. **No II-A came between Kep-00055 and Kep-00196.** The IDX rules page lists *"II-A Kep-00055/BEI/03-2023"* as the II-A in force in the captures of 6 Apr 2024 and 21 Jun 2024, and *"II-A Kep-00196/BEI/12-2024"* in March 2025. Kep-00196's item 3 revokes Kep-00055 directly: *"Peraturan Nomor II-A … (Lampiran Keputusan Direksi PT Bursa Efek Indonesia Nomor Kep-00055/BEI/03-2023 tanggal 30 Maret 2023 …) … dicabut dan dinyatakan tidak berlaku."*
6. **Kep-00196** (issued 6 Dec 2024, *"Tgl. Diberlakukan: 9 Desember 2024"*) puts the previous close into the rule itself: *"VI.7.3.1. Harga Previous untuk saham yang sudah diperdagangkan di Bursa"*.

**What this rests on.** Each II-A revokes the one before it, and Kep-00108 revokes the one temporary override found (Kep-00063). A temporary override issued and revoked between two II-A versions without either naming it would not show up in this chain. None was found, though the search is weaker than the chain. IDX's decision list shows only decisions still in force, and it has no reference-price entry (Kep-00063 is not on it either). The IDX 2024 annual report's list of rule changes (`t-hist.md` §5) names none. A web search for *"Perubahan Acuan Harga"* turned up only Kep-00063.

**The 2024 pre-opening change is Kep-00196.** Its recital (a) is the evaluation of *"daftar saham yang masuk ke dalam daftar saham sesi Pra-pembukaan"*, the *"Perluasan Saham Pre-Opening"* that the IDX 2024 annual report names. It was not a separate II-A amendment.

### 4.2 What it means for M2

The previous close is the reference on every trading day from 7 Sep 2020. The opening price applies only from 13 Mar to 6 Sep 2020. The "impossible data" check (spec §5 step 1) can compare close-to-close moves with the band directly from 7 Sep 2020, except on a stock's first trading day (the IPO price) and after a corporate action (the theoretical price). Before that, a genuine close can sit further from the previous close than the band allows (`t-hist.md` §6 item 2).

## 5. Verdict (AC6)

| Row | Verified from | Within 13 Mar 2020 – today |
|---|---|---|
| Tick table, bands, minimum price | 13 Mar 2020 (`t-hist.md`) | verified |
| Reference price | 13 Mar 2020 (§4) | verified |
| Holidays | 2016 | verified |
| IDX fee 0.018% | 13 Mar 2020 onward (`t-fees.md`) | verified |
| KPEI clearing 0.009% | FY2019 onward (`t-fees.md`) | verified |
| KSEI settlement 0.003% | FY2019 onward (§1) | verified |
| Guarantee fund 0.01% / 0.005% | the whole window (§2) | verified |
| VAT on the levy, sale tax 0.1% | 2016 onward (`t-fees.md`) | verified |
| **Stamp duty** | **1 Jan 2021** (§3.2) | **13 Mar – 31 Dec 2020 unverified** |

**The earliest date from which every rule and fee row is primary-verified is 2021-01-01.** One row decides it: stamp duty on trade confirmations under the old law. Spec §14 AC1 therefore starts on 2021-01-01. That is 19 days earlier than the 20 Jan 2021 fallback in #41, because the KSEI rate is now verified.

**Open for the M2 plan** (decisions, not research gaps):
1. **Legal liability or actual collection.** From 1 Jan 2021 to 11 Jan 2022 every confirmation owed Rp10,000 under the law. A broker collects it only once DJP appoints it (PMK 151/2021, in force 27 Oct 2021), and when each broker started is not in any primary source found (Indo Premier from 1 Mar 2022, secondary). A backtest can charge what the law imposed, or what an investor was actually debited, which is broker-specific and unverified. For a small account the gap is material: Rp10,000 on a Rp5,000,000 trading day is 0.2%.
2. **Per day or per trade.** The duty is per confirmation, and brokers issue one per day. `t-fees.md` §6 item 1 already notes that §4.3's per-trade `costs(side, gross, on)` cannot charge it as written.

## Review log

- **Pass 1 (2026-09-25):** mechanical. Every quote was checked against the source text with whitespace removed: 17 quotes from the local extractions (KSEI, KPEI, the SKB, BPK texts) and 22 from the IDX decisions, parsed in the browser. All matched, and a deliberately wrong quote (the 16 Dec end date) was reported missing, so the checker can fail. Two findings, fixed: (1) the intro counted two corrections, while the doc corrects three; (2) §1 described KSEI's 2020 stimulus from part of its list, and the full list (issuer fees, custody, S-INVEST, VPN) has now been read.
- **Pass 2 (2026-09-25):** a full read. Six findings, fixed: (1) the source-order note said the Archive had no capture of any IDX decision, while only Kep-00196 and Kep-00108's folder were checked before it went offline; (2) PP 24/2000's end date of 31 Dec 2020 had no source, and only its start (Pasal 7) is given now; (3) "both ends inclusive" was stated as the text's, while it is a reading; (4) §4.2 left out the IPO and corporate-action exceptions to the close-to-close check; (5) the open item said brokers collected nothing before appointment, from one secondary report; (6) Pass 1 counted 25 IDX quotes, while it checked 22.
- **Pass 3 (2026-09-25):** a read of the edits this ticket made to `t-fees.md`, `t-hist.md`, `t-rules.md` and the spec. No finding in this doc. One in `t-rules.md`, fixed: its correction cited "Kep-00055, item 6" for the hold-back, but item 6 is the revocation clause, and the hold-back's item number was not read. Two in the spec, fixed and logged there as its Pass 13.
- **Pass 4 (2026-09-25):** mechanical. Every `t-verify.md` § reference in the research docs and the spec resolves to a heading. Every in-force date used (13 Mar, 7 Sep, 7 Dec and 18 Dec 2020; 26 Jul 2021; 12 Jan 2022; 3 Apr 2023; 9 Dec 2024) is a weekday. The 19-day difference to 20 Jan 2021 is correct. The spec mentions 2016-01-01 and `verified = false` only in its review log. **No findings: the review loop ends here.**
