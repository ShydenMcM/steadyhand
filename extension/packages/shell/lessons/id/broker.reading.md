+++
id = "broker.reading"
title = "Membaca broker Anda"
summary = "Halaman broker mana yang dibaca steadyhand, kapan sebuah pembacaan dihitung, dan apa yang diminta panel bila ada yang kurang."
explains = ["missing.page", "missing.history"]
module = "using-steadyhand"
position = 1
see_also = ["idx.sessions", "risk.returns"]
+++

steadyhand hanya mengetahui apa yang ditunjukkan halaman broker Anda. Dengan panel samping terbuka
di samping situs web broker Anda, setiap halaman yang Anda buka dibaca dan dicatat, dan "Baca
halaman ini" membaca ulang halaman yang sedang Anda buka. Tidak ada yang dibaca atau dicatat
selama panel tertutup.

Halaman yang dibaca steadyhand:

- **Portofolio**: kas dan kepemilikan Anda, dan, bila dibaca setelah penutupan pasar, harga
  penutupan setiap kepemilikan.
- **Daftar pantauan**: saham yang Anda ikuti, dan harga penutupannya.
- **Notasi khusus**: notasi bursa atas saham, seperti suspensi.
- **Dividen**, **mutasi kas**, dan **aksi korporasi**: dividen yang dibayarkan sebuah saham,
  setoran dan penarikan Anda, serta pemecahan saham.
- **Halaman sebuah saham**: grafik harganya.

**Pembacaan yang segar.** Saran membutuhkan halaman portofolio dan daftar pantauan yang dibaca
untuk hari yang sama, dalam selang 30 menit satu sama lain dan di luar sesi perdagangan. Jika
tidak, panel menyebutkan halaman yang perlu dibaca ulang.

**Apa yang kurang.** Ketika strategi membutuhkan sesuatu yang belum terbaca, seperti dividen atau
grafik sebuah saham, atau grafik yang tidak mencakup waktu cukup jauh ke belakang, panel
mencantumkannya di bagian Data kurang, dan tidak memberikan order sampai hal itu terbaca.

**Halaman yang Anda simpan.** Halaman broker yang Anda simpan bisa ditempel ke tab Saran, atau
dibuka dari berkas. Halaman itu dibaca di dalam panel, seperti halaman lainnya, dan tidak dikirim
ke mana pun.
