# T-TAX: dividend tax and the reinvestment exemption, from primary documents

**Ticket:** #25 (spec §12, T-TAX). **Researched and accessed:** 2026-09-25. **Feeds:** the `dividend_tax` rule (the protocol in `market.py`, spec §4), `income.py` (the dividend ledger), and the `[tax] dividend_reinvestment_exemption` switch (spec §9).

This is engineering research, not legal or tax advice. Every finding below rests on the text of a regulation unless it is marked **unverified**. Quotes are verbatim in the original language. Every source was downloaded from BPK's legal database (peraturan.bpk.go.id). #25 AC1 names jdih.kemenkeu.go.id or peraturan.go.id. JDIH Kemenkeu returned nothing to a scripted request, while BPK's JDIH is an official state legal-documentation database. BPK's copies of both PMKs carry the `jdih.kemenkeu.go.id` footer on their pages, so they are the Ministry's own documents. Those PDFs are scans with an OCR text layer, so the quotes below repair obvious OCR errors in spacing and letters (for example `Pasal36` → `Pasal 36` and `asurans1` → `asuransi`). The one repair that changes meaning was checked against the page image: in PP 55/2022 Pasal 9(2)(l) the OCR reads `huruf a2`, and the scan of page 13 reads `huruf a,`.

## Sources

| Short name | Document | Dated | In force | BPK page (Details) · PDF (Download) |
|---|---|---|---|---|
| **UU PPh** | UU 7/1983 tentang Pajak Penghasilan, as amended by UU 36/2008 (the fourth amendment) | 2008 | | Details/39704 · Download/29283 |
| **UU HPP** | UU 7/2021 tentang Harmonisasi Peraturan Perpajakan (amends UU PPh Pasal 4 and 17, among others) | 29 Oct 2021 | on promulgation, 29 Oct 2021 (some provisions take effect later) | Details/185162 · Download/178620 |
| UU Cipta Kerja | Perppu 2/2022 tentang Cipta Kerja, enacted as law by UU 6/2023 | 2022 / 2023 | | Details/234926 · Download/287447 (Perppu); Details/246523 (UU 6/2023) |
| **PP 19/2009** | PP 19/2009 tentang PPh atas Dividen yang Diterima atau Diperoleh WP Orang Pribadi Dalam Negeri | 2009 | 1 Jan 2009 | Details/4933 · Download/36260 |
| **PP 55/2022** | PP 55/2022 (implements UU HPP in the income tax field) | 20 Dec 2022 | 20 Dec 2022 | Details/233488 · Download/284096 |
| PP 20/2026 | PP 20/2026, amending PP 55/2022 | 22 Apr 2026 | | Details/349415 · Download/413101 |
| PP 9/2021 | PP 9/2021 (the Cipta Kerja income tax regulation that first implemented the exemption UU 11/2020 created) | 2021 | partially revoked | Details/161839 · Download/244291 |
| **PMK 18/2021** | PMK 18/PMK.03/2021, implementing UU 11/2020 (Cipta Kerja) for income tax | 2021 | | Details/162653 · Download/155338 and 155339 |
| **PMK 81/2024** | PMK 81 Tahun 2024 (tax administration, consolidating earlier PMKs) | set 14 Oct 2024, promulgated 18 Oct 2024 | **1 Jan 2025** | Details/306614 · Download/366884 |

All URLs have the form `https://peraturan.bpk.go.id/Details/<id>` and `https://peraturan.bpk.go.id/Download/<id>/<file>.pdf`.

## 1. What the tax is, and the rate (AC5 background)

**The rate is 10%, final.** UU PPh Pasal 17(2c), as the Pasal 17 restated in full by UU HPP gives it:

> (2c) Tarif yang dikenakan atas penghasilan berupa dividen yang dibagikan kepada Wajib Pajak orang pribadi dalam negeri adalah paling tinggi sebesar 10% (sepuluh persen) dan bersifat final.
> (2d) Ketentuan lebih lanjut mengenai besarnya tarif sebagaimana dimaksud pada ayat (2c) diatur dengan Peraturan Pemerintah.

UU HPP's amending instruction changes Pasal 17 ayat (1), (2), (2b) and (3), deletes (2a) and inserts (2e). **(2c) is carried over unchanged** from UU 36/2008. The government regulation that sets the figure is PP 19/2009 Pasal 1:

> Penghasilan berupa dividen yang diterima atau diperoleh Wajib Pajak orang pribadi dalam negeri dikenai Pajak Penghasilan sebesar 10% (sepuluh persen) dan bersifat final.

PP 19/2009 Pasal 2 has the payer withholding the tax (*"dilakukan melalui pemotongan oleh pihak yang membayar"*). **For domestic dividends to resident individuals, that is no longer how it works** (§2 below).

**Unverified:** PP 19/2009 is still in force. BPK's status block reads *"Belum Tersedia"* (not yet available): it records no amendment or revocation, and no document read for this ticket revokes it. The 10% ceiling in UU PPh 17(2c) is verified, and the exact 10% rests on PP 19/2009 alone.

## 2. The exemption, and that nothing is withheld (AC1)

UU HPP puts the exemption in UU PPh Pasal 4 ayat (3) huruf f:

> f. dividen atau penghasilan lain dengan ketentuan sebagai berikut: 1. dividen yang berasal dari dalam negeri yang diterima atau diperoleh Wajib Pajak: a) orang pribadi dalam negeri sepanjang dividen tersebut diinvestasikan di wilayah Negara Kesatuan Republik Indonesia dalam jangka waktu tertentu; dan/atau b) badan dalam negeri;

PP 55/2022 Pasal 9(2) repeats that condition and adds the payment mechanics:

> a. dividen yang berasal dari dalam negeri yang diterima atau diperoleh Wajib Pajak: 1. orang pribadi dalam negeri sepanjang dividen tersebut diinvestasikan di wilayah Negara Kesatuan Republik Indonesia dalam jangka waktu tertentu; dan/atau 2. badan dalam negeri;
> j. dividen yang dikecualikan dari objek Pajak Penghasilan sebagaimana dimaksud dalam huruf a dan huruf b merupakan dividen yang dibagikan berdasarkan rapat umum pemegang saham atau dividen interim sesuai dengan ketentuan peraturan perundang-undangan;
> l. dividen yang berasal dari dalam negeri yang diterima atau diperoleh Wajib Pajak orang pribadi dalam negeri atau Wajib Pajak badan dalam negeri sebagaimana dimaksud dalam huruf a, tidak dipotong Pajak Penghasilan;
> m. dalam hal Wajib Pajak orang pribadi dalam negeri yang tidak memenuhi ketentuan investasi sebagaimana dimaksud dalam huruf a angka 1, atas dividen yang berasal dari dalam negeri yang diterima atau diperoleh Wajib Pajak orang pribadi dalam negeri terutang Pajak Penghasilan pada saat dividen diterima atau diperoleh; dan
> n. Pajak Penghasilan yang terutang sebagaimana dimaksud dalam huruf m wajib disetor sendiri oleh Wajib Pajak orang pribadi dalam negeri sesuai dengan ketentuan peraturan perundang-undangan.

**So a resident individual receives an IDX dividend GROSS.** The issuer withholds nothing (huruf l). If the investor does not meet the investment condition, the 10% is owed **as of the day the dividend was received** (huruf m), and the investor **pays it themselves** (huruf n). The spec's "10% final withholding tax" (§3.5) is therefore wrong for this case, and so is §5's "cash net of dividend tax is credited" when read as describing what the broker pays.

PMK 18/2021 Pasal 15(1) and Pasal 16 give the same condition and the rule for a **partial** reinvestment:

> Pasal 15 (1) Dividen yang berasal dari dalam negeri … yang diterima atau diperoleh Wajib Pajak orang pribadi dalam negeri dikecualikan dari objek PPh dengan syarat harus diinvestasikan di wilayah Negara Kesatuan Republik Indonesia dalam jangka waktu tertentu.
> Pasal 16 (1) Dalam hal Dividen … diinvestasikan di wilayah Negara Kesatuan Republik Indonesia kurang dari jumlah Dividen yang diterima atau diperoleh Wajib Pajak orang pribadi dalam negeri, Dividen yang diinvestasikan dikecualikan dari pengenaan PPh. (2) Selisih dari Dividen yang diterima atau diperoleh dikurangi dengan Dividen yang diinvestasikan sebagaimana dimaksud pada ayat (1) dikenai PPh sesuai dengan ketentuan peraturan perundang-undangan.

The exemption is **pro rata**: whatever part of the dividend is invested is exempt, and only the rest is taxed at 10%.

## 3. The deadline, with a worked example (AC2)

PMK 18/2021 Pasal 36(1):

> (1) Investasi sebagaimana dimaksud dalam Pasal 35 dilakukan paling lambat: a. akhir bulan ketiga, untuk Wajib Pajak orang pribadi; atau b. akhir bulan keempat, untuk Wajib Pajak badan, setelah Tahun Pajak berakhir, untuk Tahun Pajak diterima atau diperolehnya Dividen atau penghasilan lain.

**The deadline counts from the end of the tax year in which the dividend was received, not from the day it was received.** For an individual it is the end of the third month after that tax year ends. An individual's tax year is normally the calendar year, so every dividend received in a given year has the same deadline: 31 March of the next year. The definition of *Tahun Pajak* is in UU KUP, which was not read for this ticket, so the calendar-year assumption is **unverified**.

The tax, if it falls due, is owed from the day of receipt (PP 55/2022 Pasal 9(2)(m); PMK 81/2024 Pasal 372) and is payable by the 15th of the next month (PMK 81/2024 Pasal 373, §5 below). **The deadline to pay therefore comes before the deadline to invest.** An investor who pays nothing and then misses the investment deadline owes the tax plus sanctions under UU KUP (Pasal 373(4)). How UU KUP computes them is outside this ticket.

**Worked example (a 2026 dividend).** A resident individual holds a stock whose RUPS-declared dividend pays Rp1,000,000 on 20 May 2026.

| Step | Date | Rule |
|---|---|---|
| Dividend received **gross**: Rp1,000,000, nothing withheld | 20 May 2026 | PP 55/2022 Pasal 9(2)(l) |
| If the investor does not intend to reinvest: self-pay 10% = Rp100,000 and file an SPT Masa PPh Unifikasi | by **15 Jun 2026** | PMK 81/2024 Pasal 373(1)–(3) |
| Last day to make the qualifying investment | **31 Mar 2027** | PMK 18/2021 Pasal 36(1)(a) |
| The investment is held at least 3 tax years, counted from tax year 2026: 2026, 2027 and 2028 | through **31 Dec 2028** | PMK 18/2021 Pasal 36(2) |
| Investment realisation report through the Portal Wajib Pajak, once a year | by **31 Mar 2027**, **31 Mar 2028** and **31 Mar 2029** | PMK 81/2024 Pasal 374(3) |
| If Rp600,000 is invested and Rp400,000 is not: 10% of Rp400,000 = Rp40,000 is owed, as of 20 May 2026 | | PMK 18/2021 Pasal 16 |

The holding end date and the three report dates are **this document's reading** of "paling singkat selama 3 (tiga) Tahun Pajak terhitung sejak Tahun Pajak Dividen … diterima" and "sampai dengan tahun ketiga sejak Tahun Pajak diterima". Both count from the tax year of receipt, which includes 2026 itself. No official worked example was found to confirm the reading, so it is **unverified**. A stricter reading counts the three tax years from the year of the investment, which pushes the holding for a March 2027 purchase to 31 Dec 2029. The engine takes the stricter reading (§7), because a longer holding can only understate the exemption.

## 4. The minimum holding, and an early sale (AC3)

PMK 18/2021 Pasal 36(2) and (3):

> (2) Investasi sebagaimana dimaksud dalam Pasal 35 dilakukan paling singkat selama 3 (tiga) Tahun Pajak terhitung sejak Tahun Pajak Dividen atau penghasilan lain diterima atau diperoleh.
> (3) Investasi sebagaimana dimaksud dalam Pasal 35 tidak dapat dialihkan, kecuali ke dalam bentuk investasi sebagaimana dimaksud dalam Pasal 35.

- **The minimum holding is 3 tax years**, counted from the tax year the dividend was received.
- **Selling and buying another qualifying investment is allowed** (ayat 3). Selling one IDX stock and buying another keeps the exemption. Selling and taking the money out of the qualifying forms does not.
- **A breach makes the tax due as of the original receipt date.** PMK 81/2024 Pasal 372: *"Dividen yang tidak memenuhi ketentuan sebagaimana dimaksud dalam Pasal 370 … terutang Pajak Penghasilan saat Dividen … diterima atau diperoleh."* The investor then owes the 10%, and UU KUP sanctions apply (PMK 81/2024 Pasal 373(4)). How they are computed is outside this ticket.

## 5. Qualifying investments and reporting (AC4)

**Qualifying forms.** PMK 18/2021 Pasal 34 lists them (huruf a–l), and Pasal 35(1) says which sit in the financial markets:

> Pasal 35 (1) Investasi sebagaimana dimaksud dalam Pasal 34 huruf a sampai dengan huruf e dan huruf l, ditempatkan pada instrumen investasi di pasar keuangan: a. efek bersifat utang, termasuk medium term notes; b. sukuk; **c. saham**; d. unit penyertaan reksa dana; e. efek beragun aset; f. unit penyertaan dana investasi real estat; g. deposito; h. tabungan; i. giro; j. kontrak berjangka yang diperdagangkan di bursa berjangka di Indonesia; dan/atau k. instrumen investasi pasar keuangan lainnya termasuk produk asuransi yang dikaitkan dengan investasi, perusahaan pembiayaan, dana pensiun, atau modal ventura, yang mendapatkan persetujuan Otoritas Jasa Keuangan. *(Bold added.)*

**Buying IDX shares qualifies** (huruf c, *saham*). Pasal 35(2) covers the forms outside the financial markets: infrastructure PPP, priority real-sector equity, land and buildings (not subsidised property, ayat 5), direct investment in Indonesian companies, gold bars of 99.99% purity produced in Indonesia with SNI and/or LBMA certification (ayat 6–7), the sovereign investment authority, and loans to micro and small businesses.

**Unverified:** whether cash left in the investor's RDN (the broker-linked bank account) counts as *tabungan* or *giro* at a *bank persepsi* (Pasal 34 huruf d, Pasal 35(1) huruf h–i). Nothing read for this ticket says either way, so the engine treats uninvested cash as **not** qualifying.

**Reporting.** PMK 81/2024 Pasal 370(1) makes the report a condition of the exemption, not a formality:

> (1) Pengecualian dari objek Pajak Penghasilan atas Dividen yang berasal dari dalam negeri yang diterima atau diperoleh Wajib Pajak orang pribadi dalam negeri dilaksanakan dengan memenuhi: a. kriteria bentuk investasi, tata cara investasi, dan jangka waktu investasi sesuai dengan ketentuan peraturan perundang-undangan mengenai Pajak Penghasilan; dan b. kewajiban penyampaian laporan realisasi investasi.

Pasal 374:

> (1) Wajib Pajak sebagaimana dimaksud dalam Pasal 370 dan Pasal 371 harus menyampaikan laporan realisasi investasi. (2) Penyampaian laporan sebagaimana dimaksud pada ayat (1) dilakukan secara elektronik melalui Portal Wajib Pajak. (3) Wajib Pajak wajib menyampaikan laporan sebagaimana dimaksud pada ayat (1): a. secara berkala paling lambat akhir bulan ketiga untuk Wajib Pajak orang pribadi … setelah Tahun Pajak berakhir; dan b. disampaikan sampai dengan tahun ketiga sejak Tahun Pajak diterima atau diperolehnya Dividen atau penghasilan lain.

When the condition is not met, the tax is paid through Pasal 373:

> (1) Pajak Penghasilan yang terutang sebagaimana dimaksud dalam Pasal 372 atas Dividen yang berasal dari dalam negeri, wajib disetor sendiri oleh Wajib Pajak orang pribadi dalam negeri dengan tarif sesuai dengan ketentuan peraturan perundang-undangan. (2) Pajak Penghasilan sebagaimana dimaksud pada ayat (1) disetor paling lama tanggal 15 (lima belas) bulan berikutnya setelah Masa Pajak Dividen diterima atau diperoleh. (3) Wajib Pajak orang pribadi yang melakukan pembayaran Pajak Penghasilan yang terutang sebagaimana dimaksud pada ayat (1) wajib menyampaikan Surat Pemberitahuan Masa Pajak Penghasilan Unifikasi. (4) Wajib Pajak yang tidak memenuhi ketentuan sebagaimana dimaksud pada ayat (1), ayat (2), dan ayat (3) dikenai sanksi sebagaimana diatur dalam Undang-Undang Ketentuan Umum dan Tata Cara Perpajakan.

**Not researched (out of scope):** whether the dividend must also appear in the annual individual return (SPT Tahunan).

## 6. Amendments since 2021, and what is in force on 2026-09-25 (AC5)

| When | Instrument | Effect on this rule |
|---|---|---|
| 2009 | UU 36/2008 Pasal 17(2c); PP 19/2009 | 10% final, withheld by the payer |
| 2021 | UU 11/2020 (Cipta Kerja); PP 9/2021; PMK 18/2021 | The reinvestment exemption is created. PMK 18/2021 Pasal 15–16 and 33–41 give its conditions and procedure |
| 29 Oct 2021 | **UU HPP** (UU 7/2021) | Restates UU PPh Pasal 4(3)(f), which now holds the exemption, and restates Pasal 17 with (2c) unchanged. Pasal 32C huruf e hands *"kriteria, jangka waktu, dan perubahan batasan dividen yang diinvestasikan"* to a regulation (*"diatur dengan atau berdasarkan Peraturan Pemerintah"*) |
| 20 Dec 2022 | **PP 55/2022** | Implements UU HPP. Revokes Pasal 2A of PP 94/2010 as PP 9/2021 inserted it (the earlier dividend provision). Pasal 9(2) adds **no withholding** for resident individuals (huruf l) and **self-payment** when the condition is missed (huruf m–n) |
| 2022 / 2023 | Perppu 2/2022 → UU 6/2023 (Cipta Kerja) | Pasal 111 amends only UU PPh **Pasal 2 and Pasal 26** (Pasal 26 covers non-residents). **No change** for residents' domestic dividends |
| 1 Jan 2025 | **PMK 81/2024** | Its revocation list (item 35) revokes *"Pasal 37 sampai dengan Pasal 41 … Peraturan Menteri Keuangan Nomor 18/PMK.03/2021"*, the old procedure. **Pasal 15–16 and 33–36 are not on the list and remain.** Pasal 370–374 replace the procedure: a report through the Portal Wajib Pajak, and self-payment by the 15th |
| 22 Apr 2026 | PP 20/2026 (amends PP 55/2022) | A case-insensitive search of its text finds "dividen" on 0 lines and "pasal" on 41 (the known positive). **No change** |

**In force on 2026-09-25:** UU PPh Pasal 4(3)(f) and 17(2c) as UU HPP gives them. PP 55/2022 Pasal 9(2), as amended by PP 20/2026, which does not touch it. PP 19/2009 Pasal 1 for the rate (**unverified**, §1). PMK 18/2021 Pasal 15–16 and 33–36. PMK 81/2024 Pasal 370–374.

**Unverified:** that nothing after PMK 81/2024 revoked PMK 18/2021 Pasal 15–16 or 33–36. BPK's status block for PMK 18/2021 lists partial revocations by PMK 17/2025 (Pasal 108) and PMK 177/PMK.03/2022 (Pasal 107 and 114). **It omits PMK 81/2024's revocation**, which PMK 81/2024's own text states, so that status block is incomplete. JDIH Kemenkeu's page for PMK 18/2021 returned nothing to a scripted request. A web search for a 2025–2026 revocation of these articles found none.

**Also unverified:** that a dividend is "received" (*diterima atau diperoleh*) on its **pay date**. UU HPP delegates *"penetapan saat diperolehnya dividen"* to a government regulation, and that text was not read for this ticket. The engine uses the pay date.

## 7. Verdict for the engine (AC6, AC7)

**The engine can model the exemption from data it holds, as an estimate.** Everything that makes it real is the investor's own paperwork.

The engine can model, from its dividend ledger, fills and holdings:

1. **Gross receipt.** Credit the full dividend on the pay date. Nothing is withheld (PP 55/2022 9(2)(l)).
2. **The deadline.** 31 March of the year after the pay-date year (PMK 18/2021 36(1)(a)).
3. **Qualifying reinvestment.** IDX share purchases made with dividend cash by that deadline count (Pasal 35(1)(c)). The exemption is pro rata (Pasal 16). Counting only purchases paid from the tagged dividend cash is a modelling choice: the text does not say whether any purchase counts, so this is **unverified**.
4. **The holding.** The reinvested amount must stay in shares through 31 December of the third tax year counted from the year of the qualifying purchase. That is the stricter reading of Pasal 36(2) (§3), and it is the same date whenever the purchase falls in the year of receipt. A sell followed by a buy of another stock keeps it (Pasal 36(3)). The conservative model treats the claim as broken if the portfolio's share holdings at cost fall below the amount the claim protects. Money waiting in the T+2 gap between a sell and the next buy is a grey area (**unverified**, §5).
5. **A broken claim.** 10% of the unprotected amount becomes a tax liability dated to the original pay date.

These stay outside the engine and are the investor's paperwork:
- The self-payment by the 15th and the SPT Masa PPh Unifikasi (PMK 81/2024 373).
- The annual realisation reports through the Portal Wajib Pajak (374), which are a **condition** of the exemption (370(1)(b)). The engine cannot know whether they were filed.
- Any UU KUP interest or sanctions.
- Qualifying investments held outside the steadyhand portfolio: a deposit, SBN or gold elsewhere would also qualify, and the engine cannot see them.

**Decision for the switch.** `dividend_reinvestment_exemption` **stays default-off**, as AC7 requires. With the switch off, the engine books 10% of every dividend as tax on the pay date. That matches an investor who self-pays by the 15th, and it can only understate income. With the switch on, the engine applies items 1–5 and labels the result as an estimate that depends on the investor filing the reports. The rule is now confirmed from primary text, so an operator may turn it on. The remaining unverified items (§1, §3, §5, §6) are the reasons the default stays conservative.

**Consequence for the design (M2/M4 plans):** the spec's `dividend_tax(gross, reinvested_by_deadline: bool, on)` cannot express the holding requirement or a partial or broken claim. The M4 plan should model each dividend's exemption as a ledger entry: amount received, amount reinvested by the deadline, amount still protected, and the protection end date. `dividend_tax` would then read from that entry rather than take a bool.

## Review log

- **Pass 1 (2026-09-25):** mechanical checks: every AC (1–7) maps to a section (§2 AC1; §3 AC2; §4 AC3; §5 AC4; §6 AC5; §7 AC6 and AC7). A script located 24 of 24 quoted fragments in the extracted source texts (normalised for OCR), and its negative control was correctly reported missing. Every BPK Details and Download id came from a BPK page or a search result, not from memory. Findings, all fixed: (1) the WIP notes gave PMK 81/2024's in-force date as 31 Dec 2024, and the text says *"mulai berlaku pada tanggal 1 Januari 2025"*; (2) the OCR of PP 55/2022 9(2)(l) reads `huruf a2`, which would restrict it to corporates, and the page scan reads `huruf a,`; (3) BPK's PMK 18/2021 status block omits PMK 81/2024's revocation, so it is not evidence of what remains, and PMK 81/2024's own list is cited instead; (4) the UU HPP delegation is now quoted from Pasal 32C huruf e; (5) the PP 20/2026 counts now state the case-insensitive search that produced them; (6) the calendar-year tax year rests on UU KUP, which was not read, so it is marked unverified.
- **Pass 2 (2026-09-25):** full read. 8 findings, all fixed: (1) the doc named `rules.py` for `dividend_tax`, which is a protocol in `market.py`; (2) UU HPP's in-force note did not say that some provisions take effect later; (3) PP 9/2021 was said to have "first set out" an exemption that UU 11/2020 created; (4) twice, the doc said the UU KUP sanctions run from the 15th, which is inference, and now says only that they apply; (5) §3 promised a conservative engine choice, while §7 and the spec used the lenient reading of the holding period, and both now use the stricter reading; (6) the bold on *saham* inside a verbatim quote is now marked as added; (7) counting only purchases made from dividend cash is now labelled a modelling choice and unverified; (8) the pass 1 log said the quotes were found "by grep", when a normalising script found them.
- **Pass 3 (2026-09-25):** mechanical checks re-run (24 of 24 quotes, with the negative control missing; no stale phrasing outside this log), then a full read. 1 finding, fixed: AC1 names jdih.kemenkeu.go.id or peraturan.go.id, and the doc did not say why BPK's copies were used. It now does, and it notes that the PMK copies carry the Ministry's footer.
- **Pass 4 (2026-09-25):** mechanical checks re-run (24 of 24 quotes with the negative control missing; every AC tag present), then a full read. **0 findings. Loop closed.**
