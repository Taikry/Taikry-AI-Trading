"""
Tiered VIP Telegram Subscription Bot & Membership Manager
Provides institutional subscription tier management, personalized auto-expiring
Telegram invite links with single-use member limits, automated expiration audits,
channel member eviction on lapse, renewal workflows, and bilingual notifications.
"""
import time
import datetime
import logging
from typing import Dict, Any, Optional, List, Tuple

from taikry.config import (
    VIP_TELEGRAM_CHAT_ID,
    TELEGRAM_CHAT_ID,
    BAKONG_KHQR_ACCOUNT,
    USDT_TRC20_WALLET,
    TELEGRAM_ADMIN_USERNAME,
    TELEGRAM_ADMIN_IDS
)
from taikry.database.session import SessionLocal
from taikry.database.models import VIPSubscriptionModel, VIPInviteLinkRecord
from taikry.notifications.telegram_service import TelegramService, telegram_service as default_telegram_service

logger = logging.getLogger("taikry.subscriptions.vip_manager")

def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)

def _normalize_utc_dt(dt: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)

def _to_gmt7_str(dt: Optional[datetime.datetime]) -> str:
    if not dt:
        return "N/A"
    dt = _normalize_utc_dt(dt)
    gmt7 = datetime.timezone(datetime.timedelta(hours=7))
    return dt.astimezone(gmt7).strftime("%Y-%m-%d %H:%M GMT+7")

SUBSCRIPTION_TIERS: Dict[str, Dict[str, Any]] = {
    "FREE": {
        "tier_code": "FREE",
        "name_en": "Public Community / Previews",
        "name_kh": "សហគមន៍ទូទៅ (ឥតគិតថ្លៃ)",
        "badge": "🥉 FREE",
        "price_usd": 0.0,
        "duration_days": 0,
        "is_lifetime": True,
        "daily_signal_limit": 1,
        "features_en": [
            "Daily Morning Intelligence Briefing (07:00 Phnom Penh)",
            "High-impact Forex Factory news catalyst previews",
            "General market sentiment & educational overviews",
            "Public community channel access"
        ],
        "features_kh": [
            "ព្រឹត្តិបត្រសង្ខេបទីផ្សារស្ថាប័នប្រចាំថ្ងៃ (ម៉ោង 07:00 ព្រឹក)",
            "ការជូនដំណឹងព័ត៌មានសេដ្ឋកិច្ចសំខាន់ៗ (Forex Factory)",
            "ការវិភាគទូទៅ និងការអប់រំហិរញ្ញវត្ថុ",
            "ការចូលរួមក្នុង Channel សាធារណៈ"
        ]
    },
    "PRO": {
        "tier_code": "PRO",
        "name_en": "TAIKRY Pro VIP (XAUUSD Signals)",
        "name_kh": "TAIKRY Pro VIP (សញ្ញាជួញដូរមាស XAUUSD)",
        "badge": "🥈 PRO VIP",
        "price_usd": 49.0,
        "duration_days": 30,
        "is_lifetime": False,
        "daily_signal_limit": 4,
        "features_en": [
            "2–4 High-conviction XAUUSD signals per Cambodia trading day",
            "Real-time Entry, SL, TP1, TP2, TP3 with exact R:R calculation",
            "Multi-Agent AI Consensus verification (80%–95% institutional score)",
            "Automated lifecycle event notifications (Zone Reached, TP Hit, SL Hit)",
            "Verified daily win-rate performance tracking & Cambodia date quota",
            "1-Time secure auto-expiring Telegram invite link"
        ],
        "features_kh": [
            "សញ្ញាជួញដូរមាស XAUUSD ចំនួន 2–4 ក្នុងមួយថ្ងៃ (ម៉ោងកម្ពុជា)",
            "កម្រិតជាក់លាក់ Entry, Stop Loss, TP1, TP2, TP3 ជាមួយអនុបាត R:R ច្បាស់លាស់",
            "ការផ្ទៀងផ្ទាត់ដោយ AI Multi-Agent Consensus (ពិន្ទុ 80%–95%)",
            "ការជូនដំណឹងដំណាក់កាលជួញដូរផ្ទាល់ (ដល់ Entry, ដល់ TP, ដល់ SL)",
            "ការតាមដានស្ថិតិអត្រាឈ្នះប្រចាំថ្ងៃជាក់ស្តែង (Win-Rate Tracking)",
            "តំណភ្ជាប់អញ្ជើញ (Invite Link) សុវត្ថិភាពខ្ពស់ ផុតកំណត់ស្វ័យប្រវត្ត"
        ]
    },
    "VIP": {
        "tier_code": "VIP",
        "name_en": "TAIKRY Institutional Elite VIP",
        "name_kh": "TAIKRY Institutional Elite VIP (ស្ថាប័នជាន់ខ្ពស់)",
        "badge": "🥇 INSTITUTIONAL ELITE",
        "price_usd": 129.0,
        "duration_days": 90,
        "is_lifetime": False,
        "daily_signal_limit": 999,
        "features_en": [
            "All Pro VIP features included",
            "1-Click Trade Execution Bridge to MetaTrader 5 / Binance Webhook",
            "Full AI Agents Round-Table Debate transcripts & rationale",
            "Live Economic Calendar Pre-News Lockout Early Warning",
            "Multi-Asset signals (XAUUSD + EURUSD + GBPUSD + BTCUSDT)",
            "Priority direct concierge support & account risk audits"
        ],
        "features_kh": [
            "រួមបញ្ចូលរាល់មុខងារទាំងអស់របស់ Pro VIP",
            "ប្រព័ន្ធ 1-Click Trade Execution ទៅកាន់ MetaTrader 5 / Binance Webhook",
            "កំណត់ហេតុពិភាក្សា AI Round-Table Debate ទាំងស្រុង",
            "ការព្រមានចាក់សោរហានិភ័យមុនព័ត៌មានសេដ្ឋកិច្ចចេញ (News Lockout)",
            "សញ្ញាជួញដូរទ្រព្យសកម្មចម្រុះ (មាស XAUUSD, រូបិយប័ណ្ណ Forex, BTC)",
            "ការគាំទ្រផ្ទាល់ជាអាទិភាព VIP 24/7"
        ]
    },
    "LIFETIME": {
        "tier_code": "LIFETIME",
        "name_en": "TAIKRY Institutional Lifetime VIP",
        "name_kh": "TAIKRY Institutional VIP មួយជីវិត (Lifetime)",
        "badge": "👑 LIFETIME ACCESS",
        "price_usd": 299.0,
        "duration_days": 36500,
        "is_lifetime": True,
        "daily_signal_limit": 999,
        "features_en": [
            "Unlimited Lifetime access to all current and future AI features",
            "No recurring fees or monthly renewals",
            "Permanent non-expiring VIP Channel access",
            "Direct API Webhook access for algorithmic trading",
            "VIP Private Discord / Telegram Mastermind group"
        ],
        "features_kh": [
            "ទទួលបានសិទ្ធិប្រើប្រាស់ពេញមួយជីវិត មិនបាច់បង់ប្រចាំខែ",
            "ការចូលរួម VIP Channel ជាអចិន្ត្រៃយ៍",
            "សិទ្ធិប្រើប្រាស់ API Webhook សម្រាប់ការជួញដូរស្វ័យប្រវត្ត",
            "ការចូលរួមក្រុមសម្ងាត់ Mastermind ពិសេស"
        ]
    }
}


class VIPManager:
    """
    Core engine managing VIP tiers, expiring Telegram invite links,
    and automatic subscription lifecycle enforcement.
    """

    def __init__(self, telegram_service: Optional[TelegramService] = None):
        self._custom_telegram = telegram_service
        self.default_vip_channel_id = VIP_TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID or "-1004341134868"
        self.admin_username = TELEGRAM_ADMIN_USERNAME
        self.bakong_account = BAKONG_KHQR_ACCOUNT
        self.usdt_wallet = USDT_TRC20_WALLET

    @property
    def telegram(self) -> TelegramService:
        return self._custom_telegram or default_telegram_service

    def get_tiers(self) -> Dict[str, Any]:
        """Returns all configured tiers with pricing and feature lists."""
        return SUBSCRIPTION_TIERS

    def get_user_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Returns the active or latest subscription for a given Telegram user ID."""
        user_str = str(user_id).strip()
        db = SessionLocal()
        try:
            sub = db.query(VIPSubscriptionModel).filter(
                VIPSubscriptionModel.user_id == user_str
            ).order_by(VIPSubscriptionModel.created_at.desc()).first()
            if not sub:
                return None
            return self._model_to_dict(sub)
        finally:
            db.close()

    def list_subscribers(
        self,
        status: Optional[str] = None,
        tier: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Lists subscribers filtered by status and tier."""
        db = SessionLocal()
        try:
            q = db.query(VIPSubscriptionModel)
            if status:
                q = q.filter(VIPSubscriptionModel.status == status.upper())
            if tier:
                q = q.filter(VIPSubscriptionModel.tier == tier.upper())
            results = q.order_by(VIPSubscriptionModel.created_at.desc()).offset(offset).limit(limit).all()
            return [self._model_to_dict(s) for s in results]
        finally:
            db.close()

    def grant_subscription(
        self,
        user_id: str | int,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
        tier: str = "PRO",
        duration_days: Optional[int] = None,
        channel_id: Optional[str] = None,
        payment_ref: Optional[str] = None,
        payment_amount: Optional[float] = None,
        payment_currency: str = "USD",
        notes: Optional[str] = None,
        send_telegram_alert: bool = True
    ) -> Dict[str, Any]:
        """
        Grants a VIP subscription:
        1. Calculates validity timestamps.
        2. Generates a personalized single-use auto-expiring Telegram invite link.
        3. Saves persistent subscription and invite link audit records in the database.
        4. Dispatches bilingual welcome & access notification with 1-click Join button.
        """
        user_str = str(user_id).strip()
        tier_key = tier.upper() if tier else "PRO"
        if tier_key not in SUBSCRIPTION_TIERS:
            tier_key = "PRO"

        tier_info = SUBSCRIPTION_TIERS[tier_key]
        is_lifetime = tier_info.get("is_lifetime", False)
        days = duration_days if duration_days is not None else tier_info.get("duration_days", 30)
        target_channel = str(channel_id or self.default_vip_channel_id).strip()
        cost = payment_amount if payment_amount is not None else tier_info.get("price_usd", 0.0)

        now = _now_utc()
        starts_at = now
        expires_at = None if is_lifetime else (now + datetime.timedelta(days=days))

        # Generate Telegram single-use expiring invite link
        # Expire the link after 72 hours (or subscription duration if shorter)
        link_expire_seconds = min(72 * 3600, max(3600, days * 86400)) if not is_lifetime else (7 * 86400)
        expire_unix = int(now.timestamp()) + link_expire_seconds
        link_name = f"VIP-{user_str[:8]}-{tier_key}"

        invite_link_url = None
        link_error = None
        ok, invite_link_url, link_error = self.telegram.create_chat_invite_link(
            chat_id=target_channel,
            name=link_name,
            expire_date=expire_unix,
            member_limit=1
        )

        if not ok or not invite_link_url:
            logger.warning(f"Could not generate Telegram invite link for {user_str}: {link_error}. Falling back to default channel link.")
            invite_link_url = f"https://t.me/c/{target_channel.replace('-100', '')}" if target_channel.startswith("-100") else f"https://t.me/{target_channel.lstrip('@')}"

        db = SessionLocal()
        try:
            # Check for existing active record for user
            existing = db.query(VIPSubscriptionModel).filter(
                VIPSubscriptionModel.user_id == user_str,
                VIPSubscriptionModel.channel_id == target_channel
            ).first()

            if existing:
                existing.username = username or existing.username
                existing.full_name = full_name or existing.full_name
                existing.tier = tier_key
                existing.status = "ACTIVE"
                existing.invite_link = invite_link_url
                existing.invite_link_name = link_name
                existing.starts_at = starts_at
                existing.expires_at = expires_at
                existing.duration_days = days
                existing.is_lifetime = is_lifetime
                existing.payment_reference = payment_ref or existing.payment_reference
                existing.payment_amount = cost
                existing.payment_currency = payment_currency
                existing.is_revoked = False
                existing.revoked_at = None
                existing.revoked_reason = None
                existing.last_reminded_at = None
                existing.notes = notes or existing.notes
                existing.updated_at = now
                sub_record = existing
            else:
                sub_record = VIPSubscriptionModel(
                    user_id=user_str,
                    username=username,
                    full_name=full_name,
                    tier=tier_key,
                    status="ACTIVE",
                    channel_id=target_channel,
                    invite_link=invite_link_url,
                    invite_link_name=link_name,
                    member_limit=1,
                    duration_days=days,
                    is_lifetime=is_lifetime,
                    starts_at=starts_at,
                    expires_at=expires_at,
                    payment_reference=payment_ref,
                    payment_amount=cost,
                    payment_currency=payment_currency,
                    notes=notes,
                    created_at=now,
                    updated_at=now
                )
                db.add(sub_record)

            # Record in invite links ledger if not already present
            existing_link = db.query(VIPInviteLinkRecord).filter(VIPInviteLinkRecord.invite_link == invite_link_url).first()
            if not existing_link:
                link_record = VIPInviteLinkRecord(
                    invite_link=invite_link_url,
                    channel_id=target_channel,
                    user_id=user_str,
                    tier=tier_key,
                    name=link_name,
                    expire_date_unix=expire_unix,
                    member_limit=1,
                    created_at=now
                )
                db.add(link_record)
            db.commit()
            db.refresh(sub_record)
            res_dict = self._model_to_dict(sub_record)
        finally:
            db.close()

        # Send Telegram notification if requested
        if send_telegram_alert and user_str:
            self._send_welcome_notification(user_str, res_dict, tier_info, invite_link_url)

        return res_dict

    def renew_subscription(
        self,
        user_id: str | int,
        duration_days: int = 30,
        payment_ref: Optional[str] = None,
        payment_amount: Optional[float] = None,
        payment_currency: str = "USD"
    ) -> Dict[str, Any]:
        """
        Extends an existing subscription or reactivates an expired subscription.
        """
        user_str = str(user_id).strip()
        now = _now_utc()
        db = SessionLocal()
        try:
            sub = db.query(VIPSubscriptionModel).filter(
                VIPSubscriptionModel.user_id == user_str
            ).order_by(VIPSubscriptionModel.created_at.desc()).first()

            if not sub:
                return self.grant_subscription(
                    user_id=user_str,
                    tier="PRO",
                    duration_days=duration_days,
                    payment_ref=payment_ref,
                    payment_amount=payment_amount,
                    payment_currency=payment_currency
                )

            # Determine new expiration date
            tier_info = SUBSCRIPTION_TIERS.get(sub.tier, SUBSCRIPTION_TIERS["PRO"])
            exp_dt = _normalize_utc_dt(sub.expires_at)
            if sub.is_lifetime:
                new_expires_at = None
            elif sub.status == "ACTIVE" and exp_dt and exp_dt > now:
                new_expires_at = exp_dt + datetime.timedelta(days=duration_days)
            else:
                new_expires_at = now + datetime.timedelta(days=duration_days)

            # Check if a new invite link is needed (e.g. if was previously revoked or expired)
            need_new_link = sub.status in ["EXPIRED", "REVOKED", "CANCELLED"]
            if need_new_link:
                link_name = f"VIP-{user_str[:8]}-{sub.tier}-RENEW"
                expire_unix = int(now.timestamp()) + (72 * 3600)
                ok, new_link, _ = self.telegram.create_chat_invite_link(
                    chat_id=sub.channel_id,
                    name=link_name,
                    expire_date=expire_unix,
                    member_limit=1
                )
                if ok and new_link:
                    sub.invite_link = new_link
                    sub.invite_link_name = link_name
                    existing_l = db.query(VIPInviteLinkRecord).filter(VIPInviteLinkRecord.invite_link == new_link).first()
                    if not existing_l:
                        db.add(VIPInviteLinkRecord(
                            invite_link=new_link,
                            channel_id=sub.channel_id,
                            user_id=user_str,
                            tier=sub.tier,
                            name=link_name,
                            expire_date_unix=expire_unix,
                            member_limit=1,
                            created_at=now
                        ))

            sub.status = "ACTIVE"
            sub.expires_at = new_expires_at
            sub.duration_days = duration_days
            sub.last_reminded_at = None
            sub.is_revoked = False
            sub.revoked_at = None
            sub.revoked_reason = None
            if payment_ref:
                sub.payment_reference = payment_ref
            if payment_amount is not None:
                sub.payment_amount = payment_amount
            sub.payment_currency = payment_currency
            sub.updated_at = now

            db.commit()
            db.refresh(sub)
            res_dict = self._model_to_dict(sub)
        finally:
            db.close()

        # Send renewal confirmation message
        self._send_renewal_notification(user_str, res_dict, tier_info)
        return res_dict

    def revoke_subscription(
        self,
        user_id: str | int,
        reason: str = "Admin revoked",
        kick_from_channel: bool = True
    ) -> Dict[str, Any]:
        """
        Revokes VIP subscription, invalidates invite link, and removes user from VIP channel.
        """
        user_str = str(user_id).strip()
        now = _now_utc()
        db = SessionLocal()
        try:
            sub = db.query(VIPSubscriptionModel).filter(
                VIPSubscriptionModel.user_id == user_str
            ).order_by(VIPSubscriptionModel.created_at.desc()).first()

            if not sub:
                return {"status": "NOT_FOUND", "message": f"No subscription found for user {user_str}"}

            sub.status = "REVOKED"
            sub.is_revoked = True
            sub.revoked_at = now
            sub.revoked_reason = reason
            sub.updated_at = now

            # Revoke link if exists
            if sub.invite_link:
                self.telegram.revoke_chat_invite_link(sub.channel_id, sub.invite_link)

            # Kick from channel
            if kick_from_channel and sub.channel_id:
                self.telegram.kick_chat_member(sub.channel_id, user_str)

            db.commit()
            db.refresh(sub)
            res_dict = self._model_to_dict(sub)
        finally:
            db.close()

        # Notify user
        try:
            self.telegram.send_message(
                text=f"""⚠️ <b>VIP SUBSCRIPTION REVOKED</b>
━━━━━━━━━━━━━━━━━━━━
Your VIP access for <b>{res_dict.get('tier')}</b> has been revoked.
Reason: <i>{reason}</i>

🇰🇭 <b>ភាសាខ្មែរ:</b>
សមាជិកភាព VIP របស់អ្នកត្រូវបានបញ្ឈប់ដោយ៖ {reason}។
ប្រសិនបើមានចម្ងល់ សូមទាក់ទង @{self.admin_username}។""",
                chat_id=user_str
            )
        except Exception:
            pass

        return res_dict

    def check_and_process_expirations(self) -> Dict[str, Any]:
        """
        Background Sentinel Task:
        1. Detects expired active subscriptions -> kicks from VIP channel & marks EXPIRED.
        2. Detects subscriptions expiring within 24 hours -> sends friendly renewal reminders.
        """
        now = _now_utc()
        expired_count = 0
        reminded_count = 0
        checked_count = 0

        db = SessionLocal()
        try:
            active_subs = db.query(VIPSubscriptionModel).filter(
                VIPSubscriptionModel.status == "ACTIVE",
                VIPSubscriptionModel.is_lifetime == False,
                VIPSubscriptionModel.expires_at != None
            ).all()

            checked_count = len(active_subs)

            for sub in active_subs:
                exp_dt = _normalize_utc_dt(sub.expires_at)
                if not exp_dt:
                    continue

                # 1. Check for expired
                if exp_dt <= now:
                    logger.info(f"Subscription expired for user {sub.user_id} (expired at {sub.expires_at})")
                    sub.status = "EXPIRED"
                    sub.updated_at = now

                    # Revoke link
                    if sub.invite_link:
                        try:
                            self.telegram.revoke_chat_invite_link(sub.channel_id, sub.invite_link)
                        except Exception:
                            pass

                    # Kick member out of channel
                    if sub.channel_id:
                        try:
                            self.telegram.kick_chat_member(sub.channel_id, sub.user_id)
                        except Exception as e:
                            logger.warning(f"Could not kick expired member {sub.user_id}: {e}")

                    # Notify user of expiration
                    self._send_expired_notification(sub.user_id, self._model_to_dict(sub))
                    expired_count += 1

                # 2. Check for upcoming expiration (<= 24 hours)
                elif exp_dt > now:
                    diff_seconds = (exp_dt - now).total_seconds()
                    if diff_seconds <= (24 * 3600) and sub.last_reminded_at is None:
                        logger.info(f"Sending 24h expiration reminder to user {sub.user_id}")
                        sub.last_reminded_at = now
                        sub.updated_at = now
                        self._send_pre_expiry_reminder(sub.user_id, self._model_to_dict(sub), int(diff_seconds // 3600))
                        reminded_count += 1

            db.commit()
        finally:
            db.close()

        return {
            "status": "COMPLETED",
            "checked_count": checked_count,
            "expired_count": expired_count,
            "reminded_count": reminded_count,
            "timestamp_utc": now.isoformat()
        }

    def get_vip_stats(self) -> Dict[str, Any]:
        """Calculates global VIP membership metrics for executive dashboard."""
        now = _now_utc()
        db = SessionLocal()
        try:
            total_all = db.query(VIPSubscriptionModel).count()
            active_count = db.query(VIPSubscriptionModel).filter(VIPSubscriptionModel.status == "ACTIVE").count()
            expired_count = db.query(VIPSubscriptionModel).filter(VIPSubscriptionModel.status == "EXPIRED").count()
            revoked_count = db.query(VIPSubscriptionModel).filter(VIPSubscriptionModel.status == "REVOKED").count()

            # Breakdown by tier
            tier_breakdown: Dict[str, int] = {}
            for t in SUBSCRIPTION_TIERS.keys():
                tier_breakdown[t] = db.query(VIPSubscriptionModel).filter(
                    VIPSubscriptionModel.status == "ACTIVE",
                    VIPSubscriptionModel.tier == t
                ).count()

            # Expiring soon (within 48 hours)
            limit_48h = now + datetime.timedelta(hours=48)
            active_non_life = db.query(VIPSubscriptionModel).filter(
                VIPSubscriptionModel.status == "ACTIVE",
                VIPSubscriptionModel.is_lifetime == False
            ).all()
            expiring_soon = 0
            for s in active_non_life:
                exp_dt = _normalize_utc_dt(s.expires_at)
                if exp_dt and now < exp_dt <= limit_48h:
                    expiring_soon += 1

            # Total revenue
            all_subs = db.query(VIPSubscriptionModel).all()
            total_rev = sum(s.payment_amount or 0.0 for s in all_subs)

            return {
                "total_subscribers": total_all,
                "active_subscribers": active_count,
                "expired_subscribers": expired_count,
                "revoked_subscribers": revoked_count,
                "expiring_within_48h": expiring_soon,
                "tier_breakdown": tier_breakdown,
                "total_revenue_usd": round(total_rev, 2),
                "timestamp_utc": now.isoformat()
            }
        finally:
            db.close()

    # -------------------------------------------------------------
    # Telegram Message & Keyboard Builders
    # -------------------------------------------------------------

    def build_plans_message(self) -> str:
        """Constructs bilingual presentation of all VIP subscription tiers."""
        lines = [
            "👑 <b>TAIKRY VIP SUBSCRIPTION TIERS & MEMBERSHIP</b>",
            "🇰🇭 <b>កញ្ចប់សមាជិកភាព VIP និងសញ្ញាជួញដូរមាស XAUUSD ស្ថាប័ន</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            "ជ្រើសរើសកញ្ចប់ដែលស័ក្តិសមជាមួយគោលដៅជួញដូររបស់អ្នក៖\n"
        ]

        for code, info in SUBSCRIPTION_TIERS.items():
            badge = info.get("badge", code)
            cost_str = f"${info['price_usd']:,.0f}" if info['price_usd'] > 0 else "ឥតគិតថ្លៃ (FREE)"
            dur_str = f"{info['duration_days']} ថ្ងៃ" if info['duration_days'] > 0 else "មួយជីវិត (Lifetime)"
            lines.append(f"<b>{badge}</b> — <b>{cost_str}</b> ({dur_str})")
            lines.append(f"• 🇰🇭 <i>{info['name_kh']}</i>")
            # First 2 key features
            for f in info["features_kh"][:2]:
                lines.append(f"  ✓ {f}")
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("💳 <b>Payment Methods:</b> Bakong KHQR, USDT (TRC-20)")
        lines.append(f"📞 <b>Admin Support:</b> @{self.admin_username}")
        lines.append("🤖 <i>TAIKRY AI 24/7 AUTO SENTINEL</i>")
        return "\n".join(lines)

    def build_plans_keyboard(self) -> Dict[str, Any]:
        """Constructs interactive inline keyboard for choosing tiers."""
        keyboard = [
            [
                {"text": "🥈 Pro VIP ($49 / 30 ថ្ងៃ)", "callback_data": "sub:tier:PRO"},
                {"text": "🥇 Elite VIP ($129 / 90 ថ្ងៃ)", "callback_data": "sub:tier:VIP"}
            ],
            [
                {"text": "👑 Lifetime Access ($299 មួយជីវិត)", "callback_data": "sub:tier:LIFETIME"}
            ],
            [
                {"text": "💳 ពិនិត្យសមាជិកភាពខ្ញុំ (My Plan)", "callback_data": "sub:myplan"},
                {"text": "📞 ជំនួយការ / Contact Admin", "callback_data": "sub:support"}
            ]
        ]
        return {"inline_keyboard": keyboard}

    def build_tier_details_message(self, tier_code: str) -> str:
        """Constructs full detailed specification and payment options for a tier."""
        tier_key = tier_code.upper()
        info = SUBSCRIPTION_TIERS.get(tier_key, SUBSCRIPTION_TIERS["PRO"])
        badge = info.get("badge", tier_key)
        cost_str = f"${info['price_usd']:,.0f} USD" if info['price_usd'] > 0 else "FREE"
        dur_str = f"{info['duration_days']} Days" if info['duration_days'] > 0 else "Permanent Lifetime"

        en_feats = "\n".join([f"• {f}" for f in info["features_en"]])
        kh_feats = "\n".join([f"• {f}" for f in info["features_kh"]])

        text = f"""{badge}
<b>Plan:</b> {info['name_en']}
<b>តម្លៃ / Cost:</b> <b>{cost_str}</b>
<b>សុពលភាព / Duration:</b> {dur_str}
━━━━━━━━━━━━━━━━━━━━
🇰🇭 <b>អត្ថប្រយោជន៍ និងមុខងារពិសេស:</b>
{kh_feats}

🇬🇧 <b>Institutional Specifications:</b>
{en_feats}
━━━━━━━━━━━━━━━━━━━━
💳 <b>វិធីសាស្រ្តបង់ប្រាក់ (Payment Options):</b>
1. <b>Bakong KHQR (ABA / ACLEDA / Canadia):</b> <code>{self.bakong_account}</code>
2. <b>USDT TRC-20 Address:</b>
<code>{self.usdt_wallet}</code>

បន្ទាប់ពីផ្ទេរប្រាក់រួច សូមចុចប៊ូតុង <b>«ផ្ញើភស្តុតាងបង់ប្រាក់»</b> ឬទាក់ទងមកកាន់ @{self.admin_username} ដើម្បីទទួលបានតំណភ្ជាប់ចូល VIP ភ្លាមៗ!"""
        return text

    def build_tier_details_keyboard(self, tier_code: str) -> Dict[str, Any]:
        """Builds action buttons for payment confirmation and back."""
        tier_key = tier_code.upper()
        keyboard = [
            [
                {"text": "🇰🇭 បង់ប្រាក់តាម Bakong KHQR", "callback_data": f"sub:pay:bakong:{tier_key}"},
                {"text": "🌐 បង់ប្រាក់តាម USDT TRC20", "callback_data": f"sub:pay:usdt:{tier_key}"}
            ],
            [
                {"text": "✅ ខ្ញុំបានបង់ប្រាក់រួច (Submit Proof)", "callback_data": f"sub:submitproof:{tier_key}"}
            ],
            [
                {"text": "⬅️ ត្រឡប់ក្រោយ (Back to Plans)", "callback_data": "sub:plans"}
            ]
        ]
        return {"inline_keyboard": keyboard}

    def build_payment_message(self, method: str, tier_code: str) -> str:
        """Generates dedicated payment guide with copyable credentials."""
        tier_key = tier_code.upper()
        info = SUBSCRIPTION_TIERS.get(tier_key, SUBSCRIPTION_TIERS["PRO"])
        price = info.get("price_usd", 49.0)

        if method.lower() == "bakong":
            text = f"""🇰🇭 <b>ការបង់ប្រាក់តាម BAKONG KHQR</b>
━━━━━━━━━━━━━━━━━━━━
🎯 <b>កញ្ចប់:</b> {info.get('badge')}
💵 <b>ចំនួនទឹកប្រាក់:</b> <b>${price:,.2f} USD</b>
🏦 <b>Bakong Account:</b> <code>{self.bakong_account}</code>
👤 <b>ឈ្មោះគណនី:</b> TAIKRY AI TRADING SYSTEM
📝 <b>Remark / សម្គាល់:</b> សូមដាក់ Telegram User ID ឬ Username របស់អ្នក

📸 <b>របៀបធ្វើ:</b>
1. បើកកម្មវិធីធនាគាររបស់អ្នក (ABA, ACLEDA, Sathapana, etc.)
2. ផ្ទេរប្រាក់ចំនួន ${price:,.2f} ទៅកាន់គណនី Bakong ខាងលើ
3. ថត Screenshot បង្កាន់ដៃផ្ទេរប្រាក់ ហើយផ្ញើមកកាន់ @{self.admin_username}
4. ប្រព័ន្ធនឹងផ្ញើតំណភ្ជាប់ VIP Invite Link ចូល Channel ដោយស្វ័យប្រវត្ត!"""
        else:
            text = f"""🌐 <b>ការបង់ប្រាក់តាម USDT (TRC-20)</b>
━━━━━━━━━━━━━━━━━━━━
🎯 <b>កញ្ចប់:</b> {info.get('badge')}
💵 <b>ចំនួនទឹកប្រាក់:</b> <b>${price:,.2f} USDT</b>
🔗 <b>Network:</b> TRON (TRC-20)
📥 <b>Deposit Address:</b>
<code>{self.usdt_wallet}</code>

⚠️ <i>សូមផ្ទៀងផ្ទាត់ Network ឱ្យបានត្រឹមត្រូវ (TRC-20) មុនពេលផ្ញើ។</i>

📸 <b>របៀបធ្វើ:</b>
1. ផ្ទេរចំនួន ${price:,.2f} USDT ទៅកាន់ Address ខាងលើ
2. ចម្លង Transaction Hash (TxID) ហើយផ្ញើមកកាន់ @{self.admin_username}
3. តំណភ្ជាប់ចូល VIP Channel នឹងត្រូវបានបញ្ជូនមកកាន់លោកអ្នកភ្លាមៗ!"""
        return text

    def build_user_status_message(self, user_id: str | int) -> Tuple[str, Dict[str, Any]]:
        """Constructs personalized subscription status card."""
        sub = self.get_user_subscription(str(user_id))
        if not sub or sub.get("status") not in ["ACTIVE"]:
            text = f"""ℹ️ <b>ស្ថានភាពសមាជិកភាព VIP (MEMBERSHIP STATUS)</b>
━━━━━━━━━━━━━━━━━━━━
👤 <b>User ID:</b> <code>{user_id}</code>
📊 <b>ស្ថានភាព:</b> <b>គ្មានសមាជិកភាពសកម្ម (NO ACTIVE VIP)</b>
🏷️ <b>Plan បច្ចុប្បន្ន:</b> Community Free Tier

ប្រសិនបើអ្នកចង់ទទួលបានសញ្ញាជួញដូរមាស XAUUSD ពី AI Consensus សូមចុចប៊ូតុងខាងក្រោមដើម្បីពិនិត្យកញ្ចប់ VIP៖"""
            keyboard = {
                "inline_keyboard": [
                    [{"text": "👑 ពិនិត្យកញ្ចប់ VIP Plans", "callback_data": "sub:plans"}],
                    [{"text": "📞 ទាក់ទង Admin", "callback_data": "sub:support"}]
                ]
            }
            return text, keyboard

        tier_code = sub.get("tier", "PRO")
        info = SUBSCRIPTION_TIERS.get(tier_code, SUBSCRIPTION_TIERS["PRO"])
        badge = info.get("badge", tier_code)
        is_life = sub.get("is_lifetime", False)
        expires_str = "មួយជីវិត (Never Expires)" if is_life else _to_gmt7_str(datetime.datetime.fromisoformat(sub["expires_at"]) if sub.get("expires_at") else None)

        days_left_str = "អចិន្ត្រៃយ៍"
        if not is_life and sub.get("expires_at"):
            exp_dt = datetime.datetime.fromisoformat(sub["expires_at"])
            now = _now_utc()
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=datetime.timezone.utc)
            delta = exp_dt - now
            days_left = max(0, delta.days)
            hours_left = max(0, int(delta.seconds // 3600))
            days_left_str = f"{days_left} ថ្ងៃ {hours_left} ម៉ោង"

        invite_link = sub.get("invite_link") or "https://t.me/c/-1004341134868"

        text = f"""👑 <b>ព័ត៌មានលម្អិតសមាជិកភាព VIP</b>
━━━━━━━━━━━━━━━━━━━━
👤 <b>User ID:</b> <code>{user_id}</code>
🏷️ <b>កញ្ចប់សមាជិក:</b> <b>{badge}</b>
🟢 <b>ស្ថានភាព:</b> <b>សកម្ម (ACTIVE)</b>
⏳ <b>រយៈពេលនៅសល់:</b> <b>{days_left_str}</b>
📅 <b>កាលបរិច្ឆេទផុតកំណត់:</b> {expires_str}
🎫 <b>Channel:</b> <code>{sub.get('channel_id')}</code>

🔗 <b>តំណភ្ជាប់ចូល VIP Channel (1-Time Expiring Link):</b>
{invite_link}
━━━━━━━━━━━━━━━━━━━━
🤖 <i>TAIKRY AI 24/7 AUTO SENTINEL</i>"""

        keyboard = {
            "inline_keyboard": [
                [{"text": "🚀 ចូលទៅកាន់ VIP Channel ឥឡូវនេះ", "url": invite_link}],
                [{"text": "🔄 បន្តសុពលភាព (Renew Plan)", "callback_data": f"sub:renew:{tier_code}"}],
                [{"text": "⬅️ ត្រឡប់ទៅមឺនុយដើម", "callback_data": "sub:plans"}]
            ]
        }
        return text, keyboard

    # -------------------------------------------------------------
    # Internal Notification Helpers
    # -------------------------------------------------------------

    def _send_welcome_notification(self, user_id: str, sub: Dict[str, Any], tier_info: Dict[str, Any], invite_link: str):
        """Sends congratulations message to new or renewed subscriber."""
        badge = tier_info.get("badge", sub.get("tier"))
        expires_str = "មួយជីវិត (Permanent Access)" if sub.get("is_lifetime") else _to_gmt7_str(datetime.datetime.fromisoformat(sub["expires_at"]) if sub.get("expires_at") else None)

        msg = f"""🎉 <b>សូមអបអរសាទរ! សមាជិកភាព VIP របស់អ្នកត្រូវបានបើកដំណើរការ</b>
━━━━━━━━━━━━━━━━━━━━
👑 <b>កញ្ចប់:</b> <b>{badge}</b>
🟢 <b>ស្ថានភាព:</b> ACTIVE
📅 <b>សុពលភាពរហូតដល់:</b> {expires_str}

🚀 <b>តំណភ្ជាប់ចូល VIP CHANNEL របស់អ្នក:</b>
{invite_link}

⚠️ <i>ចំណាំ៖ តំណភ្ជាប់នេះមានសុពលភាពសម្រាប់ប្រើតែម្តង (1-Time Use) និងផុតកំណត់ក្នុងរយៈពេល 72 ម៉ោង។ សូមចុច Join ឥឡូវនេះ!</i>

🇰🇭 <b>អត្ថប្រយោជន៍ដែលអ្នកទទួលបាន:</b>
✓ សញ្ញាជួញដូរ XAUUSD ពី AI Consensus ស្ថាប័ន
✓ កម្រិត Entry, SL, TP1, TP2, TP3 ជាមួយ R:R >= 1:2.0
✓ ការជូនដំណឹងគ្រប់ដំណាក់កាលនៃ Price Action ផ្ទាល់ 24/7
━━━━━━━━━━━━━━━━━━━━
🤖 <i>TAIKRY AI MARKET INTELLIGENCE PRO</i>"""

        buttons = {
            "inline_keyboard": [
                [{"text": "🚀 ចូល VIP Channel ឥឡូវនេះ", "url": invite_link}],
                [{"text": "💳 ពិនិត្យសមាជិកភាពខ្ញុំ", "callback_data": "sub:myplan"}]
            ]
        }
        try:
            self.telegram.send_message(text=msg, chat_id=user_id, reply_markup=buttons)
        except Exception as e:
            logger.warning(f"Could not dispatch VIP welcome to user {user_id}: {e}")

    def _send_renewal_notification(self, user_id: str, sub: Dict[str, Any], tier_info: Dict[str, Any]):
        """Sends renewal confirmation message."""
        badge = tier_info.get("badge", sub.get("tier"))
        expires_str = "មួយជីវិត (Permanent Access)" if sub.get("is_lifetime") else _to_gmt7_str(datetime.datetime.fromisoformat(sub["expires_at"]) if sub.get("expires_at") else None)
        invite_link = sub.get("invite_link")

        msg = f"""✅ <b>ការបន្តសុពលភាព VIP បានជោគជ័យ!</b>
━━━━━━━━━━━━━━━━━━━━
👑 <b>កញ្ចប់:</b> <b>{badge}</b>
🟢 <b>ស្ថានភាព:</b> ACTIVE
📅 <b>កាលបរិច្ឆេទផុតកំណត់ថ្មី:</b> {expires_str}

សូមអរគុណសម្រាប់ការបន្តគាំទ្រ TAIKRY AI MARKET INTELLIGENCE PRO! ប្រព័ន្ធនឹងបន្តបញ្ជូនសញ្ញាជួញដូរមាស XAUUSD ជូនលោកអ្នកដោយគ្មានការរំខាន។"""

        buttons = {
            "inline_keyboard": [
                [{"text": "💳 ពិនិត្យស្ថានភាពគណនី", "callback_data": "sub:myplan"}]
            ]
        }
        if invite_link:
            buttons["inline_keyboard"].insert(0, [{"text": "🚀 ចូល VIP Channel", "url": invite_link}])

        try:
            self.telegram.send_message(text=msg, chat_id=user_id, reply_markup=buttons)
        except Exception as e:
            logger.warning(f"Could not dispatch renewal notice to user {user_id}: {e}")

    def _send_pre_expiry_reminder(self, user_id: str, sub: Dict[str, Any], hours_left: int):
        """Sends pre-expiration warning (24h before expiry)."""
        badge = sub.get("tier", "PRO")
        expires_str = _to_gmt7_str(datetime.datetime.fromisoformat(sub["expires_at"]) if sub.get("expires_at") else None)

        msg = f"""⏳ <b>ការរំលឹក៖ សមាជិកភាព VIP របស់អ្នកជិតផុតកំណត់</b>
━━━━━━━━━━━━━━━━━━━━
👑 <b>កញ្ចប់:</b> {badge}
⚠️ <b>ពេលវេលានៅសល់:</b> ប្រហែល <b>{hours_left} ម៉ោងទៀត</b>
📅 <b>កាលបរិច្ឆេទផុតកំណត់:</b> {expires_str}

ដើម្បីកុំឱ្យខកខានសញ្ញាជួញដូរមាស XAUUSD និងការតាមដានទីផ្សារ សូមចុចប៊ូតុង <b>«បន្តសុពលភាព»</b> ខាងក្រោម ឬទាក់ទងមកកាន់ @{self.admin_username}។"""

        buttons = {
            "inline_keyboard": [
                [{"text": "🔄 បន្តសុពលភាព (Renew Now)", "callback_data": f"sub:renew:{sub.get('tier')}"}],
                [{"text": "📞 ទាក់ទង Admin", "callback_data": "sub:support"}]
            ]
        }
        try:
            self.telegram.send_message(text=msg, chat_id=user_id, reply_markup=buttons)
        except Exception as e:
            logger.warning(f"Could not dispatch pre-expiry reminder to user {user_id}: {e}")

    def _send_expired_notification(self, user_id: str, sub: Dict[str, Any]):
        """Sends expiration notification when access is revoked."""
        badge = sub.get("tier", "PRO")
        msg = f"""⚠️ <b>សមាជិកភាព VIP របស់អ្នកបានផុតកំណត់ហើយ</b>
━━━━━━━━━━━━━━━━━━━━
👑 <b>កញ្ចប់:</b> {badge}
🛑 <b>ស្ថានភាព:</b> EXPIRED

គណនីរបស់អ្នកត្រូវបានដកចេញពី VIP Signal Channel ជាបណ្តោះអាសន្ន។
ប្រសិនបើអ្នកចង់បន្តទទួលបានសញ្ញា និងស្ថិតិជួញដូរ សូមចុចប៊ូតុងខាងក្រោមដើម្បីជ្រើសរើសកញ្ចប់ និងបន្តសុពលភាព៖"""

        buttons = {
            "inline_keyboard": [
                [{"text": "👑 បន្តសុពលភាព VIP", "callback_data": "sub:plans"}],
                [{"text": "📞 ជំនួយការ / Contact Admin", "callback_data": "sub:support"}]
            ]
        }
        try:
            self.telegram.send_message(text=msg, chat_id=user_id, reply_markup=buttons)
        except Exception as e:
            logger.warning(f"Could not dispatch expired notice to user {user_id}: {e}")

    def _model_to_dict(self, model: VIPSubscriptionModel) -> Dict[str, Any]:
        """Converts SQLAlchemy model instance to clean JSON-safe dictionary."""
        return {
            "id": model.id,
            "user_id": model.user_id,
            "username": model.username,
            "full_name": model.full_name,
            "tier": model.tier,
            "status": model.status,
            "channel_id": model.channel_id,
            "invite_link": model.invite_link,
            "invite_link_name": model.invite_link_name,
            "member_limit": model.member_limit,
            "duration_days": model.duration_days,
            "is_lifetime": bool(model.is_lifetime),
            "starts_at": model.starts_at.isoformat() if model.starts_at else None,
            "expires_at": model.expires_at.isoformat() if model.expires_at else None,
            "last_reminded_at": model.last_reminded_at.isoformat() if model.last_reminded_at else None,
            "payment_reference": model.payment_reference,
            "payment_amount": model.payment_amount,
            "payment_currency": model.payment_currency,
            "is_revoked": bool(model.is_revoked),
            "revoked_at": model.revoked_at.isoformat() if model.revoked_at else None,
            "revoked_reason": model.revoked_reason,
            "notes": model.notes,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None
        }


# Global singleton instance
vip_subscription_manager = VIPManager()
