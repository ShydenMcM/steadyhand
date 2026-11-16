+++
id = "strategies.momentum_rotation"
title = "momentum-rotation, pemimpin tahun lalu"
summary = "Bagaimana momentum-rotation memegang saham yang naik paling tinggi selama setahun terakhir, dan mengapa pemimpin bisa berhenti memimpin."
explains = []
module = "strategies"
position = 7
see_also = ["strategies.total_return", "strategies.holding_cash"]
+++

Pada hari saran pertama setiap bulan, `momentum-rotation` mengukur kenaikan setiap saham: imbal
hasil totalnya dari sekitar `momentum_months` bulan lalu (bawaannya 12) sampai sekitar
`skip_months` bulan lalu (bawaannya 1). Bulan terakhir tidak dihitung karena gerakan paling baru
sebuah saham sering berbalik. Strategi ini memegang `momentum_stocks` (bawaannya 10) saham yang
naik paling tinggi, dalam bagian yang sama, dan menjual sisanya. Di antara dua evaluasi, strategi
ini mempertahankan kepemilikannya dan memasukkan kas baru ke saham pilihannya.

Saham yang naik paling tinggi selama setahun sering kali terus naik untuk sementara waktu. Namun sering
kali bukan berarti selalu: saat pasar berbalik, pemimpin tahun lalu bisa turun paling cepat, dan
evaluasi bulanan baru menjualnya setelah penurunan terjadi. Strategi ini membutuhkan grafik setiap
saham, dibaca dari halaman saham itu sendiri, yang mencakup seluruh rentang waktunya. Strategi ini juga
membutuhkan dividen saham itu selama waktu tersebut.
