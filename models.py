from datetime import datetime, timezone

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, Integer, DateTime, ForeignKey, Index, String,
                        Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(256), default="")
    abu_id: Mapped[str | None] = mapped_column(String(16), unique=True)
    is_banned: Mapped[bool] = mapped_column(default=False)


class Balance(Base, TimestampMixin):
    __tablename__ = "balances"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    currency: Mapped[str] = mapped_column(String(8), primary_key=True)  # ABU_F | ABU_TON
    amount: Mapped[int] = mapped_column(BigInteger, default=0)
    __table_args__ = (CheckConstraint("amount >= 0", name="ck_balance_non_negative"),)


class Transaction(Base):
    """Ledger: balansdagi har bir o'zgarish shu yerda yoziladi."""
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    currency: Mapped[str] = mapped_column(String(8))
    amount: Mapped[int] = mapped_column(BigInteger)  # + kirim, - chiqim
    balance_after: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(32))
    ref: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("kind", "ref", name="uq_tx_kind_ref"),)


class TopupRequest(Base, TimestampMixin):
    """Karta orqali balans to'ldirish so'rovi (qo'lda admin tasdig'i bilan)."""
    __tablename__ = "topup_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    abu_f_amount: Mapped[int] = mapped_column(BigInteger)
    amount_uzs: Mapped[int] = mapped_column(BigInteger)
    # created -> awaiting_review -> approved | rejected
    status: Mapped[str] = mapped_column(String(20), default="created", index=True)
    receipt_file_id: Mapped[str | None] = mapped_column(String(256))
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_topup_status_created", "status", "created_at"),)


class AppSetting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(64))
    details: Mapped[str] = mapped_column(Text, default="")  # maxfiy ma'lumot (karta raqami) yozilmaydi
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MandatoryChannel(Base, TimestampMixin):
    __tablename__ = "mandatory_channels"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)  # @kanal


class Referral(Base, TimestampMixin):
    __tablename__ = "referrals"
    id: Mapped[int] = mapped_column(primary_key=True)
    inviter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    invitee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    # pending -> rewarded | cancelled
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    subscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    rewarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Streak(Base, TimestampMixin):
    __tablename__ = "streaks"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    current: Mapped[int] = mapped_column(Integer, default=0)
    last_claim: Mapped[datetime | None] = mapped_column(Date)


class PromoCode(Base, TimestampMixin):
    __tablename__ = "promo_codes"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    currency: Mapped[str] = mapped_column(String(8))
    amount: Mapped[int] = mapped_column(BigInteger)
    mode: Mapped[str] = mapped_column(String(12))  # limit | time | unlimited
    max_uses: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PromoRedemption(Base):
    __tablename__ = "promo_redemptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    promo_id: Mapped[int] = mapped_column(ForeignKey("promo_codes.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("promo_id", "user_id", name="uq_promo_user"),)


class Transfer(Base):
    __tablename__ = "transfers"
    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    receiver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    currency: Mapped[str] = mapped_column(String(8))
    amount: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (CheckConstraint("amount > 0", name="ck_transfer_positive"),)


class Package(Base, TimestampMixin):
    """Valyuta paketlari (masalan 200 ABU TON = 50 000 so'm). Admin boshqaradi."""
    __tablename__ = "packages"
    id: Mapped[int] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(8))
    amount: Mapped[int] = mapped_column(BigInteger)
    price_uzs: Mapped[int] = mapped_column(BigInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(64), default="Boshqa", index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    price_uzs: Mapped[int] = mapped_column(BigInteger)
    stock: Mapped[int | None] = mapped_column(Integer)  # None = cheksiz
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    price_uzs: Mapped[int] = mapped_column(BigInteger)
    price_abu_f: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default="paid", index=True)  # paid | delivered


class Payment(Base, TimestampMixin):
    """Click orqali to'lov. Balans faqat provayder tasdig'i (complete) bilan beriladi."""
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(16), default="click")
    currency: Mapped[str] = mapped_column(String(8))
    grant_amount: Mapped[int] = mapped_column(BigInteger)
    amount_uzs: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(12), default="new", index=True)  # new|prepared|paid|cancelled
    click_trans_id: Mapped[str | None] = mapped_column(String(32))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int | None] = mapped_column(Integer, index=True)
    provider: Mapped[str] = mapped_column(String(16))
    event: Mapped[str] = mapped_column(String(16))
    result_error: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserXP(Base, TimestampMixin):
    __tablename__ = "user_xp"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    xp: Mapped[int] = mapped_column(BigInteger, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)


class XPEvent(Base):
    __tablename__ = "xp_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    ref: Mapped[str] = mapped_column(String(64))
    amount: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("kind", "ref", name="uq_xp_kind_ref"),)


class VipLevel(Base, TimestampMixin):
    __tablename__ = "vip_levels"
    id: Mapped[int] = mapped_column(primary_key=True)
    rank: Mapped[int] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(32))
    min_level: Mapped[int] = mapped_column(Integer)
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(64), default="")


class Achievement(Base):
    __tablename__ = "achievements"
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(200), default="")
    icon: Mapped[str] = mapped_column(String(8), default="🏅")
    kind: Mapped[str] = mapped_column(String(24))  # referrals|streak|tasks|purchases|transfers|sales
    threshold: Mapped[int] = mapped_column(Integer)
    reward_f: Mapped[int] = mapped_column(Integer, default=0)


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    code: Mapped[str] = mapped_column(ForeignKey("achievements.code"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "code", name="uq_user_ach"),)


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(12))  # channel | bonus | invite
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    reward_f: Mapped[int] = mapped_column(Integer, default=0)
    reward_ton: Mapped[int] = mapped_column(Integer, default=0)
    repeat: Mapped[str] = mapped_column(String(8), default="once")  # once | daily
    channel: Mapped[str | None] = mapped_column(String(64))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TaskCompletion(Base):
    __tablename__ = "task_completions"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    period_key: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("task_id", "user_id", "period_key", name="uq_task_user_period"),)


class SupportTicket(Base, TimestampMixin):
    __tablename__ = "support_tickets"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)  # open | answered | closed


class SupportMessage(Base):
    __tablename__ = "support_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("support_tickets.id"), index=True)
    sender: Mapped[str] = mapped_column(String(8))  # user | admin
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Listing(Base, TimestampMixin):
    __tablename__ = "marketplace_listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    price_abu_f: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)  # pending|approved|rejected|hidden


class MarketOrder(Base, TimestampMixin):
    """Escrow: pul xaridorda yechiladi, sotuvchiga faqat xaridor tasdiqlagach (yoki admin) o'tadi."""
    __tablename__ = "marketplace_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("marketplace_listings.id"), index=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    price_abu_f: Mapped[int] = mapped_column(BigInteger)
    fee_abu_f: Mapped[int] = mapped_column(BigInteger, default=0)
    # paid | delivered | completed | disputed | refunded
    status: Mapped[str] = mapped_column(String(12), default="paid", index=True)


class MarketMessage(Base):
    __tablename__ = "marketplace_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("marketplace_orders.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("marketplace_orders.id"), unique=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_rating"),)


class Question(Base):
    __tablename__ = "quiz_questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(String(300))
    options: Mapped[str] = mapped_column(Text)  # "a||b||c||d"
    correct: Mapped[int] = mapped_column(Integer)  # 0..3
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[str] = mapped_column(String(10))
    question_id: Mapped[int] = mapped_column(ForeignKey("quiz_questions.id"))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_quiz_user_day"),)


class Friendship(Base, TimestampMixin):
    __tablename__ = "friendships"
    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    addressee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)  # pending | accepted
    __table_args__ = (UniqueConstraint("requester_id", "addressee_id", name="uq_friend_pair"),
                      CheckConstraint("requester_id <> addressee_id", name="ck_friend_not_self"))


class UserPrefs(Base, TimestampMixin):
    """Bildirishnoma va maxfiylik sozlamalari."""
    __tablename__ = "user_prefs"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    notify_referral: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_orders: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_news: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_daily: Mapped[bool] = mapped_column(Boolean, default=False)
    profile_visibility: Mapped[str] = mapped_column(String(8), default="all")  # all | friends | nobody
    allow_requests: Mapped[bool] = mapped_column(Boolean, default=True)


class Admin(Base, TimestampMixin):
    """Superadminlar ADMIN_IDS da; bu jadval ruxsatlari cheklangan adminlar uchun."""
    __tablename__ = "admins"
    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    added_by: Mapped[int | None] = mapped_column(BigInteger)


class AdminPermission(Base):
    __tablename__ = "admin_permissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id"), index=True)
    perm: Mapped[str] = mapped_column(String(24))
    __table_args__ = (UniqueConstraint("admin_id", "perm", name="uq_admin_perm"),)
