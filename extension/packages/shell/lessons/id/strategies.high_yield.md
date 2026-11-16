+++
id = "strategies.high_yield"
title = "high-yield, dividen terbesar saat ini"
summary = "Bagaimana high-yield memilih saham yang dividen terakhirnya paling besar dibandingkan harganya, dan mengapa imbal hasil yang tinggi bisa menjadi peringatan."
explains = []
module = "strategies"
position = 5
see_also = ["dividends.basics", "strategies.holding_cash"]
+++

Setiap kuartal, `high-yield` melihat saham yang membayar dividen tunai pada setiap tahun kalender
`paid_years` (bawaannya 3) sebelum tahun ini. Untuk masing-masing, **imbal hasil** (yield) adalah
dividen per lembar dengan tanggal ex dalam 365 hari terakhir, disesuaikan untuk setiap pemecahan
saham, dibagi harga penutupan hari itu. Strategi ini memegang `yield_stocks` (bawaannya 10) saham
dengan imbal hasil tertinggi dalam bagian yang sama, dan menjual sisanya. Di antara dua evaluasi,
strategi ini mempertahankan kepemilikannya dan memasukkan kas baru ke saham pilihannya.

Imbal hasil yang tinggi tidak selalu kabar baik. Ketika harga sebuah perusahaan turun karena pasar
memperkirakan dividennya akan dipangkas, imbal hasilnya atas dividen tahun lalu justru naik.
Imbal hasil melihat ke belakang, dan dividen berikutnya bisa lebih kecil. Buka halaman dividen
setiap saham: panel membaca dividennya dari halaman itu.
