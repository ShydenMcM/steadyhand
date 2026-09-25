# T-FEES: the IDX levy, the 0.1% sale tax, stamp duty and broker fees

**Ticket:** #38 (spec §12, T-FEES). **Researched:** 2026-09-25. **Feeds:** M2 (`data/fees.toml`, the fees task, spec §5.1 and §9.1).

This is engineering research, not legal or tax advice. Every value comes from a primary document (a law, a regulation, an SRO rule or decision, an SRO's own annual report, or the broker's own page) unless it is marked **unverified** or **secondary**. Quotes are verbatim in the original language.

**Source order (Shyden, 2026-09-25).** Nothing new was taken from idx.co.id. The IDX annual report was read from an Internet Archive capture. Kep-00025/BEI/03-2020 is the copy T-HIST obtained from idx.co.id as a fallback, because the Archive's only capture is truncated (`t-hist.md`, Sources).

## Sources

All pages and files were accessed on 2026-09-25.

| Short name | Document | Issuer | Date | Obtained |
|---|---|---|---|---|
| **PP 41/1994** | *Peraturan Pemerintah Nomor 41 Tahun 1994 tentang Pajak Penghasilan atas Penghasilan dari Transaksi Penjualan Saham di Bursa Efek* | Government | 1994 | BPK, `peraturan.bpk.go.id/Details/57263` (PDF `/Download/46719/…`) |
| **PP 14/1997** | *PP Nomor 14 Tahun 1997*, amending PP 41/1994 | Government | 29 May 1997 (issued and in force) | BPK, `peraturan.bpk.go.id/Details/56237` (PDF `/Download/45728/…`); status *Berlaku* |
| **UU 42/2009** | *Undang-Undang Nomor 42 Tahun 2009*, third amendment of the VAT law | Government | 2009 | BPK, `peraturan.bpk.go.id/Details/38787/uu-no-42-tahun-2009` (PDF `/Download/28116/UU%20Nomor%2042%20Tahun%202009.pdf`) |
| **UU HPP** | *UU Nomor 7 Tahun 2021 tentang Harmonisasi Peraturan Perpajakan* | Government | 2021 | BPK, `peraturan.bpk.go.id/Details/185162/uu-no-7-tahun-2021` (PDF `/Download/178620/UU%20Nomor%207%20Tahun%202021.pdf`) |
| **PMK 131/2024** | *PMK Nomor 131 Tahun 2024* (VAT at 12% on a base of 11/12) | Minister of Finance | set 31 Dec 2024, in force 1 Jan 2025 | BPK, `peraturan.bpk.go.id/Details/311485/pmk-no-131-tahun-2024` (PDF `/Download/372221/131%20th%202024.pdf`) |
| **UU 10/2020** | *UU Nomor 10 Tahun 2020 tentang Bea Meterai* | Government | enacted 26 Oct 2020, in force 1 Jan 2021 | BPK, `peraturan.bpk.go.id/Details/149748/uu-no-10-tahun-2020` (PDF `/Download/141992/UU%20Nomor%2010%20Tahun%202020.pdf`) |
| PMK 134/2021 | *PMK Nomor 134/PMK.03/2021* (payment of stamp duty) | Minister of Finance | 2021 | BPK, `peraturan.bpk.go.id/Details/179718/pmk-no-134pmk032021` (PDF `/Download/173109/134_PMK.03_2021.pdf`) |
| **Kep-00025** | Kep-00025/BEI/03-2020, IDX Rule II-A in full as its attachment | IDX | 12 Mar 2020, in force 13 Mar 2020 | **idx.co.id** (fallback), by T-HIST: see `t-hist.md`, Sources |
| **IDX AR 2017** | IDX, *Laporan Tahunan dan Laporan Keuangan 2017* (consolidated statements for 2017 and 2016) | IDX | 2018 | Archive, 20250914211553 of `idx.co.id/Media/5649/idx-ar-dan-lk-2017.pdf` |
| **KPEI AR 2019** | KPEI, *Laporan Tahunan 2019* | KPEI | 2020 | `assets-website.idclear.co.id/idclear/storage/3569/KPEI_AR2019_Final-(2).pdf` |
| KPEI fee page | KPEI, *Biaya Kliring dan Transaksi Bersifat Ekuitas* | KPEI | live | `www.idclear.co.id/id/segmentasi/ekuitas/biaya` |
| KPEI risk page | KPEI, *Manajemen Risiko: Sekilas* (the old *Dana Jaminan* URL redirects here) | KPEI | live | `www.idclear.co.id/id/manajemen-risiko/sekilas` |
| KPEI fund page 2021 | KPEI, *Dana Jaminan* | KPEI | captured mid-2021 | Archive, 20210615161253 of `www.idclear.co.id/page/dana-jaminan` |
| KPEI II-5 matrix | KPEI, amendment matrix for Rule II-5 (draft, *Clean Version v1*) | KPEI | — | `assets-website.idclear.co.id/idclear/storage/32806/Matriks-Perubahan-Peraturan-KPEI-No.-II-5_Clean-Version_v1.pdf` |
| **KSEI list 2009** | KSEI, *Daftar Biaya Layanan Jasa Kustodian Sentral* (attachment to KEP-017/DIR/KSEI/1209 of 9 Dec 2009; this PDF was created 30 Nov 2015) | KSEI | 9 Dec 2009 | Archive, 20170430154934 of `www.ksei.co.id/files/Daftar_Biaya_Layanan_Jasa_Kustodian_Sentral.pdf` |
| **KSEI KEP-0020** | KEP-0020/DIR/KSEI/0620, *Stimulus Biaya Layanan Jasa KSEI* | KSEI | 19 Jun 2020, valid to 17 Dec 2020 | `web.ksei.co.id/files/KEP-0020-DIR-KSEI-0620_-_Stimulus_Biaya_Layanan_Jasa_KSEI.pdf` |
| **SRO decree 2020** | Joint decree of IDX, KPEI and KSEI on negotiated-market transaction fees | IDX, KPEI, KSEI | PDF created 6 Aug 2020 | `web.ksei.co.id/files/SKB_SRO_-_Kebijakan_Keringanan_Biaya_Transaksi_di_Pasar_Negosiasi_final_Upload.pdf` |
| **KSEI KEP-0005** | KEP-0005/DIR/KSEI/0121, enacting KSEI Rule VI-A | KSEI | 20 Jan 2021, in force the same day (item 5); five fees it lists, not the settlement fee, wait for a later KSEI announcement (item 2) | Archive, 20210509185555 of `ksei.co.id/files/KEP-0005_Peraturan_Biaya_Layanan_Jasa_KSEI.pdf` |
| **KSEI VI-A** | KSEI Rule VI-A, *Biaya Layanan Jasa KSEI* (text) | KSEI | PDF created 20 Jan 2021 | Archive, 20210509203849 of `ksei.co.id/files/Peraturan_KSEI_No_VI-A_Biaya_Layanan_Jasa_KSEI.pdf` |
| **KSEI list 2022** | KSEI, *Daftar Biaya Layanan Jasa KSEI Berdasarkan Peraturan KSEI Nomor VI-A* | KSEI | PDF created 5 Oct 2022 | `web.ksei.co.id/files/Daftar_Biaya_Layanan_Jasa_KSEI_Berdasarkan_Peraturan_KSEI_Nomor_VI_A_.pdf` |
| Hukumonline KEP-019 | Hukumonline's record of KEP-019/DIR/KPEI/0620 (**secondary**: a legal database, not the issuer) | Hukumonline | — | `www.hukumonline.com/pusatdata/detail/lt5ef312e04ff3a/…` |
| **BCA Sekuritas** | *Mekanisme Perdagangan Saham* (FAQ with the levy table) | PT BCA Sekuritas | — | `www.bcasekuritas.co.id/help/faq/equities-trading-mechanism` |
| **Ajaib** | *Biaya Transaksi Saham dan Reksa Dana* | PT Ajaib Sekuritas Asia | live | `ajaib.co.id/biaya` (curl gets 403; read in Chrome) |
| **Stockbit** | *Transaksi Saham: Berapa Biaya Trading di Stockbit Sekuritas?* | Stockbit Sekuritas Digital | updated 05/08/2026 | `help.stockbit.com/id/article/transaksi-saham-berapa-biaya-trading-di-stockbit-sekuritas-1lbkyq9/` |
| Stockbit stamp duty | *Apa Itu Biaya Bea Materai?* | Stockbit Sekuritas Digital | live | `help.stockbit.com/id/article/apa-itu-biaya-bea-materai-p08y2z/` |
| **IPOT** | Ipotnews, *IndoPremier Siap Tanggung Selisih Kenaikan PPN Saham, Juga tak Naikkan Fee Transaksi* | PT Indo Premier Sekuritas (its own news site) | 30 Mar 2022 | `www.indopremier.com/ipotnews/newsDetail.php?…news_id=145663…` |

## 1. The exchange levy (AC2)

The levy is what an exchange member pays the three SROs on every trade, per side, and passes on to the client. BCA Sekuritas publishes the split as it stands now:

> "Biaya Transaksi BEI 0,018% … Biaya Kliring KPEI 0,009% … Biaya Penyelesaian KSEI 0,003% … Dana Jaminan KPEI 0,010% … PPN 12% (Tarif 12% x Nilai DPP sebesar 11/12 dari Nominal Tagihan)** 0,0033% … Total 0,1433% (Jual) 0,0433% (Beli)" (BCA Sekuritas, regular market)

The VAT line (0.0033%) is 11% of 0.030%, the three fees without the guarantee fund. **VAT is charged on the IDX, KPEI and KSEI fees but not on the guarantee fund**, and the negotiated-market column, which has no guarantee fund, carries the same 0.0033%.

### 1.1 Components

| Component | Rate | Evidence, earliest first | Verified from |
|---|---|---|---|
| IDX transaction fee | 0.018% | IDX AR 2017, note 24: *"Perusahaan memperoleh jasa transaksi sebesar 0,018% dari nilai transaksi jual dan beli efek yang diperdagangkan"* (statements for 2017 and 2016). Kep-00025, II-A XI.1.1: *"untuk transaksi di Pasar Reguler dan Pasar Tunai sebesar 0,018% … dari nilai per transaksi"*, the same in II-A 2025 and 2026. XI.2 adds VAT, collected through the exchange | FY2016 and FY2017, and from 13 Mar 2020. **2018 – 12 Mar 2020 unverified**; no change was found |
| KPEI clearing fee | 0.009% | KPEI AR 2019, revenue note: *"Jasa kliring dan penjaminan penyelesaian transaksi perdagangan efek di bursa sebesar 0,009% dari nilai transaksi"*. SRO decree 2020 (negotiated market): *"Biaya Kliring Transaksi Bursa sebesar 0,009%"*. KPEI fee page (live): *"Transaksi Bursa di Pasar Regular* 0.009% per transaksi"*. The KPEI II-5 matrix (VIII.1.1) gives the same rate, but it is a **draft**, so only corroboration | FY2019 onward. **2016–2018 unverified** |
| KSEI settlement fee | 0.003% | KSEI VI-A 4.6.1: *"Biaya penyelesaian Transaksi Bursa untuk EBE … adalah sebesar 0,003% (nol koma nol nol tiga perseratus) dari nilai kumulatif Transaksi Bursa per bulan"*. The same in the KSEI list 2022, row 13. The SRO decree 2020 splits the negotiated-market fee as *"Biaya Penyelesaian Transaksi Bursa sebesar 0,003%"* | 20 Jan 2021 (KEP-0005 item 5: *"Keputusan Direksi ini berlaku efektif terhitung sejak tanggal 20 Januari 2021"*). **Before that, unverified: see §1.2** |
| KPEI guarantee fund | 0.01% | KPEI AR 2019, citing SEOJK 23/SEOJK.04/2015 of 27 Aug 2015: *"Kontribusi Dana Jaminan berdasarkan nilai transaksi efek bersifat ekuitas sebesar 0,01% (satu per sepuluh ribu) dari nilai setiap transaksi Efek bersifat Ekuitas."* KPEI fund page 2021 has the same sentence. KPEI risk page (live): *"kutipan sebesar 0,01% (nol koma nol satu persen) dari setiap nilai transaksi bursa"* | 27 Aug 2015 onward, except §1.3 |
| VAT on the three fees | 10%, then 11% | §1.4 | 2016 onward |

### 1.2 The KSEI rate before Rule VI-A

The 2009 list (in force until VI-A replaced it) prices exchange settlement at double today's rate:

> "13 Pemindahbukuan Transaksi Bursa Untuk Efek Bersifat Ekuitas dan Unit Penyertaan. Pemegang Rekening 0,006% dari nilai kumulatif Transaksi Bursa per bulan" (KSEI list 2009)

KEP-0005, however, revokes both that list and a later circular: *"Surat Edaran KSEI Nomor SE-0002/DIR-EKS/KSEI/1211 tanggal 29 Desember 2011 perihal Biaya Penyelesaian Transaksi Bursa Untuk Efek Bersifat Ekuitas di KSEI"*. A circular from December 2011 on exactly this fee means the 2009 list's 0.006% probably no longer applied from 2012. The SRO decree 2020 cites the same circular and gives 0.003% as KSEI's share. The circular's text was not found: not on ksei.co.id, not in the Archive, and KSEI's 2012 annual report states no rate.

**Verdict:** 0.003% from 2016 to 19 Jan 2021 is **probable, unverified**. It fits the industry levy of 0.043% (§1.5) exactly, and 0.006% would make it 0.0463%. The difference is 0.003% per side, far smaller than any broker commission.

**Superseded in part by T-VERIFY (#41):** KSEI's audited statements for FY2019 and FY2020 quote SE-0002/DIR-EKS/KSEI/1211 at 0.003%, so the rate is **verified from FY2019** to 19 Jan 2021 (`t-verify.md` §1). Before FY2019 it stays probable.

### 1.3 The 2020 guarantee-fund relaxation

KEP-019/DIR/KPEI/0620 cut the guarantee-fund contribution from 0.01% to 0.005% of equity trade value as a COVID-19 stimulus. The decision itself was not found on KPEI's site or in the Archive. Hukumonline records it as *"Ditetapkan: 17 Juni 2020"*, *"Berlaku s.d.: 16 Desember 2020"*, status *"Habis Masa Berlaku"*. Press reports of the SRO stimulus package date it 18 Jun 2020. No extension was found, and KPEI's page captured in June 2021 states 0.01% again.

**Verdict:** 0.005% from about 17–18 Jun 2020 to 16 Dec 2020, **secondary** (the window matches KSEI's parallel stimulus KEP-0020, which ran from 19 Jun to 17 Dec 2020 and cut only the custody fee, from 0.005% to 0.0045%, not the settlement fee). Outside that window, 0.01%.

**Superseded by T-VERIFY (#41):** KPEI's audited FY2021 notes give KEP-019/DIR/KPEI/0620 as in force *"sejak 18 Juni 2020 sampai 17 Desember 2020"*, so the window is **18 Jun – 17 Dec 2020, verified** (`t-verify.md` §2).

### 1.4 VAT rate history

| From | Rate | Text |
|---|---|---|
| in force before 2016 | 10% | UU 42/2009 Pasal 7(1): *"Tarif Pajak Pertambahan Nilai adalah 10% (sepuluh persen)."* |
| 1 Apr 2022 | 11% | UU HPP, Pasal 7(1)a: *"sebesar 11% (sebelas persen) yang mulai berlaku pada tanggal 1 April 2022"* |
| 1 Jan 2025 | 12% on a base of 11/12, so 11% effective | UU HPP Pasal 7(1)b sets 12% *"paling lambat pada tanggal 1 Januari 2025"*. PMK 131/2024 Pasal 3(1)–(3), for *"penyerahan Jasa Kena Pajak"*, multiplies *"tarif 12% (dua belas persen) dengan Dasar Pengenaan Pajak berupa nilai lain"*, where the other value is *"11/12 (sebelas per dua belas) dari … harga jual, atau penggantian"*. Pasal 6: *"mulai berlaku pada tanggal 1 Januari 2025"* |

Brokers also charge VAT on their own commission at the same effective rate (Ajaib: *"PPN Biaya Broker 12% sesuai perhitungan PMK 131/2024"*).

### 1.5 The levy by period

Per side, as a percentage of trade value. A sale also pays the 0.1% sale tax (§2).

| Period | IDX + KPEI + KSEI | VAT on those | Guarantee fund | Levy |
|---|---|---|---|---|
| 2016-01-01 – 2020-06-17 | 0.030% | 0.0030% (10%) | 0.010% | **0.0430%** |
| 2020-06-18 – 2020-12-17 | 0.030% | 0.0030% | 0.005% | **0.0380%** (`t-verify.md` §2) |
| 2020-12-18 – 2022-03-31 | 0.030% | 0.0030% | 0.010% | **0.0430%** |
| 2022-04-01 onward | 0.030% | 0.0033% (11%, then 12% × 11/12) | 0.010% | **0.0433%** |

IPOT's notice of 30 Mar 2022 confirms that the April 2022 VAT step applied to the levy, though IPOT chose not to pass it on: *"PT Indo Premier Sekuritas memutuskan untuk menyerap kenaikan PPN 1 persen"*.

## 2. The 0.1% sale tax (AC3)

- **Regulation:** PP 41/1994 Pasal 1(2)a: *"0,1% (satu perseribu) dari jumlah bruto nilai transaksi penjualan"*. PP 14/1997 restates the 0.1% (issued and in force 29 May 1997). BPK marks PP 14/1997 *Berlaku*, and no later amendment was found.
- **Levied on:** the gross value of each share sale on the exchange. Buys pay nothing.
- **Collected by:** the exchange, through its members. PP 41/1994 Pasal 2(1): *"Penyelenggara bursa efek wajib memungut … untuk setiap transaksi penjualan saham"*. BCA: *"Dibayarkan ke Bursa sebagai Wajib Pungut"*. The broker deducts it from the sale proceeds.
- **Rate history from 2016-01-01:** 0.1% throughout.
- **Not modelled:** founder shares carry an extra 0.5% of their value at the 1996 year-end. That applies to shares held since before listing, not to shares bought on the exchange.

## 3. Stamp duty

This was not in #38's AC, but it is a real per-day cost, and on small trades it outweighs every rate in §1.

- **Law:** UU 10/2020, in force 1 Jan 2021. Pasal 3(2)e makes *"Dokumen transaksi surat berharga, termasuk Dokumen transaksi kontrak berjangka, dengan nama dan dalam bentuk apa pun"* dutiable, and its elucidation names *"trade confirmation"*. Pasal 5 sets *"tarif tetap sebesar Rp10.000,00 (sepuluh ribu rupiah)"*.
- **Threshold, unverified:** Stockbit and Ajaib both charge it once per day, on the day's trade confirmation, only when the day's total exceeds Rp10,000,000 (Stockbit: *"dengan total nilai transaksi jual, beli, maupun jual dan beli di atas Rp10.000.000"*). Stockbit cites PMK 134/2021, but neither PMK 134/2021 nor UU 10/2020 contains that amount (UU 10/2020's only value threshold is Pasal 3(2)g's Rp5,000,000, for documents acknowledging receipt of money). The threshold's primary source was not found. **Found by T-VERIFY (#41):** it is an exemption in PP 3/2022 Pasal 5 huruf b, in force 12 Jan 2022. From 1 Jan 2021 to 11 Jan 2022 every confirmation was dutiable (`t-verify.md` §3.2).
- **Before 2021:** under the earlier stamp-duty law (UU 13/1985), **unverified**. T-VERIFY (#41) researched it and found no primary text saying whether a trade confirmation was dutiable (`t-verify.md` §3.1).

## 4. Broker fee schedules (AC4)

The three brokers with commission schedules (Ajaib, Stockbit and Indo Premier) are exchange members serving retail clients; BCA Sekuritas is listed for its levy table only. Ajaib's page states *"PT Ajaib Sekuritas Asia berizin dan diawasi oleh Otoritas Jasa Keuangan"*. The OJK licences of Stockbit and Indo Premier were not checked against OJK's register, which does not serve curl.

| Broker | Buy | Sell | Includes the levy? | Includes the sale tax? | Minimum fee | Other | Source |
|---|---|---|---|---|---|---|---|
| Ajaib | 0.1513% | 0.2513% | **yes**: *"Sudah termasuk biaya broker, biaya levy (BEI, KPEI, KSEI) 0,0433%, PPN Biaya Broker 12% sesuai perhitungan PMK 131/2024, dan PPh final untuk transaksi jual 0,1%"* | **yes** (same sentence) | none stated | market orders +0.1% broker fee; forced sales +0.25%; stamp duty Rp10,000 per day above Rp10,000,000 | Ajaib |
| Stockbit | 0.15% | 0.25% | not stated | implied yes: for ETFs, rights and warrants the sell fee is 0.15% and *"fee jual tidak dikenakan PPh"*, so the 0.10-point gap on shares is the sale tax | none stated | a monthly live-data fee for months with Rp20–100 million traded; stamp duty | Stockbit |
| Indo Premier (IPOT) | 0.19% | 0.29% | not stated | not stated (the 0.10-point gap suggests yes) | none stated | the April 2022 VAT increase was absorbed, not passed on | IPOT (30 Mar 2022, a news item on the broker's own site; its fee page did not load with curl) |
| BCA Sekuritas | — | — | the levy table in §1 | yes | — | publishes the levy only: *"belum termasuk komisi transaksi yang dikenakan Anggota Bursa kepada nasabah"* | BCA Sekuritas |

**Reading the all-in quotes.** Ajaib's buy rate, 0.1513%, less the 0.0433% levy leaves 0.108%, which is its commission plus VAT on the commission. Retail brokers quote a single all-in rate per side, so a preset must record what the quote includes rather than adding the levy on top again.

**Rates move over time.** Ajaib's and Stockbit's schedules are today's, and IPOT's rates are as its notice gave them on 30 Mar 2022. A search of the Archive for BCA Sekuritas and Indo Premier fee pages from 2015–2019 found none, so a backtest over 2016 charges today's commission on that year's levy. That is a modelling assumption, not a historical fact.

## 5. Recommended `fees.toml` shape (AC5)

Four tables: the exchange levy, the sale tax and the stamp duty, each effective-dated like the other `data/*.toml` files, and the broker presets. Rates are strings parsed to `Decimal` (spec §4.4), in percent.

**Superseded in part (Shyden, 2026-09-25; #41):** backtests refuse unverified rows, so no `verified = false` row ships. The earliest date every row is verified is 2021-01-01 (`t-verify.md` §5). The `verified` field, the unverified comments below, and the last bullet after the example are research record, not the shipped design. The guarantee-fund window ends on 17 Dec 2020, and the stamp-duty threshold comes from PP 3/2022, from 12 Jan 2022.

```toml
# Exchange-side charges per side, effective-dated (docs/research/t-fees.md §1).
[[levy]]
from = "2016-01-01"
exchange_fee = "0.018"      # IDX
clearing_fee = "0.009"      # KPEI
settlement_fee = "0.003"    # KSEI; probable, unverified before VI-A (§1.2)
guarantee_fund = "0.010"    # KPEI; no VAT
vat = "10"                  # on exchange + clearing + settlement
verified = false

[[levy]]
from = "2020-06-18"
exchange_fee = "0.018"      # IDX
clearing_fee = "0.009"      # KPEI
settlement_fee = "0.003"    # KSEI; probable, unverified before VI-A (§1.2)
guarantee_fund = "0.005"    # KPEI; no VAT; KEP-019/DIR/KPEI/0620, secondary (§1.3)
vat = "10"                  # on exchange + clearing + settlement
verified = false

[[levy]]
from = "2020-12-17"
exchange_fee = "0.018"      # IDX
clearing_fee = "0.009"      # KPEI
settlement_fee = "0.003"    # KSEI; probable, unverified before VI-A (§1.2)
guarantee_fund = "0.010"    # KPEI; no VAT
vat = "10"                  # on exchange + clearing + settlement
verified = false

[[levy]]
from = "2021-01-20"         # KSEI Rule VI-A in force (KEP-0005)
exchange_fee = "0.018"      # IDX
clearing_fee = "0.009"      # KPEI
settlement_fee = "0.003"    # KSEI
guarantee_fund = "0.010"    # KPEI; no VAT
vat = "10"                  # on exchange + clearing + settlement
verified = true

[[levy]]
from = "2022-04-01"
exchange_fee = "0.018"      # IDX
clearing_fee = "0.009"      # KPEI
settlement_fee = "0.003"    # KSEI
guarantee_fund = "0.010"    # KPEI; no VAT
vat = "11"                  # UU HPP; 12% x 11/12 from 2025 is also 11%
verified = true

[[sale_tax]]
from = "2016-01-01"
rate = "0.1"                # PP 41/1994 as amended by PP 14/1997; sales only; unchanged since

[[stamp_duty]]
from = "2021-01-01"
amount_idr = 10000          # UU 10/2020 Pasal 5
per = "day"
above_idr = 10000000        # broker practice; primary source not found (§3)

# Broker presets. An all-in preset says what its quote already contains.
[presets.ajaib]
buy = "0.1513"
sell = "0.2513"
includes = ["levy", "vat", "sale_tax"]
min_fee_idr = 0
checked = "2026-09-25"
note = "check against your broker's fee schedule"

[presets.custom]
buy = "0.15"                # commission only
sell = "0.15"
includes = []               # levy, VAT on commission and sale tax are added
vat_on_commission = true
min_fee_idr = 0
note = "check against your broker's fee schedule"
```

- **Every row carries its own fields.** Each `[[levy]]` row repeats every field, so no row depends on the one before it, and a test asserts that every row is complete. `verified = false` marks a row resting on any unverified or secondary value (§6); the rows from 2021-01-20 are `true`, because every component is verified from that date.
- **Rounding:** compute each component in IDR from the trade value, add them, and round the **total** once, against the trader: a buy's cost up, and a sale's net proceeds down, to the whole rupiah (spec §4.4). How brokers round each line internally is **unverified**. Rounding once keeps the error to under one rupiah per trade, and the direction is always adverse.
- **Presets:** `ajaib`, `stockbit`, `ipot` and `custom` (the example shows two). `ipot`'s `checked` date is its notice's, 2022-03-30. `stockbit` and `ipot` state `includes = ["levy", "vat", "sale_tax"]` as an assumption, since their pages do not say it, and the preset's note says so. The default is `custom`, as spec §9.5 has it now.
- **Minimum fee:** none of the brokers publishes one, so `min_fee_idr = 0`. The field stays so that a user whose broker has one can set it.
- **Stamp duty** is charged per trading day, against settled cash, when that day's buys plus sells exceed the threshold.
- **Historical rows** that are unverified carry `verified = false`, and a backtest that uses them says so in its report, as T-HIST proposes for the rule tables.

## 6. Verdict for M2

| Data | Verified from | Unverified |
|---|---|---|
| IDX fee 0.018% | FY2016–2017; 13 Mar 2020 onward | 2018 – 12 Mar 2020 (no change found) |
| KPEI clearing 0.009% | FY2019 onward | 2016–2018 |
| KSEI settlement 0.003% | FY2019 onward (`t-verify.md` §1) | 2016–2018: 0.003% probable, 0.006% possible (§1.2) |
| Guarantee fund 0.01% | 27 Aug 2015 onward, with 0.005% from 18 Jun to 17 Dec 2020 (`t-verify.md` §2) | — |
| VAT on the levy | 2016 onward (10%, 11%, 12% × 11/12) | — |
| Sale tax 0.1% | 1997 onward | — |
| Stamp duty Rp10,000 | 1 Jan 2021 onward, with the Rp10,000,000 exemption from 12 Jan 2022 (PP 3/2022; `t-verify.md` §3.2) | everything before 2021 |
| Broker commissions | published rates: Ajaib and Stockbit as of 2026-09-25, IPOT as of 30 Mar 2022 | any other date |

**Open for the M2 plan** (decisions, not research gaps):
1. Whether the fees task ships stamp duty in M2, or records it as a known omission. Spec §5.1 now lists it and leaves this to the plan, and §4.3's per-trade `costs(side, gross, on)` cannot charge a per-day amount as written.
2. Whether `stockbit` and `ipot` ship as presets with an assumed `includes` list, or only `ajaib` (whose page states it) plus `custom`.
3. How unverified fee rows interact with T-HIST's open decision on unverified rule rows (`t-hist.md` §6 item 1). One answer for both keeps the report's caveats consistent. **Answered (Shyden, 2026-09-25):** refuse unverified rows. T-VERIFY (#41) then moved the earliest verified date to 2021-01-01 (`t-verify.md` §5).

## Review log

- **Pass 1 (2026-09-25):** a mechanical check of every quote against the extracted source text, the arithmetic in §1.5 and §4, and the §5 TOML parsed with Python 3.12's `tomllib`, all against #38's AC1–AC7. Six findings, all fixed. (1) The source-order note said nothing came from idx.co.id, but Kep-00025 is T-HIST's idx.co.id fallback copy. (2) BCA's date cell gave a date belonging to other pages. (3) The VAT table dated the 10% rate "before 2016", which reads as a start date. (4) §3 called Rp5,000,000 UU 10/2020's only amount, which is true only of value thresholds. (5) The TOML example abbreviated three `[[levy]]` rows while the text required every row complete. (6) The sale-tax row started in 1997, before the backtest scope, from an effective date of PP 41/1994 that was not researched; it now starts on 2016-01-01.
- **Pass 2 (2026-09-25):** a full read of the document and of the spec lines it feeds. Five findings, all fixed. (1) §4 opened "All three brokers" over a four-row table. (2) §1.5 said IPOT's notice showed the April 2022 VAT step reaching clients, while IPOT absorbed it. (3) §4 claimed the Archive holds no 2016–2019 broker schedule, while only two brokers' domains were searched. (4) §5 said the 2022 levy row is unverified "before VI-A took effect", when the gap is VI-A's unknown effective date. (5) §6 item 1 said stamp duty is absent from spec §5.1, which Pass 11 of the spec review has since changed.
- **Pass 3 (2026-09-25):** a re-read of the sources table against the source texts found one error, fixed. KEP-0005 was recorded as in force "on a date set by a later KSEI announcement"; that clause (item 2) covers only five listed fees, and the decision itself is in force from 20 Jan 2021 (item 5). The KSEI rate is therefore verified from 20 Jan 2021: §1.1, §1.2, §5 (a new `2021-01-20` levy row, and `verified = true` from it) and §6 now say so, which supersedes Pass 2's fix (4).
- **Pass 4 (2026-09-25):** a grep for every `VI-A` mention and for the table count found one finding, fixed: §5 introduced "three tables" over four (levy, sale tax, stamp duty, presets).
- **Pass 5 (2026-09-25):** a full read of §1–§4. One finding, fixed: §4 called every broker schedule "today's", while IPOT's rates come from its notice of 30 Mar 2022.
- **Pass 6 (2026-09-25):** a full read of §5–§6. Two findings, fixed: (1) §5 named four presets beside an example showing two, and did not date `ipot`'s rates; (2) §6 called every broker commission "today's", the same error Pass 5 fixed in §4.
- **Pass 7 (2026-09-25):** the mechanical checks again (the §5 TOML parses with `tomllib`: five complete levy rows; the §1.5 and §4 sums; a sweep of this document and the spec for "today", "three brokers" and every `VI-A` mention), then a read against #38's AC1–AC7 one by one. **No findings.** The document is reviewed to zero.
