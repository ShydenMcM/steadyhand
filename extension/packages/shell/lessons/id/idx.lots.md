+++
id = "idx.lots"
title = "Lot: saham dijual per seratus lembar"
summary = "Di Bursa Efek Indonesia, Anda membeli dan menjual saham dalam lot berisi 100 lembar."
explains = []
module = "how-idx-works"
position = 1
see_also = ["idx.ticks"]

+++

Di Bursa Efek Indonesia (BEI), saham diperdagangkan dalam **lot**. Satu lot berisi 100 lembar
saham, dan order di pasar reguler harus dalam lot utuh: 100, 200, atau 1.000 lembar, tidak pernah 150.

Jadi pembelian terkecil sebuah saham adalah satu lot. Pada harga Rp4.000 per lembar, satu lot
berharga Rp400.000 sebelum biaya.

Hal ini paling terasa saat portofolio masih kecil. Jika sebuah strategi menginginkan saham itu
senilai Rp300.000, ia tidak bisa membelinya: jumlah terdekat adalah nol atau Rp400.000. steadyhand
selalu membulatkan rencana pembelian **ke bawah** ke lot utuh, dan membuang order yang lebih kecil
dari satu lot, sehingga sebagian kas bisa tersisa tanpa dibelanjakan.
