+++
id = "strategies.ma_trend"
title = "ma-trend, mengikuti tren"
summary = "Bagaimana ma-trend memegang saham yang harganya sedang naik, dengan membandingkan dua rata-rata, dan mengapa tren bisa berbalik."
explains = []
module = "strategies"
position = 6
see_also = ["strategies.total_return", "costs.trading"]
+++

Setiap hari saran, `ma-trend` membandingkan dua rata-rata harga penutupan setiap saham: rata-rata
`fast_days` (bawaannya 50) hari terakhir dan rata-rata `slow_days` (bawaannya 200) hari terakhir,
keduanya dihitung sebagai imbal hasil total. Saham yang rata-rata pendeknya berada di atas
rata-rata panjangnya sedang dalam **tren naik**.

Strategi ini mempertahankan sebuah kepemilikan selama tren naiknya berlangsung, dan menjual
seluruhnya saat tren berbalik atau saham itu keluar dari semesta. Kas baru masuk ke saham yang
sedang dalam tren naik, masing-masing hingga bagian yang sama dari semesta.

Rata-rata memang lambat. Rata-rata baru bergerak setelah harga bergerak, jadi strategi ini membeli
setelah kenaikan dimulai dan menjual setelah penurunan dimulai, dan di pasar yang bergerak
mendatar strategi ini bisa membeli dan menjual berulang kali, membayar biaya setiap kali. Strategi
ini membutuhkan grafik setiap saham, dibaca dari halaman saham itu sendiri, hingga `slow_days` hari
bursa ke belakang.
