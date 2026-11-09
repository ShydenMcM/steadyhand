+++
id = "orders.limit_prices"
title = "Harga limit"
summary = "Mengapa limit setiap order adalah harga penutupan hari itu, dan kapan broker masih bisa menolaknya."
explains = []
module = "using-steadyhand"
position = 3
see_also = ["idx.ticks", "idx.auto_reject"]
+++

Setiap order yang diberikan panel adalah order limit pada harga penutupan di hari saran itu dibuat. Harga
penutupan selalu merupakan harga yang diterima bursa: harga itu selalu sesuai dengan kelipatan
fraksi harga yang berlaku, dan pada hari biasa harga itu menjadi acuan untuk rentang auto rejection hari berikutnya,
sehingga berada di dalam rentang tersebut.

Limit pada harga penutupan bisa saja tidak terisi. Jika harga tetap di atas limit beli Anda,
atau di bawah limit jual Anda, tidak ada yang dibeli atau dijual, dan saran hari berikutnya
dimulai dari apa yang Anda pegang saat itu.

Pada beberapa hari, acuannya bukan harga penutupan sebelumnya, misalnya pada tanggal ex dari
rights issue, ketika bursa menetapkan acuan baru. steadyhand tidak mengetahui adanya rights issue,
jadi pada hari seperti itu broker Anda bisa menolak order pada harga penutupan. Tidak ada yang
terisi, dan tidak ada hal lain yang berubah.
