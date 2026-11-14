+++
id = "risk.limits"
title = "Batas pengaman yang diterapkan steadyhand"
summary = "Batas-batas yang memangkas atau menghentikan order sebuah strategi, apa pun yang ingin dilakukan strategi itu."
explains = ["risk.halt.daily_loss", "risk.halt.drawdown", "limit.weight.full", "limit.weight.cut", "limit.min_lots", "limit.cash.short", "limit.cash.cut"]
module = "risk"
position = 3
see_also = ["risk.drawdown"]

+++

Order dari setiap strategi melewati batas-batas yang sama sebelum dipasang. Setiap batas, kecuali
hanya kas, bisa diubah di Pengaturan. Inilah nilai bawaannya:

- **Hanya kas.** Tidak ada pinjaman dan tidak ada short selling. Pembelian yang membutuhkan lebih
  banyak kas yang sudah diselesaikan daripada yang Anda miliki dipangkas atau dibuang.
- **Paling banyak 10% pada satu saham.** Pembelian yang akan membuat satu saham melebihi 10% dari
  nilai portofolio dipangkas kembali ke 10%, dan tidak dipasang sama sekali jika saham itu sudah
  mencapainya.
- **Pembelian terkecil.** Pembelian yang lebih kecil dari jumlah lot minimum tidak dipasang.
- **Batas kerugian harian.** Jika portofolio turun 5% dalam satu hari, strategi **berhenti**:
  tidak ada order baru yang dipasang sampai Anda melanjutkannya.
- **Batas drawdown.** Jika portofolio turun 25% di bawah titik tertingginya, strategi berhenti
  dengan cara yang sama.

Berhenti bukan berarti menjual. Kepemilikan tetap di tempatnya; strategi hanya berhenti menambah
order sampai Anda melihat apa yang terjadi dan memilih untuk melanjutkan.

Batas-batas ini mengurangi sebagian risiko. Batas-batas ini tidak menghilangkannya: portofolio
masih bisa kehilangan sebagian besar nilainya, dan batas-batas itu bertindak pada harga penutupan
hari itu, setelah penurunannya terjadi.
