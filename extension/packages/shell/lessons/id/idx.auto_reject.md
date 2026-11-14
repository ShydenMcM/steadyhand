+++
id = "idx.auto_reject"
title = "Auto rejection: seberapa jauh harga boleh bergerak dalam sehari"
summary = "Bursa menolak setiap order yang harganya terlalu jauh di atas atau di bawah harga penutupan sebelumnya."
explains = []
module = "how-idx-works"
position = 3
see_also = ["idx.ticks"]

+++

Untuk mencegah ayunan liar, bursa menolak order yang harganya **lebih dari** persentase tertentu
di atas atau di bawah harga acuan, biasanya harga penutupan hari sebelumnya. Harga yang persis sama dengan batasnya masih diterima. Batas-batas ini disebut rentang **auto rejection**.

Batas atas bergantung pada harga:

| Penutupan sebelumnya         | Kenaikan tertinggi yang diterima |
| ---------------------------- | -------------------------------- |
| sampai Rp200                 | 35%                              |
| di atas Rp200 sampai Rp5.000 | 25%                              |
| di atas Rp5.000              | 20%                              |

Batas bawah sudah beberapa kali berubah. Sejak 8 April 2025 batasnya 15% di semua harga, dan mulai
1 Januari 2027 batas bawah menjadi sama dengan batas atas di setiap rentang harga. Mulai
28 September 2026, harga terendah tempat saham boleh diperdagangkan adalah Rp1, bukan Rp50, dan
saham berharga Rp1 sampai Rp10 boleh bergerak Rp1 ke atas atau ke bawah, bukan dengan persentase.

Jadi, selama sisa tahun 2026, sebuah saham bisa turun paling banyak sekitar 15% dalam sehari, seburuk apa
pun beritanya. Jika penjual menginginkan harga yang lebih rendah, saham itu berhenti di batasnya
dan penjualan berlanjut keesokan harinya. steadyhand juga memakai rentang ini untuk mengenali data
harga yang mustahil.
