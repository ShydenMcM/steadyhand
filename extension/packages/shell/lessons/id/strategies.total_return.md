+++
id = "strategies.total_return"
title = "Imbal hasil total"
summary = "Mengapa ma-trend, momentum-rotation, dan low-volatility menilai saham dari harganya dengan dividen ditambahkan kembali."
explains = []
module = "strategies"
position = 8
see_also = ["dividends.basics", "strategies.low_volatility", "strategies.ma_trend", "strategies.momentum_rotation"]
+++

Pada tanggal ex sebuah dividen, harga saham biasanya turun kira-kira sebesar dividen itu, karena
pembeli sejak hari itu tidak akan menerimanya. Grafik harga saja lalu menunjukkan penurunan yang
tidak benar-benar dialami pemegangnya: uangnya datang sebagai dividen.

**Imbal hasil total** menambahkan dividen itu kembali. Setiap dividen tunai diperlakukan seolah
diinvestasikan kembali ke saham itu pada tanggal ex-nya, sehingga setiap harga penutupan sebelum
tanggal ex dikalikan dengan satu dikurangi dividen dibagi harga penutupan sehari sebelumnya.
Grafik yang sudah memuat penyesuaian itu tidak disesuaikan dua kali.

`ma-trend`, `momentum-rotation`, dan `low-volatility` menilai setiap saham dari imbal hasil
totalnya, sehingga saham yang membayar dividen besar tidak disangka sedang turun. Untuk itu
dibutuhkan dividen saham itu selama seluruh rentang waktunya, dibaca dari halaman dividennya, dan
saham yang dividennya belum terbaca dicantumkan di bagian Data yang kurang.
