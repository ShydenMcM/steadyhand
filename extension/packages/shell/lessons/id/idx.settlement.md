+++
id = "idx.settlement"
title = "Penyelesaian: kapan uang dan saham berpindah tangan"
summary = "Transaksi di BEI diselesaikan dua hari bursa setelah dilakukan, jadi kas dari penjualan hanya bisa dibelanjakan setelah itu."
explains = []
module = "how-idx-works"
position = 5
see_also = ["idx.lots"]

+++

Saat order Anda terisi, transaksinya langsung disepakati, tetapi uang dan sahamnya berpindah
belakangan. Di BEI hal itu terjadi pada hari bursa kedua setelah transaksi, yang disebut **T+2**.
Penjualan pada hari Senin diselesaikan pada hari Rabu, dan penjualan pada hari Jumat diselesaikan
pada hari Selasa, bila tidak ada hari libur di antaranya.

Karena itu steadyhand mencatat kas dalam dua bagian:

- **Kas yang sudah diselesaikan** sudah masuk dan bisa dibelanjakan.
- **Kas yang belum diselesaikan** adalah uang hasil penjualan yang belum masuk.

Hanya kas yang sudah diselesaikan yang dibelanjakan untuk pembelian baru. Jika sebuah strategi
menjual satu saham untuk membeli saham lain, pembeliannya mungkin harus menunggu sampai kas hasil
penjualan diselesaikan.

Nilai portofolio menghitung keduanya, karena uang yang belum diselesaikan adalah milik Anda: uang
itu hanya sedang dalam perjalanan.
