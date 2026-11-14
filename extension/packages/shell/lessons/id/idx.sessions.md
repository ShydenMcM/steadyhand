+++
id = "idx.sessions"
title = "Jam perdagangan"
summary = "Kapan Bursa Efek Indonesia buka, dan harga mana dalam sehari yang dipakai steadyhand."
explains = ["missing.rules_year"]
module = "how-idx-works"
position = 4
see_also = ["orders.limit_prices", "broker.reading"]
+++

Jam pasar reguler, dalam Waktu Indonesia Barat:

|                                                                   | Senin sampai Kamis    | Jumat                 |
| ----------------------------------------------------------------- | --------------------- | --------------------- |
| Pra-pembukaan: order dikumpulkan, lalu dipertemukan di satu harga | 08:45 sampai 08:59:59 | sama                  |
| Sesi I                                                            | 09:00 sampai 12:00    | 09:00 sampai 11:30    |
| Sesi II                                                           | 13:30 sampai 15:49:59 | 14:00 sampai 15:49:59 |
| Pra-penutupan: order dikumpulkan untuk harga penutupan            | 15:50 sampai 15:59:59 | sama                  |
| Pasca-penutupan: perdagangan pada harga penutupan                 | 16:02 sampai 16:15    | sama                  |

**Harga pembukaan** berasal dari lelang pra-pembukaan, dan **harga penutupan** dari lelang
pra-penutupan. Dalam masing-masing, order dikumpulkan selama beberapa menit lalu dipertemukan pada
satu harga.

steadyhand bekerja dengan harga penutupan setiap hari, bukan dengan menit-menit di antaranya.
Halaman portofolio atau daftar pantauan yang dibaca sejak pukul 16:02 pada hari bursa sampai
pra-pembukaan hari bursa berikutnya mencatat harga penutupan hari itu. Halaman yang dibaca selama
sesi tidak mencatat harga penutupan, dan panel memintanya lagi setelah penutupan pasar.

Bursa tutup pada akhir pekan dan pada hari libur yang diumumkannya. Setiap rilis steadyhand
memuat hari libur tahun demi tahun; untuk tahun yang hari liburnya belum dimuat, pemberian saran ditunda sampai ada rilis yang memuatnya.
