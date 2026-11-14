+++
id = "income.projection"
title = "Proyeksi, bukan janji"
summary = "Berapa tahun yang dibutuhkan setiap skenario untuk mencapai target pendapatan Anda, dengan asumsi yang dinyatakan."
explains = ["income.projection.costs_ignored"]
module = "income-goal"
position = 6
see_also = ["income.goal", "income.growth"]

+++

Proyeksi menghitung berapa lama waktu yang dibutuhkan agar portofolio Anda membayar target
pendapatan Anda, jika Anda terus menginvestasikan kembali. Perhitungannya berjalan bulan demi bulan
dari kepemilikan Anda hari ini:

- dividen bersih setiap bulan diinvestasikan kembali, dan **jumlah bulanan yang Anda tambahkan**
  juga ditambahkan (diatur di Pengaturan; jika dikosongkan, dihitung 0);
- uang baru itu membeli lebih banyak saham dari kepemilikan yang sama, pada imbal hasil hari ini;
- setahun sekali, dividen tumbuh sesuai laju skenarionya.

Ada tiga skenario:

| Skenario | Pendapatan awal | Pertumbuhan dividen                                 |
| -------- | --------------- | --------------------------------------------------- |
| Pesimis  | run-rate × 0,8  | pertumbuhan terukur atau 0%, mana yang lebih rendah |
| Dasar    | run-rate        | pertumbuhan terukur, paling banyak 5% setahun       |
| Optimis  | run-rate        | pertumbuhan terukur, paling banyak 10% setahun      |

Setiap skenario memberikan **jumlah tahun sampai target**, dibulatkan ke atas ke sepersepuluh
tahun, atau menyatakan bahwa target tidak tercapai dalam 50 tahun. Tidak ada proyeksi dari
portofolio kosong atau dari run-rate nol.

Asumsinya sengaja hati-hati: harga saham tidak pernah naik, dan hanya pendapatan bersih yang
diinvestasikan kembali. **Biaya pembelian tidak dihitung**, yang justru condong ke arah
sebaliknya, dan sebuah catatan menyebutkannya pada setiap proyeksi. Proyeksi ini adalah cara
membandingkan rencana, bukan tanggal yang bisa diandalkan.
