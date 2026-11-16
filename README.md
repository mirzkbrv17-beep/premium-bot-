# ABU BOT — 1-qism (poydevor + karta orqali to'lov)

## GitHub'ga yuklash
1. github.com da yangi **private** repository oching (karta ma'lumotlari uchun private tavsiya etiladi).
2. Barcha fayl va papkalarni (`handlers`, `services`, `keyboards`, `middlewares`, `utils`, `tests` ...) shu tuzilmada yuklang. `.env` faylini yuklamang.

## Render
1. Render -> New -> **PostgreSQL** yarating, "Internal Database URL" ni nusxalang.
2. Render -> New -> **Web Service** -> GitHub repository'ni tanlang.
3. Build: `pip install -r requirements.txt`  |  Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Environment bo'limiga yozing:
   - `BOT_TOKEN` — BotFather bergan token
   - `DATABASE_URL` — PostgreSQL manzili
   - `ADMIN_IDS` — sizning Telegram ID'ingiz (vergul bilan bir nechta bo'lishi mumkin)
   - `WEBHOOK_SECRET` — o'zingiz o'ylab topgan harf/raqam qatori
   - `BASE_URL` — Render bergan manzil, masalan `https://abu-bot.onrender.com`
   - `CARD_NUMBER` va `CARD_HOLDER` — karta rekvizitlari (faqat shu yerga, kodga emas)
5. Deploy qiling. `https://.../health` ochilsa — "ok" chiqadi.

## Karta orqali to'lov qanday ishlaydi
Kabinet -> Balansni to'ldirish -> Karta orqali to'lov -> miqdor -> rekvizitlar + «Nusxalash» -> «To'lov qildim» -> chek rasmi -> admin «Tasdiqlash/Rad etish». Balans faqat admin tasdiqlagandan keyin, bir marta to'ldiriladi.
Rekvizitlarni o'zgartirish (admin): `/setcard 16_xonali_raqam Karta_egasi` (xabar o'chiriladi, logga yozilmaydi).

---
## 2-qism (qo'shildi): referral, kunlik bonus, promo kod, admin buyruqlari
**Yangilash:** 1-qismdagi papkani shu fayllar bilan almashtiring (fayllar bir-biriga bog'liq, hammasini yuklang), GitHub'ga yuklang, Render o'zi qayta deploy qiladi. Yangi jadvallar avtomatik yaratiladi.

**Admin buyruqlari** (faqat `ADMIN_IDS` dagilar):
- `/stats` — statistika
- `/channels`, `/channel_add @kanal`, `/channel_del @kanal` — majburiy kanallar (bot kanalda admin bo'lishi kerak; boshlang'ich: @o11abu)
- `/give ABU-000001 ABU_F 100` — foydalanuvchiga valyuta berish
- `/promo_add KOD ABU_F 100 limit 50` | `/promo_add KOD ABU_TON 5 time 7` | `/promo_add KOD ABU_F 10 unlimited`
- `/promo_stop KOD`
- `/setcard 16_xonali_raqam Karta_egasi`

**Promo kodni foydalanuvchi kiritishi** Mini App Kabinetida bo'ladi (4-qism). Hozir faqat admin tomoni va server logikasi tayyor.

---
## 3-qism (qo'shildi): Transfer, Click, Do'kon, valyuta paketlari
**Yangilash:** yangi va o'zgargan fayllarni yuklang, eskilarini almashtiring. Render o'zi qayta deploy qiladi.

**Click sozlash** (Click merchant shartnomasi sizda bo'lishi kerak):
1. Render Environment'ga `CLICK_SERVICE_ID`, `CLICK_MERCHANT_ID`, `CLICK_SECRET_KEY` qo'shing.
2. Click kabinetida manzillarni kiriting:
   - Prepare URL: `BASE_URL/webhook/click/prepare`
   - Complete URL: `BASE_URL/webhook/click/complete`
3. Kalitlar bo'lmasa, Click `not_configured` holatida qoladi va to'lov tugmasi ishlamaydi (soxta muvaffaqiyat yo'q).

**Balans to'ldirish ikki yo'l bilan:** Click (avtomatik, provayder tasdig'i bilan) yoki karta (qo'lda, admin tasdig'i bilan).

**Admin buyruqlari (yangi):**
- Do'kon: `/product_add Nomi | Kategoriya | narx_uzs | ombor (son yoki -) | Tavsif`, `/product_list`, `/product_off id`, `/product_on id`, `/product_stock id son`, `/product_discount id foiz`
- Paketlar: `/pack_add ABU_TON 200 50000`, `/pack_list`, `/pack_del id`
- Buyurtmalar: `/orders`, `/deliver id`

Do'kon narxlari so'mda; xarid ABU F balansidan kurs bo'yicha yechiladi (kasr keyingi butun so'mga yaxlitlanadi).

---
## 4-qism (qo'shildi): Market, level/XP, VIP, yutuqlar, topshiriqlar, yordam, o'yinlar
**Yangilash:** yangi va o'zgargan fayllarni yuklang (eskilarini almashtiring). Yangi jadvallar avtomatik yaratiladi.

**ABU MARKET:** e'lonlar ABU F bilan sotiladi. Har bir e'lon admin tasdig'idan o'tadi. Pul escrowda saqlanadi: xaridor «Qabul qildim» bossa sotuvchiga o'tadi (komissiya 5%). Nizo bo'lsa admin hal qiladi. Xaridor va sotuvchi bot orqali yozishadi, username va telefon oshkor bo'lmaydi.

**Admin buyruqlari (yangi):**
- Market: `/market_pending`, `/market_ok id`, `/market_no id`, `/market_hide id`, `/disputes`, `/market_release id`, `/market_refund id`
- Topshiriqlar: `/task_add kind | Nomi | Tavsif | ABU_F | ABU_TON | once/daily | @kanal | kunlar`, `/task_list`, `/task_off id` (kind: channel, bonus, invite)
- XP/VIP: `/setxp daily|task|referral|quiz|market|achievement miqdor`, `/setxp levelup_reward_f miqdor`, `/vip_set rank min_level chegirma`
- Viktorina: `/quiz_add Savol | A | B | C | D | to'g'ri(1-4)`
- Yordam: `/tickets`, `/reply id matn`, `/close_ticket id`

**Level:** 0-99 XP = 1, 100 = 2, 400 = 3, 900 = 4 ... Level oshganda ABU F mukofoti beriladi. VIP darajalar levelga bog'liq, chegirma ABU SHOP'da avtomatik.
**Omad g'ildiragi** bepul, sovrinsiz (faqat ko'ngilochar).

---
## 5-qism (qo'shildi): Mini App
**Yangilash:** yangi va o'zgargan fayllarni yuklang, `miniapp/` papkasini ham (3 ta fayl) shu nom bilan yuklang. Qo'shimcha o'rnatish (build) kerak emas: Mini App oddiy HTML/CSS/JS, bot bilan bir serverda ishlaydi.

**Mini App manzili:** `BASE_URL/app/` (masalan `https://abu-bot.onrender.com/app/`). `BASE_URL` Render'da kiritilgan bo'lsa:
- Botning asosiy menyusida «📱 ABU Mini App» tugmasi chiqadi.
- Bot ishga tushganda chat menyu tugmasi ham avtomatik o'rnatiladi.

**BotFather'da (ixtiyoriy):** `/mybots` → botingiz → Bot Settings → Menu Button → URL: yuqoridagi manzil.

**Xavfsizlik:** har bir so'rovda Telegram `initData` serverda tekshiriladi (bot tokeni bilan imzo, 24 soatlik muddat). Balansni faqat server o'zgartiradi. Promo kod faqat Mini App kabinetida kiritiladi va daqiqasiga 5 martadan ko'p urinib bo'lmaydi. Barcha foydalanuvchi matnlari ekranga chiqarilishidan oldin tozalanadi (XSS himoyasi).

**Sahifalar:** Bosh, Do'kon, Market, Bonus (kunlik bonus + topshiriqlar), Kabinet (profil, level, VIP, promo kod, tarix, «Yengil animatsiya» tugmasi).

---
## 6-qism (qo'shildi): premium emoji, ABU Friends, sozlamalar, admin ruxsatlari, Alembic
**Yangilash:** yangi va o'zgargan fayllarni yuklang, `migrations/` papkasini (ichidagi `versions/` bilan) va `alembic.ini` ni ham yuklang. `requirements.txt` yangilandi (aiogram 3.25.0), Render o'zi qayta o'rnatadi.

**Baza migratsiyasi (Alembic):** bot ishga tushganda baza o'zi yangilanadi. Eski bazangiz (1-5 qism) bor bo'lsa, hech narsa yo'qolmaydi, faqat yangi jadvallar qo'shiladi.

### Premium animatsiyali emoji
Telegram talabi (rasmiy hujjat): tugmalarda va xabarlarda custom emoji faqat **bot egasida Telegram Premium bo'lsa** (yoki bot Fragment'da qo'shimcha username sotib olgan bo'lsa) ishlaydi. Aks holda bot avtomatik oddiy emojiga qaytadi, hech narsa buzilmaydi.

Emoji ID'larni men to'qib yozmayman, ularni haqiqiy paketdan olasiz:
1. Telegram'da animatsiyali emoji paketini toping (havola `t.me/addemoji/PAKET_NOMI`).
2. Botga (admin sifatida): `/emoji_pack PAKET_NOMI` — paketdagi emoji va ularning ID'lari chiqadi.
3. `/emoji_set abu_f 1234567890123456789` — tanlangan ID'ni kalitga biriktiring (ID Telegram'dan tekshiriladi). Yoki `/emoji_set abu_f ` dan keyin premium emojining o'zini yuboring.
4. Kalitlar: `home, cabinet, balance, abu_f, abu_ton, shop, market, bonus, tasks, rating, vip, games, support, settings, payment, referral, transfer, friends, back, achievements`.
5. `/emoji_list` — holat, `/emoji_test` — sinash, `/emoji off` — o'chirish, `/emoji_clear kalit` — bittasini o'chirish.

### Adminlar va ruxsatlar (faqat superadmin, ya'ni `ADMIN_IDS` dagilar)
`/admins`, `/admin_add tg_id`, `/admin_del tg_id`, `/admin_perm tg_id ruxsat on|off` (ruxsat: `payments, shop, market, support, promo, tasks, balance, stats, channels, broadcast, emoji` yoki `all`), `/logs` — audit jurnali.
Adminga faqat tegishli bo'limning buyruqlari va xabarlari keladi.

### Boshqa yangiliklar
- **ABU Friends:** ABU ID orqali topish, so'rov yuborish/qabul qilish, do'stlikni bekor qilish. Profilni kim ko'rishi sozlanadi (hamma / faqat do'stlar / hech kim); Telegram username va ism oshkor qilinmaydi.
- **Sozlamalar:** bildirishnomalarni yoqish/o'chirish (referral, buyurtma, yangiliklar, kunlik bonus eslatmasi), do'stlik so'rovlarini qabul qilish. To'lov holati haqidagi xabarlar doim yuboriladi.
- **Kunlik eslatma** (yoqqanlarga, Toshkent 10:00 dan keyin) va `/broadcast matn` (ruxsat: `broadcast`; yangiliklarni o'chirganlarga yuborilmaydi).
