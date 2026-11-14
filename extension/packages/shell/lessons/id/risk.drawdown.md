+++
id = "risk.drawdown"
title = "Drawdown: seberapa dalam turunnya"
summary = "Drawdown adalah seberapa jauh portofolio turun dari titik tertingginya sebelum pulih."
explains = ["risk.halt.drawdown"]
module = "risk"
position = 1
see_also = ["risk.returns", "risk.limits"]
+++

Anda bisa kehilangan uang. Drawdown memberi angka pada seberapa banyak.

**Titik tertinggi** (high-water mark) adalah nilai tertinggi yang pernah dicapai portofolio sejauh
ini, diukur per unit agar setoran baru tidak terhitung sebagai keuntungan (pelajaran tentang imbal
hasil menjelaskan unit). **Drawdown** adalah penurunan dari titik tertinggi itu, sebagai bagian
darinya. Jika titik tertingginya 1,20 per unit dan portofolio kemudian turun ke 0,90, drawdown-nya
adalah 0,30 / 1,20 = 25%.

steadyhand mengikuti nilai unit dari setiap halaman portofolio yang dibaca setelah penutupan
pasar. Jika nilainya turun 25% di bawah titik tertingginya, pembelian berhenti sampai Anda
melanjutkannya; pelajaran tentang batas pengaman menjelaskan caranya.

Dua hal membuat drawdown lebih penting daripada kelihatannya:

- Untuk kembali dibutuhkan lebih dari penurunannya. Setelah turun 25%, portofolio perlu naik
  sepertiga (33%) hanya untuk kembali ke posisi semula.
- Penurunan terburuk sejauh ini bukanlah yang terburuk yang bisa terjadi. Masa depan bisa membawa
  penurunan yang lebih dalam daripada masa lalu.
