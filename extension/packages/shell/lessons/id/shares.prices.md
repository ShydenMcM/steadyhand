+++
id = "shares.prices"
title = "Harga, dan berapa nilai portofolio Anda"
summary = "Bagaimana harga penutupan sebuah saham dan kepemilikan Anda menjumlah menjadi nilai portofolio Anda."
explains = []
module = "shares-and-dividends"
position = 2
see_also = ["shares.cost_basis", "costs.trading"]
+++

Sebuah saham punya banyak harga dalam sehari. Pelajaran-pelajaran ini memakai beberapa di antaranya.

- **Harga penutupan.** Harga terakhir sebuah saham pada hari bursa terakhir. Panel mencatat harga
  penutupan setiap saham dari halaman portofolio atau daftar pantauan yang dibaca setelah
  penutupan pasar, dan menilai apa yang Anda pegang dengan harga itu.
- **Nilai transaksi.** Jumlah lembar yang diperdagangkan dikali harganya, sebelum biaya apa pun.
  Membeli 2 lot, yaitu 200 lembar, Saham A di harga 1.000 berarti nilai transaksi 200.000.

Dari situ, steadyhand menghitung berapa nilai portofolio Anda setiap hari:

- **Nilai kepemilikan.** Setiap saham yang Anda pegang, dikali harga penutupannya, lalu
  dijumlahkan.
- **Nilai portofolio.** Kas Anda ditambah nilai kepemilikan Anda. Kas itu termasuk uang hasil
  penjualan yang belum masuk ke rekening Anda.

Broker Anda mungkin menampilkan angka yang lebih besar sebagai kas yang tersedia untuk membeli.
steadyhand hanya membelanjakan kas yang benar-benar ada, sehingga order yang diberikannya tidak pernah berjumlah lebih dari yang dimiliki portofolio.

Nilai portofolio bukanlah uang di tangan Anda. Nilai itu adalah jumlah yang akan Anda dapat jika saham-saham itu dijual pada harga penutupan hari itu, sebelum biaya menjualnya, dan harga besok bisa lebih rendah.
