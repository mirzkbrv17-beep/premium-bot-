from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton as B, InlineKeyboardMarkup as M, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import Listing, MarketOrder, User
from services.admin_service import targets
from services import market_service as mk, progress_service, support_service
from services.market_service import MarketError
from services.prefs_service import notify_user
from services.user_service import get_or_create_user
from utils.helpers import e, fmt, say

router = Router()
OST = {"paid": "💰 To'langan", "delivered": "📦 Topshirilgan", "completed": "✅ Yakunlangan",
       "disputed": "⚠️ Nizo", "refunded": "↩️ Qaytarilgan"}
LST = {"pending": "⏳ Moderatsiyada", "approved": "🟢 Faol", "rejected": "🔴 Rad etilgan", "hidden": "⚪️ Yashirin"}


class SellStates(StatesGroup):
    title = State()
    price = State()
    desc = State()


class SearchState(StatesGroup):
    query = State()


class PriceState(StatesGroup):
    price = State()


class MsgState(StatesGroup):
    text = State()


async def _me(session, call_or_msg):
    u = call_or_msg.from_user
    return await get_or_create_user(session, u.id, u.username, u.full_name)


def _list_kb(items, back="market", extra=None):
    rows = [[B(text=f"{li.title[:30]} — {fmt(li.price_abu_f)} ABU F", callback_data=f"mk:v:{li.id}")] for li in items]
    rows += extra or []
    rows.append([B(text="⬅️ Orqaga", callback_data=back)])
    return M(inline_keyboard=rows)


@router.callback_query(F.data == "market")
async def market(call: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = M(inline_keyboard=[
        [B(text="🛒 E'lonlar", callback_data="mk:list:new:0"), B(text="🔎 Qidiruv", callback_data="mk:search")],
        [B(text="➕ Sotish", callback_data="mk:sell"), B(text="📋 E'lonlarim", callback_data="mk:mine")],
        [B(text="📦 Xaridlarim", callback_data="mk:buys"), B(text="💼 Sotuvlarim", callback_data="mk:sales")],
        [B(text="⬅️ Orqaga", callback_data="home")]])
    await call.message.edit_text("🌐 <b>ABU MARKET</b>\nTo'lov ABU F bilan, xavfsiz escrow orqali.", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.regexp(r"^mk:list:(new|cheap):\d+$"))
async def mk_list(call: CallbackQuery, session: AsyncSession):
    _, _, sort, page = call.data.split(":")
    page = int(page)
    items = await mk.search(session, None, sort, page)
    nav = []
    if page > 0:
        nav.append(B(text="◀️", callback_data=f"mk:list:{sort}:{page - 1}"))
    other = "cheap" if sort == "new" else "new"
    nav.append(B(text="↕️ " + ("Arzonlari" if sort == "new" else "Yangilari"), callback_data=f"mk:list:{other}:0"))
    if len(items) == 8:
        nav.append(B(text="▶️", callback_data=f"mk:list:{sort}:{page + 1}"))
    await call.message.edit_text("🛒 <b>E'lonlar</b>" + ("" if items else "\nHozircha e'lon yo'q."),
                                 reply_markup=_list_kb(items, extra=[nav]))
    await call.answer()


@router.callback_query(F.data == "mk:search")
async def mk_search(call: CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.query)
    await call.message.edit_text("Qidiruv so'zini yuboring:")
    await call.answer()


@router.message(SearchState.query, F.text)
async def mk_search_q(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    items = await mk.search(session, message.text, "new", 0, 10)
    await message.answer(f"🔎 «{e(message.text[:40])}» bo'yicha natijalar" + ("" if items else ": topilmadi"),
                         reply_markup=_list_kb(items))


@router.callback_query(F.data.regexp(r"^mk:v:\d+$"))
async def mk_view(call: CallbackQuery, session: AsyncSession):
    li = await session.get(Listing, int(call.data.split(":")[2]))
    if not li or li.status != "approved":
        await call.answer("E'lon mavjud emas", show_alert=True)
        return
    seller = await session.get(User, li.seller_id)
    avg, n = await mk.seller_rating(session, li.seller_id)
    kb = M(inline_keyboard=[[B(text=f"🛒 {fmt(li.price_abu_f)} ABU F ga olish", callback_data=f"mk:buy:{li.id}")],
                            [B(text="🚩 Shikoyat", callback_data=f"mk:rep:{li.id}")],
                            [B(text="⬅️ Orqaga", callback_data="mk:list:new:0")]])
    await call.message.edit_text(f"<b>{e(li.title)}</b>\n{e(li.description)}\n\nNarx: <b>{fmt(li.price_abu_f)} ABU F</b>\n"
                                 f"Sotuvchi: <code>{seller.abu_id}</code> · ⭐ {avg or '—'} ({n})", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.regexp(r"^mk:rep:\d+$"))
async def mk_report(call: CallbackQuery, session: AsyncSession):
    user = await _me(session, call)
    lid = int(call.data.split(":")[2])
    t = await support_service.create_ticket(session, user.id, f"Shikoyat: market e'loni #{lid}")
    await call.answer(f"Shikoyat yuborildi: {support_service.tid(t.id)}", show_alert=True)
    for admin_id in await targets(session, "market"):
        try:
            await call.bot.send_message(admin_id, f"🚩 Shikoyat {support_service.tid(t.id)} — e'lon #{lid} ({user.abu_id}). "
                                                  f"/market_hide {lid}")
        except Exception:
            pass


@router.callback_query(F.data.regexp(r"^mk:buy:\d+$"))
async def mk_buy_confirm(call: CallbackQuery):
    lid = call.data.split(":")[2]
    kb = M(inline_keyboard=[[B(text="✅ Ha", callback_data=f"mk:ok:{lid}"), B(text="❌ Yo'q", callback_data=f"mk:v:{lid}")]])
    await call.message.edit_text("Xaridni tasdiqlaysizmi? Pul escrowda saqlanadi, siz qabul qilgach sotuvchiga o'tadi.", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.regexp(r"^mk:ok:\d+$"))
async def mk_buy(call: CallbackQuery, session: AsyncSession):
    user = await _me(session, call)
    try:
        o = await mk.buy(session, user.id, int(call.data.split(":")[2]))
    except MarketError as ex:
        await call.message.edit_text(f"❌ {ex}", reply_markup=M(inline_keyboard=[[B(text="⬅️ Market", callback_data="market")]]))
        await call.answer()
        return
    await call.message.edit_text(f"✅ Buyurtma #{o.id} yaratildi. Sotuvchi topshirishini kuting.",
                                 reply_markup=M(inline_keyboard=[[B(text="📦 Buyurtma", callback_data=f"mk:o:{o.id}")]]))
    seller = await session.get(User, o.seller_id)
    await notify_user(session, call.bot, seller, "orders", f"🛒 Yangi buyurtma #{o.id}! Mahsulotni topshirib, «Sotuvlarim»da «Topshirdim»ni bosing.")
    await say(call.bot, call.from_user.id, await progress_service.check_achievements(session, user.id))
    await call.answer()


# ---- sotish ----
@router.callback_query(F.data == "mk:sell")
async def sell_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(SellStates.title)
    await call.message.edit_text("E'lon nomini yuboring:")
    await call.answer()


@router.message(SellStates.title, F.text)
async def sell_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip()[:100])
    await state.set_state(SellStates.price)
    await message.answer("Narxni ABU F da yuboring (butun son):")


@router.message(SellStates.price, F.text)
async def sell_price(message: Message, state: FSMContext):
    raw = message.text.replace(" ", "")
    if not raw.isdigit() or int(raw) < 1 or len(raw) > 9:
        await message.answer("Musbat butun son yuboring.")
        return
    await state.update_data(price=int(raw))
    await state.set_state(SellStates.desc)
    await message.answer("Tavsifni yuboring:")


@router.message(SellStates.desc, F.text)
async def sell_desc(message: Message, session: AsyncSession, state: FSMContext):
    d = await state.get_data()
    user = await _me(session, message)
    li = await mk.create_listing(session, user.id, d["title"], d["price"], message.text)
    await state.clear()
    await message.answer(f"✅ E'lon #{li.id} moderatsiyaga yuborildi.")
    for admin_id in await targets(session, "market"):
        await say(message.bot, admin_id, [f"🆕 Yangi e'lon #{li.id}: {e(li.title)} — {li.price_abu_f} ABU F\n/market_ok {li.id}  /market_no {li.id}"])


@router.callback_query(F.data == "mk:mine")
async def mine(call: CallbackQuery, session: AsyncSession):
    user = await _me(session, call)
    items = (await session.execute(select(Listing).where(Listing.seller_id == user.id).order_by(Listing.id.desc()).limit(15))).scalars().all()
    rows = [[B(text=f"{LST[li.status]} · {li.title[:25]}", callback_data=f"mk:m:{li.id}")] for li in items]
    rows.append([B(text="⬅️ Orqaga", callback_data="market")])
    await call.message.edit_text("📋 <b>E'lonlarim</b>" + ("" if items else "\nHali yo'q."), reply_markup=M(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.regexp(r"^mk:m:\d+$"))
async def mine_view(call: CallbackQuery, session: AsyncSession):
    user = await _me(session, call)
    li = await session.get(Listing, int(call.data.split(":")[2]))
    if not li or li.seller_id != user.id:
        await call.answer("Topilmadi", show_alert=True)
        return
    kb = M(inline_keyboard=[[B(text="✏️ Narxni o'zgartirish", callback_data=f"mk:price:{li.id}"),
                             B(text="🙈 Yashirish", callback_data=f"mk:hide:{li.id}")],
                            [B(text="⬅️ Orqaga", callback_data="mk:mine")]])
    await call.message.edit_text(f"<b>{e(li.title)}</b>\n{fmt(li.price_abu_f)} ABU F · {LST[li.status]}", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.regexp(r"^mk:hide:\d+$"))
async def hide(call: CallbackQuery, session: AsyncSession):
    user = await _me(session, call)
    try:
        await mk.hide_own(session, int(call.data.split(":")[2]), user.id)
    except MarketError as ex:
        await call.answer(str(ex), show_alert=True)
        return
    await call.answer("Yashirildi", show_alert=True)


@router.callback_query(F.data.regexp(r"^mk:price:\d+$"))
async def price_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(PriceState.price)
    await state.update_data(listing_id=int(call.data.split(":")[2]))
    await call.message.answer("Yangi narxni yuboring (tahrirdan keyin e'lon qayta moderatsiyadan o'tadi):")
    await call.answer()


@router.message(PriceState.price, F.text)
async def price_set(message: Message, session: AsyncSession, state: FSMContext):
    raw = message.text.replace(" ", "")
    d = await state.get_data()
    user = await _me(session, message)
    if not raw.isdigit() or int(raw) < 1:
        await message.answer("Musbat butun son yuboring.")
        return
    try:
        await mk.edit_price(session, d["listing_id"], user.id, int(raw))
    except MarketError as ex:
        await message.answer(str(ex))
    else:
        await message.answer("✅ Narx yangilandi, e'lon moderatsiyaga qaytdi.")
    await state.clear()


# ---- buyurtmalar ----
async def _orders(call, session, role):
    user = await _me(session, call)
    col = MarketOrder.buyer_id if role == "buy" else MarketOrder.seller_id
    items = (await session.execute(select(MarketOrder).where(col == user.id).order_by(MarketOrder.id.desc()).limit(15))).scalars().all()
    rows = [[B(text=f"#{o.id} · {OST[o.status]} · {fmt(o.price_abu_f)} ABU F", callback_data=f"mk:o:{o.id}")] for o in items]
    rows.append([B(text="⬅️ Orqaga", callback_data="market")])
    await call.message.edit_text("📦 <b>Xaridlarim</b>" if role == "buy" else "💼 <b>Sotuvlarim</b>", reply_markup=M(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data == "mk:buys")
async def buys(call: CallbackQuery, session: AsyncSession):
    await _orders(call, session, "buy")


@router.callback_query(F.data == "mk:sales")
async def sales(call: CallbackQuery, session: AsyncSession):
    await _orders(call, session, "sell")


@router.callback_query(F.data.regexp(r"^mk:o:\d+$"))
async def order_view(call: CallbackQuery, session: AsyncSession):
    user = await _me(session, call)
    o = await session.get(MarketOrder, int(call.data.split(":")[2]))
    if not o or user.id not in (o.buyer_id, o.seller_id):
        await call.answer("Topilmadi", show_alert=True)
        return
    li = await session.get(Listing, o.listing_id)
    rows = []
    if user.id == o.seller_id and o.status == "paid":
        rows.append([B(text="📦 Topshirdim", callback_data=f"mk:dlv:{o.id}")])
    if user.id == o.buyer_id and o.status == "delivered":
        rows.append([B(text="✅ Qabul qildim", callback_data=f"mk:cfm:{o.id}")])
    if user.id == o.buyer_id and o.status in ("paid", "delivered"):
        rows.append([B(text="⚠️ Nizo", callback_data=f"mk:dsp:{o.id}")])
    if o.status in ("paid", "delivered", "disputed"):
        rows.append([B(text="💬 Xabar yozish", callback_data=f"mk:msg:{o.id}")])
    if user.id == o.buyer_id and o.status == "completed":
        rows.append([B(text=f"{'⭐' * n}", callback_data=f"mk:rate:{o.id}:{n}") for n in (1, 3, 5)])
    rows.append([B(text="⬅️ Orqaga", callback_data="market")])
    await call.message.edit_text(f"Buyurtma <b>#{o.id}</b> · {OST[o.status]}\n{e(li.title)}\n{fmt(o.price_abu_f)} ABU F",
                                 reply_markup=M(inline_keyboard=rows))
    await call.answer()


async def _notify_other(call, session, o, me_id, text):
    other = await session.get(User, o.seller_id if me_id == o.buyer_id else o.buyer_id)
    await notify_user(session, call.bot, other, "orders", text)


@router.callback_query(F.data.regexp(r"^mk:dlv:\d+$"))
async def deliver(call: CallbackQuery, session: AsyncSession):
    user = await _me(session, call)
    try:
        o = await mk.mark_delivered(session, int(call.data.split(":")[2]), user.id)
    except MarketError as ex:
        await call.answer(str(ex), show_alert=True)
        return
    await call.answer("Belgilandi", show_alert=True)
    await _notify_other(call, session, o, user.id, f"📦 Buyurtma #{o.id} topshirildi. Tekshirib, «Xaridlarim»da «Qabul qildim»ni bosing.")


@router.callback_query(F.data.regexp(r"^mk:cfm:\d+$"))
async def confirm(call: CallbackQuery, session: AsyncSession):
    user = await _me(session, call)
    try:
        o = await mk.confirm(session, int(call.data.split(":")[2]), user.id)
    except MarketError as ex:
        await call.answer(str(ex), show_alert=True)
        return
    await call.answer("Tasdiqlandi. Sotuvchiga to'lov o'tdi.", show_alert=True)
    seller = await session.get(User, o.seller_id)
    extra = await progress_service.award_xp(session, seller.id, "market", f"mkt:{o.id}")
    extra += await progress_service.check_achievements(session, seller.id)
    await notify_user(session, call.bot, seller, "orders", f"💰 Buyurtma #{o.id} yakunlandi: +{fmt(o.price_abu_f - o.fee_abu_f)} ABU F")
    await say(call.bot, seller.tg_id, extra)


@router.callback_query(F.data.regexp(r"^mk:dsp:\d+$"))
async def dispute(call: CallbackQuery, session: AsyncSession):
    user = await _me(session, call)
    try:
        o = await mk.dispute(session, int(call.data.split(":")[2]), user.id)
    except MarketError as ex:
        await call.answer(str(ex), show_alert=True)
        return
    await call.answer("Nizo ochildi. Admin ko'rib chiqadi.", show_alert=True)
    await _notify_other(call, session, o, user.id, f"⚠️ Buyurtma #{o.id} bo'yicha nizo ochildi.")
    for admin_id in await targets(session, "market"):
        await say(call.bot, admin_id, [f"⚠️ Nizo: buyurtma #{o.id}\n/market_release {o.id} (sotuvchiga)  /market_refund {o.id} (xaridorga)"])


@router.callback_query(F.data.regexp(r"^mk:msg:\d+$"))
async def msg_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(MsgState.text)
    await state.update_data(order_id=int(call.data.split(":")[2]))
    await call.message.answer("Xabaringizni yuboring (shaxsiy ma'lumotlaringiz oshkor bo'lmaydi):")
    await call.answer()


@router.message(MsgState.text, F.text)
async def msg_send(message: Message, session: AsyncSession, state: FSMContext):
    d = await state.get_data()
    user = await _me(session, message)
    await state.clear()
    try:
        other_id = await mk.add_message(session, d["order_id"], user.id, message.text)
    except MarketError as ex:
        await message.answer(str(ex))
        return
    other = await session.get(User, other_id)
    kb = M(inline_keyboard=[[B(text="💬 Javob", callback_data=f"mk:msg:{d['order_id']}")]])
    try:
        await message.bot.send_message(other.tg_id, f"💬 Buyurtma #{d['order_id']} (<code>{user.abu_id}</code>):\n{e(message.text[:1000])}", reply_markup=kb)
    except Exception:
        pass
    await message.answer("✅ Yuborildi.")


@router.callback_query(F.data.regexp(r"^mk:rate:\d+:[1-5]$"))
async def rate(call: CallbackQuery, session: AsyncSession):
    user = await _me(session, call)
    _, _, oid, n = call.data.split(":")
    try:
        await mk.review(session, int(oid), user.id, int(n))
    except MarketError as ex:
        await call.answer(str(ex), show_alert=True)
        return
    await call.answer("Rahmat! Baho qabul qilindi.", show_alert=True)
