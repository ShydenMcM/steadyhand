+++
id = "risk.returns"
title = "Imbal hasil, dihitung dengan adil"
summary = "Bagaimana steadyhand mengukur untung atau rugi agar uang yang Anda setorkan tidak pernah dihitung sebagai laba."
explains = ["missing.deposits", "missing.reread"]
module = "risk"
position = 2
see_also = ["risk.drawdown", "risk.limits"]
+++

Jika Anda menyetor 1.000.000 ke sebuah portofolio dan kemudian nilainya 1.100.000, kelihatannya
untung 10%. Tetapi jika Anda menyetor 100.000 lagi di tengah jalan, portofolio itu tidak untung
sama sekali: tambahan nilainya adalah uang Anda sendiri.

steadyhand menghindari kesalahan itu dengan menghitung portofolio seperti sebuah reksa dana.

- **Setoran** adalah uang yang Anda masukkan, dan **penarikan** adalah uang yang Anda ambil.
- Setiap setoran membeli **unit** pada **nilai unit** saat itu, dan setiap penarikan menjualnya,
  sehingga keduanya tidak menggerakkan nilai unit.
- Setelah itu, nilai unit hanya bergerak bersama investasinya: perubahan harga, dividen, dan biaya.

Nilai unit hanya diambil dari halaman portofolio yang dibaca setelah penutupan pasar, dan
pembacaan pertama seperti itu memulainya di angka 1.

Jadi steadyhand membutuhkan setiap setoran dan penarikan. steadyhand membaca setoran dan penarikan itu dari halaman mutasi kas broker Anda, atau Anda mengetik masing-masing di Pengaturan. Sampai catatannya mencakup
waktu sejak pembacaan terakhir, pembelian berhenti, dan panel meminta Anda membuka halaman mutasi
kas, mengetik masing-masing, atau menjawab bahwa tidak ada setoran maupun penarikan.
