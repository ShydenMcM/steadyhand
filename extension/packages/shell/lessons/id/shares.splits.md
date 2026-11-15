+++
id = "shares.splits"
title = "Pemecahan saham"
summary = "Pemecahan saham mengubah berapa lembar yang Anda pegang dan harga per lembarnya, tanpa mengubah nilai kepemilikannya."
explains = ["corporate.split.fraction_dropped", "corporate.split.order_cancelled"]
module = "shares-and-dividends"
position = 5
see_also = ["shares.cost_basis"]
+++

Perusahaan bisa **memecah** sahamnya (stock split). Dalam pemecahan 5 banding 1, setiap lembar yang
Anda pegang menjadi lima, dan harga per lembarnya turun menjadi kira-kira seperlimanya. Anda
memiliki bagian perusahaan yang sama seperti sebelumnya.

**Penggabungan saham** (reverse split) berlaku sebaliknya: dalam penggabungan 1 banding 5, setiap
lima lembar menjadi satu.

**Saat pecahan lembar dibuang.** Penggabungan saham bisa menyisakan pecahan: 1.203 lembar dalam
penggabungan 1 banding 5 menjadi 240,6 lembar. Saham tidak bisa dipegang sebagian, jadi Anda
menyimpan 240 dan sisa 0,6 lembar tertinggal. Di rekening sungguhan, bagian itu mungkin dibayarkan
kepada Anda secara tunai, yang disebut cash in lieu. steadyhand tidak memodelkan pembayaran itu:
pecahannya dibuang dan hal itu disebutkan dalam sebuah catatan, sehingga laporan menunjukkan
sedikit lebih kecil daripada rekening sungguhan.

Order yang sudah diantrekan untuk saham yang pemecahannya berlaku hari itu dibatalkan: order itu
dihitung untuk jumlah lembar yang lama, jadi strategi memutuskan lagi setelah pemecahan.
