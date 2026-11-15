+++
id = "income.growth"
title = "Pertumbuhan dividen"
summary = "Seberapa cepat dividen per lembar saham kepemilikan Anda tumbuh selama empat tahun terakhir, sebagai laju tahunan."
explains = ["income.growth.short_history"]
module = "income-goal"
position = 4
see_also = ["income.projection", "income.run_rate"]

+++

Untuk setiap kepemilikan, steadyhand membandingkan dividen yang dibayarkan satu lembar saham
selama setahun terakhir dengan dividen yang dibayarkannya selama tahun yang berakhir empat tahun
sebelumnya. Perubahan itu diubah menjadi laju tahunan: dividen yang naik dari 100 menjadi 146 per
lembar dalam empat tahun tumbuh sekitar 10% setahun.

Yang diukur adalah dividen **per lembar**, jadi membeli lebih banyak saham tidak dihitung sebagai
pertumbuhan. Pemecahan saham ikut diperhitungkan, sehingga tidak terlihat seperti pemotongan
dividen.

**Pertumbuhan dividen** portofolio adalah pertumbuhan setiap kepemilikan, dibobot menurut
seberapa besar bagian run-rate yang diberikan kepemilikan itu. Proyeksi memakainya untuk
skenario-skenarionya, dengan batas atas atau pemangkasan, agar satu periode yang bagus tidak
terbawa terlalu jauh.

**Bila dividen yang terbaca tidak menjangkau cukup jauh ke belakang.** Mengukur pertumbuhan
membutuhkan dividen setiap kepemilikan yang membayar dividen sampai awal tahun pembanding itu,
lima tahun yang lalu. Jika halaman dividen sebuah kepemilikan belum terbaca sejauh itu,
steadyhand tidak mengukur apa pun dan menyebutkan halaman yang perlu dibuka, sehingga steadyhand tidak menebak pertumbuhan apa pun.

**Bila sebuah kepemilikan tidak membayar apa pun pada tahun pembanding.** Pertumbuhannya tidak
bisa diukur sebagai laju. steadyhand menghitungnya sebagai 0% dan menyebutkan kepemilikan itu
dalam sebuah catatan, sehingga pertumbuhannya tidak pernah ditebak lebih tinggi.
