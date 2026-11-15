+++
id = "strategies.holding_cash"
title = "Saat sebuah strategi memegang kas"
summary = "Mengapa sebuah strategi menyimpan sebagian portofolio dalam bentuk kas ketika terlalu sedikit saham yang lolos ujiannya, dan apa harganya."
explains = ["strategy.too_few_qualified"]
module = "strategies"
position = 4
see_also = ["dividends.basics", "strategies.dividend_growth"]
+++

`dividend-growth` hanya memegang saham yang lolos ujian dividennya pada evaluasi tahunan terakhir,
dan memberi masing-masing bagian yang sama dari portofolio, tidak pernah lebih dari satu bagian
dalam `min_stocks` (bawaannya 15). Jika yang lolos lebih sedikit dari itu, strategi ini tidak
menyebar uangnya ke beberapa saham yang ada: bagian yang seharusnya diambil saham lain tetap
berupa kas, dan peringatan di panel menyebutkan berapa saham yang lolos. `high-yield`,
`momentum-rotation`, dan `low-volatility` melakukan hal yang sama ketika saham yang memenuhi syarat
lebih sedikit daripada jumlah yang mereka pegang.

Ini mencegah portofolio bertumpu pada segelintir perusahaan, yang merupakan risiko tersendiri.
Harganya: kas tidak menghasilkan apa-apa dalam hitungan steadyhand, jadi tahun dengan banyak
pemangkasan dividen bisa membuat portofolio memegang banyak kas sampai evaluasi berikutnya
menemukan cukup banyak saham yang lolos lagi. Menurunkan `min_stocks` di Pengaturan menempatkan
lebih banyak uang ke dalam lebih sedikit saham. Mana yang lebih baik adalah pilihan tentang risiko.
