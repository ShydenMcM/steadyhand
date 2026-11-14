+++
id = "orders.not_tradable"
title = "Mengapa sebuah saham tidak diperdagangkan pada suatu hari"
summary = "Alasan sebuah saham tidak ikut dibeli atau dijual pada suatu hari, apa pun keinginan strateginya."
explains = ["trade.not_in_universe", "trade.not_held", "trade.excluded", "trade.frozen"]
module = "using-steadyhand"
position = 2
see_also = ["idx.special_monitoring", "idx.universe"]
+++

Setiap hari saran, steadyhand lebih dulu menentukan saham mana yang bisa dibeli dan mana yang
bisa dijual. Sebuah strategi tetap bisa meminta saham lain, tetapi order itu tidak diberikan, dan
panel menyebutkan alasannya:

- **Tidak ada di semesta.** Hanya saham dalam semesta yang Anda cantumkan di Pengaturan yang bisa
  dibeli.
- **Tidak dipegang.** Anda hanya bisa menjual apa yang Anda miliki: tidak ada short selling.
- **Dikecualikan.** Saham itu ada di daftar pengecualian Anda di Pengaturan, jadi
  saham itu tidak dibeli maupun dijual.
- **Dibekukan.** Halaman notasi khusus broker Anda menunjukkan saham itu disuspensi atau berada di
  Papan Pemantauan Khusus. Saham itu tidak dibeli maupun dijual sampai tandanya hilang.

Saham yang tidak ikut pada satu hari bisa diperdagangkan lagi pada hari lain sesudahnya, begitu alasannya hilang.
