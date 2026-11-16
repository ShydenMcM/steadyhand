+++
id = "strategies.low_volatility"
title = "low-volatility, saham-saham paling tenang"
summary = "Bagaimana low-volatility memegang saham yang bergerak paling merata selama setahun terakhir, dan apa yang dikorbankannya."
explains = []
module = "strategies"
position = 9
see_also = ["strategies.total_return", "strategies.holding_cash"]
+++

Pada hari saran pertama setiap bulan, `low-volatility` mengukur seberapa tidak merata pergerakan
setiap saham: simpangan baku dari gerakan harian imbal hasil totalnya selama sekitar
`volatility_months` (bawaannya 12) bulan. Strategi ini memilih saham yang angkanya paling rendah, sebanyak
`volatility_stocks` (bawaannya 10), memegangnya dalam bagian yang sama, dan menjual sisanya. Di antara dua evaluasi,
strategi ini mempertahankan kepemilikannya dan memasukkan kas baru ke saham pilihannya.

Tenang tidak sama dengan aman, dan tidak mengatakan apa pun tentang arah: saham yang turun sedikit
dengan jumlah yang sama setiap hari juga dinilai tenang. Saham yang tenang sering kali turun lebih
sedikit di pasar yang buruk, dan sering kali naik lebih sedikit di pasar yang baik. Diukur pada
LQ45 dari 2020 sampai 2025, tanpa memperhitungkan biaya, strategi ini turun lebih sedikit daripada
memegang semua anggota dalam bagian yang sama, 21,5% dibanding 33,5% pada titik terburuknya, dan
menghasilkan lebih sedikit, 7,1% setahun dibanding 9,6%. Satu rentang tahun tidak mengatakan apa
yang akan terjadi pada rentang berikutnya.

Saham yang jarang diperdagangkan akan tampak tenang, jadi saham dengan kurang dari 15 harga
penutupan untuk setiap bulan yang ditinjau tidak dinilai. Strategi ini membutuhkan grafik setiap
saham, dibaca dari halaman saham itu sendiri, yang mencakup seluruh rentang tinjauan, beserta
dividen saham itu selama waktu tersebut.
