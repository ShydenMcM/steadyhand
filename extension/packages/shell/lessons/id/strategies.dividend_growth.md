+++
id = "strategies.dividend_growth"
title = "dividend-growth, ujian atas dividen masa lalu"
summary = "Bagaimana dividend-growth memilih saham berdasarkan dividen yang telah dibayarkannya, dan mengapa catatan yang baik bukanlah janji."
explains = []
module = "strategies"
position = 3
see_also = ["dividends.basics", "strategies.holding_cash", "broker.reading"]
+++

Setahun sekali, `dividend-growth` mempertahankan saham yang membayar dividen pada setiap tahun
dari enam tahun terakhir dan dividen tahun lalunya tidak lebih kecil daripada dividennya
`growth_years` tahun sebelum tahun lalu (bawaannya 5), dengan jumlah yang disesuaikan untuk setiap pemecahan saham.
Strategi ini memegang hingga `max_stocks` (bawaannya 25) saham tersebut dalam bagian yang sama,
disebar agar dividennya tiba pada bulan yang berbeda-beda, dan menjual saham yang tidak lagi
lolos.

Catatan panjang membayar dan menaikkan dividen mengatakan sesuatu tentang masa lalu sebuah
perusahaan, tetapi tidak memberi kepastian apa pun tentang masa depannya: dividen bisa dipangkas pada tahun mana
pun, dan perusahaan yang dividennya naik turun mengikuti bisnisnya tetap bisa lolos. Ujian ini
juga membutuhkan dividen selama bertahun-tahun: buka halaman dividen setiap saham agar panel bisa
membacanya. Saham yang dividennya belum terbaca dicantumkan di bagian Data yang kurang.
