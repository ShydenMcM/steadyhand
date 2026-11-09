+++
id = "idx.ticks"
title = "Fraksi harga: langkah pergerakan harga"
summary = "Harga di BEI bergerak dalam langkah tetap, dan langkahnya lebih besar untuk saham yang lebih mahal."
explains = []
module = "how-idx-works"
position = 2
see_also = ["idx.lots", "idx.auto_reject"]

+++

Harga saham tidak bisa berupa sembarang angka. Harga bergerak dalam langkah tetap yang disebut
**fraksi harga** (tick), dan besar langkahnya bergantung pada harga:

| Harga                           | Fraksi |
| ------------------------------- | ------ |
| di bawah Rp200                  | Rp1    |
| Rp200 sampai di bawah Rp500     | Rp2    |
| Rp500 sampai di bawah Rp2.000   | Rp5    |
| Rp2.000 sampai di bawah Rp5.000 | Rp10   |
| Rp5.000 ke atas                 | Rp25   |

Jadi saham di harga Rp4.990 bisa ditawarkan di Rp4.990 atau Rp5.000, tetapi tidak di Rp4.995, dan
saham di harga Rp5.000 naik berikutnya ke Rp5.025, bukan Rp5.010. Besar langkahnya ditentukan oleh
harga order itu sendiri.

Langkah-langkah ini tidak berubah setidaknya sejak Maret 2020. steadyhand menyimpannya, beserta
tanggalnya, dalam berkas data, bukan dalam kodenya, sehingga perubahan aturan cukup berupa
perubahan data.
