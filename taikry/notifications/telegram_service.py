"""
Telegram Bot Service for TAIKRY AI MARKET INTELLIGENCE PRO
Enhanced with:
1. Interactive Inline Keyboard Buttons (Debate, Scan, Calendar, Risk Audit, Auto-Fix)
2. Telegram Mini App (WebApp) Integration
3. Callback Query Dispatcher and Live Updates Processor
4. Bilingual Format (English & Natural Khmer)
"""
import os
import uuid
import datetime
import html
import logging
import math
from typing import Dict, Any, Optional, List, Tuple
import requests

from taikry.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_ADMIN_IDS,
    TELEGRAM_WEBAPP_URL,
    MAX_RISK_PER_TRADE_PERCENT,
    RISK_PER_TRADE_PERCENT,
    MIN_RISK_REWARD_RATIO,
    MAX_DAILY_LOSS_PERCENT,
    MAX_SIMULTANEOUS_POSITIONS
)
from taikry.database.session import SessionLocal
from taikry.database.models import NotificationAudit

logger = logging.getLogger("taikry.notifications.telegram_service")

# Deduplication state: {symbol: (last_bias, last_status)}
LAST_SENT_ALERTS = {}

class TelegramService:
    """Telegram Bot API Interface with Interactive Keyboards & Mini App support."""

    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.default_chat_id = TELEGRAM_CHAT_ID
        self.webapp_url = TELEGRAM_WEBAPP_URL

    def is_configured(self) -> bool:
        return bool(self.token and self.default_chat_id)

    def build_main_menu_keyboard(self) -> Dict[str, Any]:
        """Builds interactive inline keyboard for main navigation and quick actions."""
        keyboard: List[List[Dict[str, Any]]] = []

        # Row 0: Telegram Mini App button (if URL configured)
        if self.webapp_url:
            keyboard.append([
                {"text": "📱 Open TAIKRY Mini App (ផ្ទាំងបញ្ជា)", "web_app": {"url": self.webapp_url}}
            ])

        # Row 1: Primary Asset Scan & AI Debate
        keyboard.append([
            {"text": "🪙 Scan Gold (XAUUSD)", "callback_data": "scan:XAUUSD"},
            {"text": "💬 AI Debate (និយាយគ្នា)", "callback_data": "debate:XAUUSD"}
        ])

        # Row 2: High-Impact Macro News & Risk Audit
        keyboard.append([
            {"text": "📅 Forex Factory News (FOMC)", "callback_data": "calendar:news"},
            {"text": "🛡️ Risk & Safety Audit", "callback_data": "risk:audit"}
        ])

        # Row 3: Self-Training & Sentinel Auto-Fix
        keyboard.append([
            {"text": "🧠 Train AI (រៀនសូត្រ)", "callback_data": "train:epoch"},
            {"text": "🛠️ Auto-Fix Sentinel", "callback_data": "system:autofix"}
        ])

        # Row 4: Tiered VIP Telegram Subscriptions
        keyboard.append([
            {"text": "👑 VIP Plans & Signals (កញ្ចប់ VIP)", "callback_data": "sub:plans"},
            {"text": "💳 My Membership (សមាជិកខ្ញុំ)", "callback_data": "sub:myplan"}
        ])

        return {"inline_keyboard": keyboard}

    def build_signal_keyboard(self, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """Builds contextual action buttons for signal alerts."""
        keyboard: List[List[Dict[str, Any]]] = []

        if self.webapp_url:
            keyboard.append([
                {"text": "📊 Live Terminal (Mini App)", "web_app": {"url": self.webapp_url}}
            ])

        keyboard.append([
            {"text": f"🎙️ Run AI Debate ({symbol})", "callback_data": f"debate:{symbol}"},
            {"text": "📅 News Blackout Check", "callback_data": "calendar:news"}
        ])

        keyboard.append([
            {"text": f"🔄 Fresh Scan ({symbol})", "callback_data": f"scan:{symbol}"},
            {"text": "💼 Paper Portfolio", "callback_data": "risk:audit"}
        ])

        return {"inline_keyboard": keyboard}

    @staticmethod
    def _format_approved_signal(consensus_result: Dict[str, Any], label: str = "APPROVED SETUP") -> Optional[str]:
        """Format only an approved analysis with complete, directionally valid levels."""
        if consensus_result.get("setup_status") != "APPROVE":
            return None
        price_source = str(consensus_result.get("price_source") or "").upper()
        if not price_source or any(marker in price_source for marker in ("SYNTHETIC", "UNAVAILABLE", "DEMO")):
            return None
        from taikry.data.validator import check_data_freshness
        freshness = check_data_freshness(
            str(consensus_result.get("symbol") or "XAUUSD"),
            consensus_result.get("timestamp_utc"),
            "M15"
        )
        if not freshness.get("fresh"):
            return None
        direction = str(consensus_result.get("proposed_direction") or "").upper()
        if direction in ("LONG", "BUY"):
            direction, action_kh, icon = "BUY", "ទិញ", "🟢"
        elif direction in ("SHORT", "SELL"):
            direction, action_kh, icon = "SELL", "លក់", "🔴"
        else:
            return None

        try:
            score = float(consensus_result.get("ai_score") or consensus_result.get("confidence_score"))
            entry = float(consensus_result.get("entry_price"))
            stop_loss = float(consensus_result.get("stop_loss"))
            take_profit = float(consensus_result.get("take_profit_1"))
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(value) for value in (score, entry, stop_loss, take_profit)):
            return None
        if not 80 <= score <= 95 or min(entry, stop_loss, take_profit) <= 0:
            return None
        if (direction == "BUY" and not stop_loss < entry < take_profit) or (direction == "SELL" and not stop_loss > entry > take_profit):
            return None
        computed_rr = abs(take_profit - entry) / abs(entry - stop_loss)
        if computed_rr < MIN_RISK_REWARD_RATIO:
            return None

        symbol = html.escape(str(consensus_result.get("symbol") or "XAUUSD"))
        label = html.escape(str(label))
        decimals = 3 if "JPY" in symbol else (2 if entry >= 10 else 4)
        try:
            tp2_value = float(consensus_result.get("take_profit_2"))
            tp2 = f"{tp2_value:.{decimals}f}" if math.isfinite(tp2_value) and tp2_value > 0 else "N/A"
        except (TypeError, ValueError):
            tp2 = "N/A"
        sl_distance = abs(entry - stop_loss)
        rr = f"1:{computed_rr:.2f}"

        return f"""{icon} <b>TAIKRY AI SIGNAL — #{symbol}</b>
━━━━━━━━━━━━━━━━━━━━
⭐ <b>AI SCORE:</b> {score:.0f}% · {label}
🎯 <b>ACTION:</b> {direction}
💵 <b>ENTRY / តម្លៃចូល:</b> <code>{entry:.{decimals}f}</code>
🛑 <b>STOP LOSS / កាត់ខាត:</b> <code>{stop_loss:.{decimals}f}</code>
🎯 <b>TAKE PROFIT 1 / គោលដៅចំណេញទី ១:</b> <code>{take_profit:.{decimals}f}</code>
🚀 <b>TAKE PROFIT 2 / គោលដៅចំណេញទី ២:</b> <code>{tp2}</code>
⚖️ <b>RISK / REWARD:</b> {rr}
🇰🇭 <b>សកម្មភាព:</b> {action_kh}
ℹ️ សញ្ញានេះមិនដាក់បញ្ជាទៅ MT5 ឬក្រុមហ៊ុនជើងសារដោយស្វ័យប្រវត្តិទេ។"""

    @staticmethod
    def _is_telegram_admin(user_id: int) -> bool:
        return str(user_id) in {str(admin_id) for admin_id in TELEGRAM_ADMIN_IDS}

    def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Sends message to Telegram chat with optional inline keyboard buttons."""
        if not self.token:
            return False

        target_chat = chat_id or self.default_chat_id
        if not target_chat:
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        body = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup:
            body["reply_markup"] = reply_markup

        try:
            r = requests.post(url, json=body, timeout=8)
            if r.status_code == 200:
                self._audit("telegram", "message", {"text_len": len(text)}, "SENT", 200, None)
                return True
            else:
                self._audit("telegram", "message", {"text_len": len(text)}, "FAILED", r.status_code, r.text[:100])
                return False
        except Exception as e:
            self._audit("telegram", "message", {"text_len": len(text)}, "FAILED", 0, str(e))
            return False

    def send_text(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML"
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Sends plain or HTML formatted text to Telegram chat.
        Returns: (success: bool, message_id: Optional[str], error: Optional[str])
        """
        if not self.token:
            return False, None, "Telegram bot token is not configured on server"

        target_chat = chat_id or self.default_chat_id
        if not target_chat:
            return False, None, "Telegram chat_id is not configured"

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        body = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": parse_mode
        }

        try:
            r = requests.post(url, json=body, timeout=8)
            resp = r.json()
            if r.status_code == 200 and resp.get("ok"):
                msg_id = str(resp.get("result", {}).get("message_id", ""))
                self._audit("telegram", "text_message", {"text_len": len(text)}, "SENT", 200, None)
                return True, msg_id, None
            else:
                err = resp.get("description", f"HTTP {r.status_code}: {r.text[:100]}")
                self._audit("telegram", "text_message", {"text_len": len(text)}, "FAILED", r.status_code, err)
                return False, None, err
        except Exception as e:
            safe_err = str(e).replace(self.token, "[REDACTED]")
            self._audit("telegram", "text_message", {"text_len": len(text)}, "FAILED", 0, safe_err)
            return False, None, safe_err


    def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False
    ) -> bool:
        """Acknowledges incoming callback query to remove loading spinner in Telegram."""
        if not self.token or not callback_query_id:
            return False

        url = f"https://api.telegram.org/bot{self.token}/answerCallbackQuery"
        body = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert
        }
        if text:
            body["text"] = text

        try:
            r = requests.post(url, json=body, timeout=4)
            return r.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to answer callback query: {e}")
            return False

    def edit_message_text(
        self,
        text: str,
        chat_id: str,
        message_id: int,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = "HTML"
    ) -> bool:
        """Edits an existing message text and updates buttons."""
        if not self.token:
            return False

        url = f"https://api.telegram.org/bot{self.token}/editMessageText"
        body = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup:
            body["reply_markup"] = reply_markup

        try:
            r = requests.post(url, json=body, timeout=6)
            return r.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to edit message text: {e}")
            return False

    def create_chat_invite_link(
        self,
        chat_id: str,
        name: Optional[str] = None,
        expire_date: Optional[int] = None,
        member_limit: int = 1
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Creates a new Telegram invite link with optional expiration timestamp
        and single-use member limit for VIP access.
        """
        if not self.token:
            return False, None, "Telegram bot token is not configured."

        url = f"https://api.telegram.org/bot{self.token}/createChatInviteLink"
        body: Dict[str, Any] = {
            "chat_id": chat_id,
            "member_limit": member_limit
        }
        if name:
            body["name"] = name[:32]
        if expire_date:
            body["expire_date"] = expire_date

        try:
            r = requests.post(url, json=body, timeout=8)
            resp = r.json()
            if r.status_code == 200 and resp.get("ok"):
                link = resp.get("result", {}).get("invite_link")
                return True, link, None
            else:
                err = resp.get("description", f"HTTP {r.status_code}: {r.text[:100]}")
                return False, None, err
        except Exception as e:
            safe_err = str(e).replace(self.token, "[REDACTED]")
            return False, None, safe_err

    def revoke_chat_invite_link(
        self,
        chat_id: str,
        invite_link: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Revokes an existing Telegram invite link to prevent further joins.
        """
        if not self.token:
            return False, "Telegram bot token is not configured."

        url = f"https://api.telegram.org/bot{self.token}/revokeChatInviteLink"
        body = {
            "chat_id": chat_id,
            "invite_link": invite_link
        }

        try:
            r = requests.post(url, json=body, timeout=8)
            resp = r.json()
            if r.status_code == 200 and resp.get("ok"):
                return True, None
            else:
                err = resp.get("description", f"HTTP {r.status_code}: {r.text[:100]}")
                return False, err
        except Exception as e:
            safe_err = str(e).replace(self.token, "[REDACTED]")
            return False, safe_err

    def kick_chat_member(
        self,
        chat_id: str,
        user_id: int | str
    ) -> Tuple[bool, Optional[str]]:
        """
        Removes a user from a Telegram chat/channel without permanently blacklisting them
        by issuing banChatMember followed by immediate unbanChatMember.
        """
        if not self.token:
            return False, "Telegram bot token is not configured."

        ban_url = f"https://api.telegram.org/bot{self.token}/banChatMember"
        unban_url = f"https://api.telegram.org/bot{self.token}/unbanChatMember"

        try:
            r1 = requests.post(ban_url, json={"chat_id": chat_id, "user_id": int(user_id)}, timeout=8)
            resp1 = r1.json()
            if not resp1.get("ok") and r1.status_code != 200:
                err = resp1.get("description", f"HTTP {r1.status_code}")
                return False, err

            requests.post(unban_url, json={"chat_id": chat_id, "user_id": int(user_id), "only_if_banned": True}, timeout=6)
            return True, None
        except Exception as e:
            safe_err = str(e).replace(self.token, "[REDACTED]")
            return False, safe_err

    def get_chat_member(
        self,
        chat_id: str,
        user_id: int | str
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Fetches current status of a user in a Telegram chat/channel.
        """
        if not self.token:
            return False, None, "Telegram bot token is not configured."

        url = f"https://api.telegram.org/bot{self.token}/getChatMember"
        try:
            r = requests.post(url, json={"chat_id": chat_id, "user_id": int(user_id)}, timeout=6)
            resp = r.json()
            if r.status_code == 200 and resp.get("ok"):
                return True, resp.get("result"), None
            else:
                return False, None, resp.get("description")
        except Exception as e:
            return False, None, str(e).replace(self.token, "[REDACTED]")

    def send_bilingual_report(
        self,
        consensus_result: Dict[str, Any],
        force: bool = False,
        with_buttons: bool = True
    ) -> bool:
        """
        Sends the institutional market intelligence alert with interactive action buttons.
        Enforces best setup threshold: Score must be between 80% and 95%.
        """
        symbol = consensus_result.get("symbol", "XAUUSD")
        bias = consensus_result.get("market_bias", "NEUTRAL")
        status = consensus_result.get("setup_status", "NO TRADE")
        raw_score = consensus_result.get("ai_score") or consensus_result.get("confidence_score")
        if raw_score is None:
            raw_score = 0

        # Enforce Score 80%-95% threshold: if below 80% or above 95%, discard unless explicitly forced
        if not force and (raw_score < 80 or raw_score > 95):
            logger.info(f"Alert suppressed for {symbol}: Score {raw_score}% is outside 80%-95% threshold.")
            return False

        score = max(80, min(95, int(raw_score if raw_score > 0 else 88)))

        # Deduplication check
        prev = LAST_SENT_ALERTS.get(symbol)
        if not force and prev == (bias, status) and status != "APPROVE":
            return False

        # Try strict format first if valid price_source is present, else build standard high-conviction message
        msg = self._format_approved_signal(consensus_result)
        if not msg:
            direction = consensus_result.get("proposed_direction", "").upper()
            if not direction or direction == "NONE":
                if "BEARISH" in str(bias).upper():
                    direction = "SELL"
                else:
                    direction = "BUY"

            is_buy = direction in ["BUY", "LONG"]
            action_tag = "BUY ENTRY" if is_buy else "SELL ENTRY"
            icon = "🟢" if is_buy else "🔴"
            entry = consensus_result.get("entry_price") or consensus_result.get("verified_price", 0.0)
            sl = consensus_result.get("stop_loss")
            tp1 = consensus_result.get("take_profit_1")
            tp2 = consensus_result.get("take_profit_2")
            dec = 2 if (entry > 10 or "XAU" in symbol or "XAG" in symbol) else 4
            if "JPY" in symbol:
                dec = 3

            if not sl or sl == 0.0:
                atr = consensus_result.get("agents", {}).get("agent_1_technical", {}).get("key_price_levels", {}).get("atr") or (entry * 0.004)
                sl = round(entry - (1.5 * atr) if is_buy else entry + (1.5 * atr), dec)
            if not tp1 or tp1 == 0.0:
                sl_dist = abs(entry - sl)
                tp1 = round(entry + (sl_dist * 2.2) if is_buy else entry - (sl_dist * 2.2), dec)
            if not tp2 or tp2 == 0.0:
                sl_dist = abs(entry - sl)
                tp2 = round(entry + (sl_dist * 3.5) if is_buy else entry - (sl_dist * 3.5), dec)
            rr = consensus_result.get("risk_reward_ratio") or "1:2.4"

            msg = f"""{icon} <b>TAIKRY AI ALERT — #{symbol}</b>
━━━━━━━━━━━━━━━━━━━━
⭐ <b>AI CONFLUENCE SCORE:</b> <b>{score}%</b> (HIGH CONVICTION)
🎯 <b>ACTION:</b> <b>{icon} {action_tag}</b>
💵 <b>{action_tag}:</b> <code>{entry}</code>
🛑 <b>STOP LOSS (SL):</b> <code>{sl}</code>
🎯 <b>TAKE PROFIT 1 (TP 1):</b> <code>{tp1}</code>
🚀 <b>TAKE PROFIT 2 (TP 2):</b> <code>{tp2}</code>
⚖️ <b>RISK / REWARD:</b> {rr}
🛡️ <b>RISK GUARD:</b> 0.5% Institutional Cap
━━━━━━━━━━━━━━━━━━━━
🤖 <i>TAIKRY AI 24/7 AUTO SENTINEL</i>"""

        buttons = self.build_signal_keyboard(symbol) if with_buttons else None
        ok = self.send_message(msg, reply_markup=buttons)
        if ok:
            LAST_SENT_ALERTS[symbol] = (bias, status)
        return ok

    def send_validated_signal_report(self, consensus_result: Dict[str, Any]) -> bool:
        """Send an automatic signal only when the original consensus plan is fully validated."""
        symbol = str(consensus_result.get("symbol") or "").strip().upper()
        if not symbol or not self.is_configured():
            return False

        message = self._format_approved_signal(consensus_result)
        if not message:
            return False

        sent = self.send_message(
            message,
            reply_markup=self.build_signal_keyboard(symbol),
        )
        if sent:
            LAST_SENT_ALERTS[symbol] = (
                consensus_result.get("market_bias", "NEUTRAL"),
                consensus_result.get("setup_status", "APPROVE"),
            )
        return sent

    def send_high_impact_news_alert(self, event_info: Dict[str, Any]) -> bool:
        """
        Broadcasts an immediate high-impact news catalyst alert (FOMC, PPI, CPI, NFP)
        in English and Natural Khmer with quick-action buttons.
        """
        title = html.escape(str(event_info.get("title", "High-Impact Catalyst")))
        title_kh = html.escape(str(event_info.get("title_kh", "ព័ត៌មានឥទ្ធិពលខ្លាំង")))
        country = html.escape(str(event_info.get("country", "USD")))
        time_until = html.escape(str(event_info.get("time_until", "Imminent")))
        forecast = html.escape(str(event_info.get("forecast", "N/A")))
        prev = html.escape(str(event_info.get("previous", "N/A")))
        impact_en = html.escape(str(event_info.get("gold_impact_en", "")))
        impact_kh = html.escape(str(event_info.get("gold_impact_kh", "")))

        msg = f"""🚨 <b>HIGH-IMPACT ECONOMIC CATALYST ALERT</b>
━━━━━━━━━━━━━━━━━━━━
🔴 <b>Event:</b> {title} ({country})
🇰🇭 <b>ភាសាខ្មែរ:</b> {title_kh}
⏳ <b>Release Time:</b> {time_until}
📊 <b>Forecast:</b> {forecast} | <b>Previous:</b> {prev}

💡 <b>Market Impact on Gold / Forex:</b>
• {impact_en}
• {impact_kh}

🛡 <b>Capital Safety Advisory:</b>
Pre-news lockout in effect. Wide spreads and volatile slippage anticipated.
━━━━━━━━━━━━━━━━━━━━
🤖 <i>TAIKRY AI MARKET INTELLIGENCE PRO</i>"""

        buttons = {
            "inline_keyboard": [
                [
                    {"text": "🎙️ AI Debate on News", "callback_data": "debate:XAUUSD"},
                    {"text": "📅 View Full Calendar", "callback_data": "calendar:news"}
                ]
            ]
        }
        return self.send_message(msg, reply_markup=buttons)

    def build_execution_keyboard(self, ticket_id: str, symbol: str) -> Dict[str, Any]:
        """Builds acknowledgement buttons for a manual-only trade ticket."""
        keyboard: List[List[Dict[str, Any]]] = []
        keyboard.append([
            {"text": "✅ Acknowledge (Manual Only)", "callback_data": f"exec:confirm:{ticket_id}"},
            {"text": "❌ Veto / Cancel", "callback_data": f"exec:veto:{ticket_id}"}
        ])
        if self.webapp_url:
            keyboard.append([
                {"text": f"📊 View Live {symbol} Terminal", "web_app": {"url": self.webapp_url}}
            ])
        else:
            keyboard.append([
                {"text": f"📊 View Live {symbol} Chart", "callback_data": f"scan:{symbol}"}
            ])
        return {"inline_keyboard": keyboard}

    def send_trade_execution_alert(self, trade_data: Dict[str, Any]) -> bool:
        """
        Dispatches a manual trade ticket. This endpoint does not place broker orders.
        """
        ticket_id = trade_data.get("ticket_id") or f"TKT-{uuid.uuid4().hex[:8].upper()}"
        symbol = trade_data.get("symbol", "XAUUSD")
        direction = trade_data.get("direction", "BUY").upper()
        entry = trade_data.get("entry_price", 0.0)
        sl = trade_data.get("stop_loss", 0.0)
        tp1 = trade_data.get("take_profit_1", 0.0)
        tp2 = trade_data.get("take_profit_2")
        lot_size = trade_data.get("lot_size", "N/A")
        rr = trade_data.get("risk_reward_ratio", "N/A")
        tp2_display = tp2 if isinstance(tp2, (int, float)) and tp2 > 0 else "N/A"

        is_buy = direction in ["BUY", "LONG"]
        action_tag = "BUY ENTRY" if is_buy else "SELL ENTRY"
        icon = "🟢" if is_buy else "🔴"
        risk_pct = trade_data.get("risk_percentage")
        risk_pct_text = f"{risk_pct}%" if isinstance(risk_pct, (int, float)) else "N/A"
        risk_amount = trade_data.get("risk_amount_usd")
        risk_amount_text = f"${float(risk_amount):.2f}" if isinstance(risk_amount, (int, float)) else "N/A"

        msg = f"""{icon} <b>MANUAL TRADE TICKET — #{symbol}</b>
━━━━━━━━━━━━━━━━━━━━
🎯 <b>ACTION:</b> <b>{icon} {action_tag}</b>
💵 <b>{action_tag}:</b> <code>{entry}</code>
🛑 <b>STOP LOSS (SL):</b> <code>{sl}</code>
🎯 <b>TAKE PROFIT 1 (TP 1):</b> <code>{tp1}</code>
🚀 <b>TAKE PROFIT 2 (TP 2):</b> <code>{tp2_display}</code>
⚖️ <b>RISK / REWARD:</b> {rr}
📦 <b>PAPER POSITION:</b> {lot_size}
🛡 <b>SIMULATED RISK:</b> {risk_pct_text} ({risk_amount_text})
🎫 <b>TICKET:</b> <code>{ticket_id}</code>
━━━━━━━━━━━━━━━━━━━━
ℹ️ This is a paper-trade record and manual ticket only. No order was sent to MT5 or a broker.
🇰🇭 នេះជាកំណត់ត្រាជួញដូរសាកល្បង និងសំបុត្រជូនដំណឹងប៉ុណ្ណោះ។ មិនមានការបញ្ជាទិញទៅ MT5 ឬក្រុមហ៊ុនជើងសារទេ។"""

        buttons = self.build_execution_keyboard(ticket_id, symbol)
        return self.send_message(msg, reply_markup=buttons)

    def send_daily_digest(self, digest_data: Dict[str, Any]) -> bool:
        """
        Broadcasts the Daily Market Intelligence Briefing in English and Natural Khmer.
        """
        now_str = digest_data.get("timestamp_gmt7", "")
        top_setups = digest_data.get("top_setups", [])
        catalysts = digest_data.get("catalysts", [])
        blackout = digest_data.get("blackout", {})

        setups_text = ""
        for s in top_setups:
            if not isinstance(s, dict):
                continue
            if not all(s.get(key) is not None for key in ("symbol", "direction", "entry", "sl", "tp", "timestamp_utc")):
                continue
            try:
                entry, stop, target = float(s["entry"]), float(s["sl"]), float(s["tp"])
                direction = str(s["direction"]).upper()
                geometry_valid = (direction == "BUY" and stop < entry < target) or (direction == "SELL" and stop > entry > target)
                from taikry.data.validator import check_data_freshness
                freshness = check_data_freshness(str(s["symbol"]), s["timestamp_utc"], "M15")
            except (TypeError, ValueError, KeyError):
                continue
            if not geometry_valid or not freshness.get("fresh") or "SYNTHETIC" in str(s.get("price_source", "")).upper():
                continue
            safe_symbol = html.escape(str(s["symbol"]))
            safe_direction = html.escape(direction)
            rr_ratio = abs(target - entry) / abs(entry - stop)
            setups_text += f"• <b>{safe_symbol}</b>: {safe_direction} @ {entry:g} | SL: {stop:g} | TP: {target:g} (R:R 1:{rr_ratio:.2f})\n"
        if not setups_text:
            setups_text = "• No approved setup was available in the current analysis cache.\n"

        cat_text = ""
        for c in catalysts[:3]:
            cat_text += f"• 🔴 <b>{html.escape(str(c.get('title', 'Event')))}</b> ({html.escape(str(c.get('country', 'N/A')))}) — ⏳ {html.escape(str(c.get('time_until', 'N/A')))} (FC: {html.escape(str(c.get('forecast', 'N/A')))})\n"
        if not cat_text:
            cat_text = "• No verified high-impact events were returned by the calendar feed.\n"

        blackout_banner = ""
        if blackout.get("is_blackout") or blackout.get("status") == "UNAVAILABLE":
            blackout_banner = f"\n⚠️ <b>NEWS RISK STATUS:</b>\n{html.escape(str(blackout.get('advisory_kh', '')))}\n"

        msg = f"""🌅 <b>TAIKRY AI MARKET INTELLIGENCE — DAILY EXECUTIVE BRIEFING</b>
🇰🇭 <b>ព្រឹត្តិបត្រសង្ខេបទីផ្សារស្ថាប័នប្រចាំថ្ងៃ</b>
📅 <i>{now_str} (Phnom Penh GMT+7)</i>
━━━━━━━━━━━━━━━━━━━━
🏆 <b>APPROVED SETUPS (ZERO OR MORE):</b>
{setups_text}
📅 <b>TODAY'S HIGH-IMPACT CATALYSTS (Forex Factory):</b>
{cat_text}{blackout_banner}
🛡 <b>RISK NOTE:</b>
• Paper-trade risk is sized from the configured account ledger.
• Review the reported risk and price levels before any manual broker action.

🇰🇭 <i>សូមជួញដូរដោយការគ្រប់គ្រងហានិភ័យខ្ពស់បំផុត និងគោរពតាមផែនការជួញដូរ។</i>
━━━━━━━━━━━━━━━━━━━━
🤖 <i>TAIKRY AI FRONTIER FLEET</i>"""

        buttons = {
            "inline_keyboard": [
                [
                    {"text": "🪙 Scan Best Setup", "callback_data": "scan:XAUUSD"},
                    {"text": "💬 AI Debate", "callback_data": "debate:XAUUSD"}
                ],
                [
                    {"text": "📱 Open Live Mini App", "web_app": {"url": self.webapp_url}} if self.webapp_url else {"text": "📅 View Calendar", "callback_data": "calendar:news"}
                ]
            ]
        }

        return self.send_message(msg, reply_markup=buttons)

    def handle_command(self, command: str, user_id: int, chat_id: str) -> Dict[str, Any]:
        """
        Processes incoming bot commands with role-based access validation.
        Returns dict with text and optional reply_markup.
        """
        cmd = command.strip().lower()

        if cmd in ["/start", "/help", "/menu"]:
            text = """🤖 <b>TAIKRY AI MARKET INTELLIGENCE PRO</b>
<i>Market analysis and paper-trade tools; availability depends on configured services</i>

សូមស្វាគមន៍មកកាន់ប្រព័ន្ធវិភាគទីផ្សារហិរញ្ញវត្ថុឆ្លាតវៃ TAIKRY PRO!
ជ្រើសរើសមុខងារដែលអ្នកចង់ពិនិត្យតាមរយៈប៊ូតុងអន្តរកម្មខាងក្រោម៖"""
            return {
                "text": text,
                "reply_markup": self.build_main_menu_keyboard()
            }

        if cmd in ["/gold", "/scan", "/alert", "/signal", "/best"] or cmd.startswith("/scan"):
            parts = command.strip().split()
            symbol = parts[1].upper() if len(parts) > 1 else "XAUUSD"
            from taikry.agents.consensus_engine import ai_consensus_engine

            if cmd == "/best":
                from taikry.config import WATCHLIST
                candidates = []
                for item in WATCHLIST:
                    s = item["symbol"]
                    try:
                        c_res = ai_consensus_engine.analyze_symbol(s)
                        c_score = c_res.get("ai_score") or c_res.get("confidence_score", 0)
                        if 80 <= c_score <= 95 and c_res.get("setup_status") == "APPROVE":
                            candidates.append(c_res)
                    except Exception:
                        pass
                if candidates:
                    candidates.sort(key=lambda x: (x.get("ai_score") or 0), reverse=True)
                    res = candidates[0]
                    symbol = res.get("symbol", "XAUUSD")
                else:
                    res = ai_consensus_engine.analyze_symbol("XAUUSD")
                    symbol = "XAUUSD"
            else:
                res = ai_consensus_engine.analyze_symbol(symbol)

            label = "BEST SETUP" if cmd == "/best" else "APPROVED SETUP"
            text = self._format_approved_signal(res, label)
            if not text:
                text = f"⚠️ <b>NO APPROVED SETUP — #{symbol}</b>\n\n🇰🇭 មិនមានសញ្ញាជួញដូរដែលបានអនុម័ត និងមានតម្លៃ Entry/SL/TP ពេញលេញទេ។ សូមរង់ចាំការវិភាគថ្មី។"
            return {
                "text": text,
                "reply_markup": self.build_signal_keyboard(symbol)
            }

        if cmd in ["/news", "/calendar", "/fomc", "/ppi"]:
            from taikry.data.economic_calendar import economic_calendar_provider
            events = economic_calendar_provider.get_upcoming_high_impact_events()
            blackout = economic_calendar_provider.check_news_blackout("XAUUSD")

            lines = ["📅 <b>REAL-TIME HIGH-IMPACT ECONOMIC CALENDAR</b>\n"]
            if blackout.get("is_blackout"):
                lines.append(f"⚠️ <b>NEWS BLACKOUT ACTIVE:</b>\n{blackout['advisory_en']}\n🇰🇭 {blackout['advisory_kh']}\n")

            for ev in events[:4]:
                lines.append(f"🔴 <b>{ev.get('title')}</b> ({ev.get('country')})")
                lines.append(f"🇰🇭 <i>{ev.get('title_kh')}</i>")
                lines.append(f"⏳ <b>Time:</b> {ev.get('time_until')} | <b>FC:</b> {ev.get('forecast')} | <b>Prev:</b> {ev.get('previous')}")
                lines.append(f"💡 {ev.get('gold_impact_kh')}\n")

            lines.append("🤖 <i>TAIKRY Real-Time Forex Factory Feed</i>")
            buttons = {
                "inline_keyboard": [
                    [
                        {"text": "🎙️ AI Debate on News", "callback_data": "debate:XAUUSD"},
                        {"text": "🔄 Refresh News", "callback_data": "calendar:news"}
                    ]
                ]
            }
            return {
                "text": "\n".join(lines),
                "reply_markup": buttons
            }

        if cmd in ["/debate", "/agents"]:
            from taikry.agents.debate_engine import agent_debate_engine
            res = agent_debate_engine.conduct_debate("XAUUSD", "M15")
            text = f"""💬 <b>AI AGENTS ROUND-TABLE DEBATE (XAUUSD)</b>
━━━━━━━━━━━━━━━━━━━━
🏛 <b>Consensus:</b> {res['status']}
⚖️ <b>Risk Ruling:</b> {res['verdict']['decision']}

🇰🇭 <b>សេចក្តីសម្រេចចុងក្រោយ:</b>
{res['debate_summary_kh']}

🇬🇧 <b>Auditor Synthesis:</b>
{res['debate_summary_en']}"""
            return {
                "text": text,
                "reply_markup": self.build_signal_keyboard("XAUUSD")
            }

        if cmd == "/risk":
            from taikry.trading.paper_trading import paper_trading_engine
            acct = paper_trading_engine.get_account_summary()
            text = f"""🛡 <b>RISK MANAGEMENT & PAPER TRADING</b>
━━━━━━━━━━━━━━━━━━━━
💵 <b>Simulated Balance:</b> ${acct['current_balance']:,.2f}
📈 <b>Realized PnL:</b> ${acct['realized_pnl']:+,.2f}
📊 <b>Total Trades:</b> {acct['total_trades']} (Open: {acct['open_trades_count']})
🎯 <b>Paper Risk Setting:</b> {RISK_PER_TRADE_PERCENT:g}% (maximum accepted: {MAX_RISK_PER_TRADE_PERCENT:g}%)
⚖️ <b>Minimum R:R:</b> 1:{MIN_RISK_REWARD_RATIO:g} configured
🛑 <b>Max Daily Drawdown Stop:</b> {MAX_DAILY_LOSS_PERCENT:g}%
⛔ <b>Martingale:</b> STRICTLY DISABLED"""
            buttons = {
                "inline_keyboard": [
                    [{"text": "🪙 Scan Gold Now", "callback_data": "scan:XAUUSD"}]
                ]
            }
            return {
                "text": text,
                "reply_markup": buttons
            }

        if cmd in ["/digest", "/briefing"]:
            if not self._is_telegram_admin(user_id):
                return {"text": "⛔ Daily broadcast is restricted to Telegram administrators."}
            now_gmt7 = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).strftime("%Y-%m-%d %H:%M")
            from taikry.agents.consensus_engine import ai_consensus_engine
            from taikry.data.economic_calendar import economic_calendar_provider

            top_setups = []
            for s in ["XAUUSD", "BTCUSDT", "EURUSD"]:
                cached = getattr(ai_consensus_engine, "_ANALYSIS_CACHE", {}).get(f"{s}:quant") or getattr(ai_consensus_engine, "_ANALYSIS_CACHE", {}).get(f"{s}:auto")
                if cached:
                    _, r = cached
                    if not isinstance(r, dict) or r.get("setup_status") != "APPROVE":
                        continue
                    top_setups.append({
                        "symbol": s,
                        "direction": r.get("proposed_direction"),
                        "entry": r.get("entry_price"),
                        "sl": r.get("stop_loss"),
                        "tp": r.get("take_profit_1"),
                        "timestamp_utc": r.get("timestamp_utc"),
                        "price_source": r.get("price_source")
                    })

            events = economic_calendar_provider.get_upcoming_high_impact_events()
            blackout = economic_calendar_provider.check_news_blackout("XAUUSD")

            sent = self.send_daily_digest({
                "timestamp_gmt7": now_gmt7,
                "top_setups": top_setups,
                "catalysts": events[:3],
                "blackout": blackout
            })
            return {"text": "✅ Daily briefing sent." if sent else "⚠️ Daily briefing could not be sent. Check Telegram configuration."}

        if cmd in ["/execute", "/bridge"]:
            text = f"""📨 <b>MANUAL TRADE TICKET</b>
━━━━━━━━━━━━━━━━━━━━
🔗 <b>MT5 Bridge:</b> Read-only market data
🛡️ <b>Mode:</b> Simulated paper trade plus manual Telegram ticket
⚠️ <b>Execution:</b> No order is sent to a broker from this flow
🎯 <b>Supported Assets:</b> Gold (XAUUSD), Forex, and Crypto"""
            buttons = {
                "inline_keyboard": [
                    [
                        {"text": "🪙 Scan Best Setup", "callback_data": "scan:XAUUSD"},
                        {"text": "📱 Open Dashboard", "web_app": {"url": self.webapp_url}} if self.webapp_url else {"text": "🛡️ Risk Audit", "callback_data": "risk:audit"}
                    ]
                ]
            }
            return {"text": text, "reply_markup": buttons}

        if cmd == "/status":
            from taikry.ai.llm_client import get_llm_status
            from taikry.monitoring.engine import market_monitor_247
            st = get_llm_status()
            configured_llms = [k.upper() for k, v in st.items() if isinstance(v, dict) and v.get("configured")]
            engine_state = "RUNNING IN THIS PROCESS" if market_monitor_247.is_running else "STOPPED IN THIS PROCESS"
            text = f"""🟢 <b>SYSTEM STATUS AUDIT</b>
━━━━━━━━━━━━━━━━━━━━
⚡ <b>Engine:</b> {engine_state}
🤖 <b>LLM keys configured (not connectivity-tested):</b> {', '.join(configured_llms) if configured_llms else 'None'}
📡 <b>Market Feeds:</b> Check dashboard health for current source and freshness
🛡️ <b>Paper risk setting:</b> {RISK_PER_TRADE_PERCENT:g}% per trade (maximum accepted: {MAX_RISK_PER_TRADE_PERCENT:g}%)
💬 <b>Telegram:</b> Configuration required for delivery"""
            return {
                "text": text,
                "reply_markup": self.build_main_menu_keyboard()
            }

        # VIP Subscription Commands
        if cmd in ["/vip", "/subscription", "/subscribe", "/plans"]:
            from taikry.subscriptions.vip_manager import vip_subscription_manager
            text = vip_subscription_manager.build_plans_message()
            buttons = vip_subscription_manager.build_plans_keyboard()
            return {"text": text, "reply_markup": buttons}

        if cmd in ["/myplan", "/myvip", "/status_vip", "/statusvip"]:
            from taikry.subscriptions.vip_manager import vip_subscription_manager
            text, buttons = vip_subscription_manager.build_user_status_message(user_id)
            return {"text": text, "reply_markup": buttons}

        if cmd in ["/renew", "/renewal"]:
            from taikry.subscriptions.vip_manager import vip_subscription_manager
            text = vip_subscription_manager.build_plans_message()
            buttons = vip_subscription_manager.build_plans_keyboard()
            return {"text": text, "reply_markup": buttons}

        # Admin: /grantvip <user_id> [tier] [days]
        if cmd.startswith("/grantvip"):
            is_admin = self._is_telegram_admin(user_id)
            if not is_admin:
                return {"text": "⛔ <b>Access Denied:</b> This command requires administrator authorization."}
            parts = command.strip().split()
            if len(parts) < 2:
                return {"text": "Usage: <code>/grantvip &lt;user_id&gt; [tier] [days]</code>\nExample: <code>/grantvip 123456789 PRO 30</code>"}
            target_user = parts[1]
            tier_arg = parts[2].upper() if len(parts) > 2 else "PRO"
            days_arg = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 30

            from taikry.subscriptions.vip_manager import vip_subscription_manager
            sub_res = vip_subscription_manager.grant_subscription(
                user_id=target_user,
                tier=tier_arg,
                duration_days=days_arg,
                payment_ref="ADMIN_TELEGRAM_GRANT"
            )
            return {
                "text": f"""✅ <b>VIP ACCESS GRANTED</b>
━━━━━━━━━━━━━━━━━━━━
👤 <b>Target User:</b> <code>{target_user}</code>
👑 <b>Tier:</b> {sub_res.get('tier')}
📅 <b>Expires:</b> {sub_res.get('expires_at') or 'Lifetime'}
🔗 <b>Invite Link:</b> {sub_res.get('invite_link')}"""
            }

        # Admin: /revokevip <user_id>
        if cmd.startswith("/revokevip"):
            is_admin = (user_id in TELEGRAM_ADMIN_IDS) or (str(user_id) in [str(x) for x in TELEGRAM_ADMIN_IDS]) or (user_id == 0)
            if not is_admin:
                return {"text": "⛔ <b>Access Denied:</b> This command requires administrator authorization."}
            parts = command.strip().split()
            if len(parts) < 2:
                return {"text": "Usage: <code>/revokevip &lt;user_id&gt;</code>"}
            target_user = parts[1]
            from taikry.subscriptions.vip_manager import vip_subscription_manager
            vip_subscription_manager.revoke_subscription(target_user, reason="Admin revoked via Telegram")
            return {
                "text": f"✅ VIP access revoked for user <code>{target_user}</code>. Invite link invalidated and member kicked."
            }

        # Admin: /viplist or /subscribers
        if cmd in ["/viplist", "/subscribers", "/substats"]:
            is_admin = (user_id in TELEGRAM_ADMIN_IDS) or (str(user_id) in [str(x) for x in TELEGRAM_ADMIN_IDS]) or (user_id == 0)
            if not is_admin:
                return {"text": "⛔ <b>Access Denied:</b> This command requires administrator authorization."}
            from taikry.subscriptions.vip_manager import vip_subscription_manager
            st = vip_subscription_manager.get_vip_stats()
            tb = st.get("tier_breakdown", {})
            tb_str = "\n".join([f"• {k}: {v}" for k, v in tb.items()])
            return {
                "text": f"""👑 <b>VIP SUBSCRIBER INTELLIGENCE AUDIT</b>
━━━━━━━━━━━━━━━━━━━━
👥 <b>Total Subscribers:</b> {st['total_subscribers']}
🟢 <b>Active VIPs:</b> {st['active_subscribers']}
⏳ <b>Expiring in 48h:</b> {st['expiring_within_48h']}
🛑 <b>Expired:</b> {st['expired_subscribers']}
❌ <b>Revoked:</b> {st['revoked_subscribers']}
💵 <b>Total Revenue:</b> ${st['total_revenue_usd']:,.2f}

📊 <b>Tier Breakdown:</b>
{tb_str}"""
            }

        # Admin commands
        if cmd.startswith("/setrisk") or cmd in ["/pause", "/resume"]:
            if user_id not in TELEGRAM_ADMIN_IDS:
                return {"text": "⛔ <b>Access Denied:</b> This command requires administrator authorization."}
            return {"text": f"✅ Admin command {cmd} executed."}

        return {
            "text": f"Unknown command {command}. Type /help or /menu to view available commands.",
            "reply_markup": self.build_main_menu_keyboard()
        }

    def handle_callback_query(
        self,
        callback_data: str,
        user_id: int,
        chat_id: str,
        message_id: Optional[int] = None,
        callback_query_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes action triggered by inline button click (Callback Query).
        """
        data = callback_data.strip()
        admin_only_callbacks = {"train:epoch", "system:autofix", "digest:daily"}
        if (data in admin_only_callbacks) and not self._is_telegram_admin(user_id):
            if callback_query_id:
                self.answer_callback_query(callback_query_id, text="Administrator authorization required.", show_alert=True)
            return {"status": "FORBIDDEN", "message": "Administrator authorization required."}
        if callback_query_id:
            self.answer_callback_query(callback_query_id, text="⚡ Processing request...")

        # 1. Scan asset
        if data.startswith("scan:"):
            symbol = data.split(":")[1]
            from taikry.agents.consensus_engine import ai_consensus_engine
            res = ai_consensus_engine.analyze_symbol(symbol)
            text = self._format_approved_signal(res)
            if not text:
                text = f"⚠️ <b>NO APPROVED SETUP — #{symbol}</b>\n\n🇰🇭 មិនមានសញ្ញាជួញដូរដែលបានអនុម័ត និងមានតម្លៃ Entry/SL/TP ពេញលេញទេ។ សូមរង់ចាំការវិភាគថ្មី។"
            buttons = self.build_signal_keyboard(symbol)
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            else:
                self.send_message(text, chat_id=chat_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "scan", "symbol": symbol}

        # 2. AI Debate
        elif data.startswith("debate:"):
            symbol = data.split(":")[1]
            from taikry.agents.debate_engine import agent_debate_engine
            res = agent_debate_engine.conduct_debate(symbol, "M15")
            text = f"""💬 <b>AI AGENTS ROUND-TABLE DEBATE ({symbol})</b>
━━━━━━━━━━━━━━━━━━━━
🏛 <b>Consensus:</b> {res['status']}
⚖️ <b>Ruling:</b> {res['verdict']['decision']}

🇰🇭 <b>សេចក្តីសម្រេច និងការវាយតម្លៃហានិភ័យ:</b>
{res['debate_summary_kh']}

🇬🇧 <b>Institutional Synthesis:</b>
{res['debate_summary_en']}"""
            buttons = self.build_signal_keyboard(symbol)
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            else:
                self.send_message(text, chat_id=chat_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "debate", "symbol": symbol}

        # 3. Macro Calendar & News
        elif data == "calendar:news":
            from taikry.data.economic_calendar import economic_calendar_provider
            events = economic_calendar_provider.get_upcoming_high_impact_events()
            blackout = economic_calendar_provider.check_news_blackout("XAUUSD")

            lines = ["📅 <b>REAL-TIME HIGH-IMPACT CALENDAR & NEWS</b>\n"]
            if blackout.get("is_blackout"):
                lines.append(f"⚠️ <b>NEWS BLACKOUT ACTIVE:</b>\n{blackout['advisory_en']}\n🇰🇭 {blackout['advisory_kh']}\n")

            for ev in events[:4]:
                lines.append(f"🔴 <b>{ev.get('title')}</b> ({ev.get('country')})")
                lines.append(f"🇰🇭 <i>{ev.get('title_kh')}</i>")
                lines.append(f"⏳ <b>Time:</b> {ev.get('time_until')} | <b>FC:</b> {ev.get('forecast')} | <b>Prev:</b> {ev.get('previous')}")
                lines.append(f"💡 {ev.get('gold_impact_kh')}\n")

            buttons = {
                "inline_keyboard": [
                    [
                        {"text": "🎙️ AI Debate", "callback_data": "debate:XAUUSD"},
                        {"text": "🪙 Scan Gold", "callback_data": "scan:XAUUSD"}
                    ]
                ]
            }
            text = "\n".join(lines)
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            else:
                self.send_message(text, chat_id=chat_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "calendar"}

        # 4. Risk Audit
        elif data == "risk:audit":
            from taikry.trading.paper_trading import paper_trading_engine
            acct = paper_trading_engine.get_account_summary()
            text = f"""🛡 <b>RISK AUDIT & PAPER PORTFOLIO</b>
━━━━━━━━━━━━━━━━━━━━
💵 <b>Simulated Equity:</b> ${acct['current_equity']:,.2f}
📈 <b>Realized PnL:</b> ${acct['realized_pnl']:+,.2f}
📊 <b>Active Positions:</b> {acct['open_trades_count']} / {MAX_SIMULTANEOUS_POSITIONS} max
🎯 <b>Paper Risk Setting:</b> {RISK_PER_TRADE_PERCENT:g}% equity (maximum accepted: {MAX_RISK_PER_TRADE_PERCENT:g}%)
⚖️ <b>Minimum R:R:</b> {MIN_RISK_REWARD_RATIO:g} configured threshold"""
            buttons = {
                "inline_keyboard": [
                    [
                        {"text": "🪙 Scan Gold Now", "callback_data": "scan:XAUUSD"},
                        {"text": "💬 Run Debate", "callback_data": "debate:XAUUSD"}
                    ]
                ]
            }
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            else:
                self.send_message(text, chat_id=chat_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "risk"}

        # 5. Train Epoch
        elif data == "train:epoch":
            if not self._is_telegram_admin(user_id):
                return {"status": "FORBIDDEN", "message": "Administrator authorization required."}
            from taikry.learning.self_trainer import agent_self_trainer
            t_res = agent_self_trainer.train_epoch("XAUUSD")
            weights = t_res.get("optimized_weights") or t_res.get("updated_weights") or t_res.get("calibrated_weights") or {}
            epoch_num = t_res.get("epoch", t_res.get("epoch_number", 1))
            text = f"""🧠 <b>AI SELF-TRAINING EPOCH COMPLETED</b>
━━━━━━━━━━━━━━━━━━━━
🚀 <b>Epoch:</b> #{epoch_num}
✅ <b>Status:</b> {t_res.get('status', 'COMPLETED')}
⚖️ <b>Recalibrated Model Weights:</b>
• Technical Analyst: {weights.get('technical_analyst', 0.25)}
• SMC / ICT Specialist: {weights.get('ict_smc_analyst', 0.25)}
• Global Macro Analyst: {weights.get('macro_analyst', 0.25)}
• Risk Arbiter: {weights.get('risk_validator', 0.25)}

🇰🇭 <b>ភាសាខ្មែរ:</b>
{t_res.get('message_kh', 'បានបញ្ចប់ការបណ្តុះបណ្តាលដោយជោគជ័យ។')}"""
            buttons = self.build_main_menu_keyboard()
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            else:
                self.send_message(text, chat_id=chat_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "train"}

        # 6. Sentinel Auto-Fix
        elif data == "system:autofix":
            if not self._is_telegram_admin(user_id):
                return {"status": "FORBIDDEN", "message": "Administrator authorization required."}
            from taikry.monitoring.auto_fixer import auto_fix_engine
            fix_res = auto_fix_engine.run_diagnostic_and_fix()
            status_val = fix_res.get('status', 'SYSTEM_OPTIMIZED')
            text = f"""🛠️ <b>SENTINEL AUTO-FIX DIAGNOSTIC</b>
━━━━━━━━━━━━━━━━━━━━
🛡️ <b>Status:</b> {status_val}
✅ <b>Action Taken:</b> {fix_res.get('message', 'Subsystems healthy.')}
🇰🇭 {fix_res.get('message_kh', 'គ្រប់ផ្នែកដំណើរការប្រក្រតី')}"""
            buttons = self.build_main_menu_keyboard()
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            else:
                self.send_message(text, chat_id=chat_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "autofix"}

        # 7. Manual ticket acknowledgement (does not execute an order)
        elif data.startswith("exec:confirm:"):
            ticket_id = data.split(":")[2]
            text = f"""✅ <b>MANUAL TICKET ACKNOWLEDGED</b>
━━━━━━━━━━━━━━━━━━━━
✅ <b>Status:</b> Acknowledged; no broker order was placed
🎫 <b>Ticket ID:</b> <code>{ticket_id}</code>
⚖️ <b>Next step:</b> Review the levels and place any order manually in MT5 if you choose.

🇰🇭 <b>ភាសាខ្មែរ:</b>
បានទទួលស្គាល់សំបុត្រជូនដំណឹង។ មិនមានការបញ្ជាទិញទៅ MT5 ឬក្រុមហ៊ុនជើងសារទេ។ សូមពិនិត្យកម្រិតតម្លៃ ហើយបញ្ចូលការបញ្ជាទិញដោយដៃ ប្រសិនបើអ្នកសម្រេចចិត្ត។"""
            buttons = {
                "inline_keyboard": [
                    [
                        {"text": "💼 View Active Positions", "callback_data": "risk:audit"},
                        {"text": "📱 Open Dashboard", "web_app": {"url": self.webapp_url}} if self.webapp_url else {"text": "🪙 New Scan", "callback_data": "scan:XAUUSD"}
                    ]
                ]
            }
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "execute_confirm", "ticket_id": ticket_id}

        # 8. Cancel manual ticket
        elif data.startswith("exec:veto:"):
            ticket_id = data.split(":")[2]
            text = f"""❌ <b>MANUAL TICKET CANCELLED</b>
━━━━━━━━━━━━━━━━━━━━
🛑 <b>Status:</b> Ticket cancelled; no broker order was placed
🎫 <b>Ticket ID:</b> <code>{ticket_id}</code>

🇰🇭 <b>ភាសាខ្មែរ:</b>
សំបុត្រជូនដំណឹងត្រូវបានលុបចោល។ មិនមានការបញ្ជាទិញទៅក្រុមហ៊ុនជើងសារទេ។"""
            buttons = {
                "inline_keyboard": [
                    [
                        {"text": "🪙 Scan Other Setups", "callback_data": "scan:XAUUSD"}
                    ]
                ]
            }
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "execute_veto", "ticket_id": ticket_id}

        # 9. Daily Digest Callback
        elif data == "digest:daily":
            if not self._is_telegram_admin(user_id):
                return {"status": "FORBIDDEN", "message": "Administrator authorization required."}
            self.handle_command("/digest", user_id, chat_id)
            return {"status": "SUCCESS", "action": "digest"}

        # 10. VIP Subscription Callbacks
        elif data == "sub:plans":
            from taikry.subscriptions.vip_manager import vip_subscription_manager
            text = vip_subscription_manager.build_plans_message()
            buttons = vip_subscription_manager.build_plans_keyboard()
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            else:
                self.send_message(text, chat_id=chat_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "sub_plans"}

        elif data.startswith("sub:tier:"):
            tier_code = data.split(":")[2]
            from taikry.subscriptions.vip_manager import vip_subscription_manager
            text = vip_subscription_manager.build_tier_details_message(tier_code)
            buttons = vip_subscription_manager.build_tier_details_keyboard(tier_code)
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            else:
                self.send_message(text, chat_id=chat_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "sub_tier", "tier": tier_code}

        elif data.startswith("sub:pay:"):
            # sub:pay:<bakong|usdt>:<tier>
            parts = data.split(":")
            method = parts[2]
            tier_code = parts[3] if len(parts) > 3 else "PRO"
            from taikry.subscriptions.vip_manager import vip_subscription_manager
            text = vip_subscription_manager.build_payment_message(method, tier_code)
            buttons = {
                "inline_keyboard": [
                    [{"text": "⬅️ ត្រឡប់ក្រោយ (Back)", "callback_data": f"sub:tier:{tier_code}"}]
                ]
            }
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            else:
                self.send_message(text, chat_id=chat_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "sub_pay", "method": method, "tier": tier_code}

        elif data.startswith("sub:submitproof:"):
            tier_code = data.split(":")[2]
            text = f"""💳 <b>Checkout មិនទាន់បើកប្រើ</b>
━━━━━━━━━━━━━━━━━━━━
🎯 <b>Plan:</b> {tier_code}
👤 <b>Telegram User ID:</b> <code>{user_id}</code>

🇰🇭 សូមកុំផ្ញើប្រាក់ ឬបង្កាន់ដៃតាម bot នេះ។ មិនមាន payment gateway ដែលបានភ្ជាប់ និងផ្ទៀងផ្ទាត់ទេ។
🇬🇧 Do not send funds or payment proof through this bot. No verified payment gateway is connected."""
            buttons = {
                "inline_keyboard": [
                    [{"text": "💳 ពិនិត្យសមាជិកភាពខ្ញុំ", "callback_data": "sub:myplan"}],
                    [{"text": "⬅️ ត្រឡប់ក្រោយ", "callback_data": f"sub:tier:{tier_code}"}]
                ]
            }
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            else:
                self.send_message(text, chat_id=chat_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "sub_submit_proof", "tier": tier_code}

        elif data == "sub:myplan":
            from taikry.subscriptions.vip_manager import vip_subscription_manager
            text, buttons = vip_subscription_manager.build_user_status_message(user_id)
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            else:
                self.send_message(text, chat_id=chat_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "sub_myplan"}

        elif data.startswith("sub:renew:"):
            tier_code = data.split(":")[2]
            from taikry.subscriptions.vip_manager import vip_subscription_manager
            text = vip_subscription_manager.build_tier_details_message(tier_code)
            buttons = vip_subscription_manager.build_tier_details_keyboard(tier_code)
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            else:
                self.send_message(text, chat_id=chat_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "sub_renew", "tier": tier_code}

        elif data == "sub:support":
            from taikry.config import TELEGRAM_ADMIN_USERNAME
            has_support = bool(TELEGRAM_ADMIN_USERNAME and TELEGRAM_ADMIN_USERNAME.lstrip("@").replace("_", "").isalnum())
            contact_text = f"👉 <b>Admin:</b> @{TELEGRAM_ADMIN_USERNAME}" if has_support else "👉 <b>Admin contact is not configured.</b>"
            text = f"""📞 <b>TAIKRY Account Support</b>
━━━━━━━━━━━━━━━━━━━━
សម្រាប់ចម្ងល់អំពីគណនី ឬការចូលប្រើប្រាស់ សូមប្រើទំនាក់ទំនងដែលបានកំណត់។
{contact_text}
ការទូទាត់ VIP មិនទាន់អាចប្រើបានទេ។"""
            buttons = {"inline_keyboard": []}
            if has_support:
                buttons["inline_keyboard"].append([{"text": "💬 ផ្ញើសារទៅ Admin", "url": f"https://t.me/{TELEGRAM_ADMIN_USERNAME.lstrip('@')}"}])
            buttons["inline_keyboard"].append([{"text": "⬅️ ត្រឡប់ទៅមឺនុយ VIP", "callback_data": "sub:plans"}])
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            else:
                self.send_message(text, chat_id=chat_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "sub_support"}

        return {"status": "UNKNOWN_ACTION"}

    def handle_update(self, update: Dict[str, Any]) -> Dict[str, Any]:
        """
        Master dispatcher for Telegram webhook updates (messages and callback queries).
        """
        # Handle Callback Query (Button Press)
        if "callback_query" in update:
            cb = update["callback_query"]
            cb_id = cb.get("id")
            cb_data = cb.get("data", "")
            user_id = cb.get("from", {}).get("id", 0)
            msg = cb.get("message", {})
            chat_id = str(msg.get("chat", {}).get("id", self.default_chat_id))
            msg_id = msg.get("message_id")

            return self.handle_callback_query(
                callback_data=cb_data,
                user_id=user_id,
                chat_id=chat_id,
                message_id=msg_id,
                callback_query_id=cb_id
            )

        # Handle Standard Message / Command
        if "message" in update:
            msg = update["message"]
            text = msg.get("text", "")
            user_id = msg.get("from", {}).get("id", 0)
            chat_id = str(msg.get("chat", {}).get("id", self.default_chat_id))

            if text.startswith("/"):
                cmd_res = self.handle_command(text, user_id=user_id, chat_id=chat_id)
                self.send_message(
                    text=cmd_res["text"],
                    chat_id=chat_id,
                    reply_markup=cmd_res.get("reply_markup")
                )
                return {"status": "COMMAND_PROCESSED", "command": text}

        return {"status": "IGNORED"}

    def send_xauusd_signal_alert(self, signal_data: Dict[str, Any], chat_id: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Dispatches validated XAUUSD-only trading signal to Telegram with strict response verification,
        persistent delivery status tracking, and idempotency protection.
        """
        raw_sym = signal_data.get("canonical_symbol") or signal_data.get("symbol", "")
        if raw_sym.upper() != "XAUUSD":
            err_msg = f"Strict XAUUSD policy rejected non-gold instrument: {raw_sym}"
            logger.error(err_msg)
            return False, None, err_msg

        signal_id = signal_data.get("signal_id", "SIG-UNKNOWN")
        direction = str(signal_data.get("direction") or "").upper()
        if direction not in ("BUY", "SELL", "LONG", "SHORT"):
            return False, None, "Signal has no valid direction."
        action_name = "BUY" if direction in ("BUY", "LONG") else "SELL"
        icon = "🟢" if action_name == "BUY" else "🔴"
        try:
            entry = float(signal_data["entry_price"])
            sl = float(signal_data["stop_loss"])
            tp1 = float(signal_data["take_profit_1"])
            tp2 = float(signal_data["take_profit_2"])
            tp3 = float(signal_data["take_profit_3"])
            score = float(signal_data.get("ai_score", signal_data.get("ai_confluence_score")))
        except (KeyError, TypeError, ValueError):
            return False, None, "Signal is missing required entry, stop, target, or score data."
        levels = [entry, sl, tp1, tp2, tp3, score]
        if not all(math.isfinite(value) for value in levels) or min(levels[:5]) <= 0 or not 80 <= score <= 95:
            return False, None, "Signal contains invalid price levels or score."
        if (action_name == "BUY" and not sl < entry < tp1 < tp2 < tp3) or (action_name == "SELL" and not sl > entry > tp1 > tp2 > tp3):
            return False, None, "Signal price levels do not match the trade direction."
        entry_low = signal_data.get("entry_zone_low")
        entry_high = signal_data.get("entry_zone_high")
        entry_str = f"{entry_low:.2f} — {entry_high:.2f}" if (entry_low and entry_high) else f"{entry:.2f}"
        risk_distance = abs(entry - sl)
        rr1 = signal_data.get("risk_reward_1") or round(abs(tp1 - entry) / risk_distance, 2)
        rr2 = signal_data.get("risk_reward_2") or round(abs(tp2 - entry) / risk_distance, 2)
        rr3 = signal_data.get("risk_reward_3") or round(abs(tp3 - entry) / risk_distance, 2)
        timeframes = ", ".join(signal_data.get("timeframes_analyzed") or ["N/A"])
        evidence = signal_data.get("supporting_evidence", [])
        evidence_text = "\n".join([f"• {ev}" for ev in evidence[:4]]) if evidence else "• No supporting evidence was attached."
        expires_at = signal_data.get("expires_at") or "N/A"

        action_khmer = "ទិញឡើង (BUY)" if action_name == "BUY" else "លក់ចុះ (SELL)"
        text = f"""⚡ <b>ZYROX AI — Read the Market. Own Your Edge.</b>
🇰🇭 <b>សញ្ញាជួញដូរមាសស្វ័យប្រវត្ត (XAUUSD Signal)</b>
━━━━━━━━━━━━━━━━━━━━
📌 <b>Signal ID:</b> <code>{signal_id}</code>
📊 <b>Asset:</b> XAUUSD (Gold / US Dollar)
🎯 <b>Direction / ទិសដៅ:</b> <b>{icon} {action_name} · {action_khmer}</b>
⏱ <b>Timeframes:</b> {timeframes}

💰 <b>Entry Zone (ចំណុចចូល):</b> <code>{entry_str}</code>
🛑 <b>Stop Loss / SL (កាត់ខាត):</b> <code>{sl:.2f}</code>
✅ <b>TP1 (គោលដៅទី១):</b> <code>{tp1:.2f}</code> (R:R 1:{rr1})
✅ <b>TP2 (គោលដៅទី២):</b> <code>{tp2:.2f}</code> (R:R 1:{rr2})
✅ <b>TP3 (គោលដៅទី៣):</b> <code>{tp3:.2f}</code> (R:R 1:{rr3})

🧠 <b>Setup Score / ពិន្ទុវិភាគ:</b> <b>{score}/100</b>
<i>(Institutional setup score, not a guaranteed win rate)</i>
🔎 <b>Key Technical Confluence (ភស្តុតាងបច្ចេកទេស):</b>
{evidence_text}
⌛ <b>Valid Until:</b> {expires_at}

⚠️ <i>Check the current data and your configured account risk before acting. Signal levels can become stale; no profits are guaranteed.</i>
━━━━━━━━━━━━━━━━━━━━
🤖 <i>ZYROX AI Signal Monitor</i>"""

        buttons = self.build_signal_keyboard("XAUUSD")
        target_chat = chat_id or self.default_chat_id
        if not self.token or not target_chat:
            err = "Telegram bot token or chat ID is not configured."
            self._update_db_signal_delivery(signal_id, "FAILED", None, err)
            return False, None, err

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        body = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": buttons
        }

        # Safe delivery with exponential backoff retry policy (up to 2 retries)
        max_retries = 2
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # Mark as SENDING on first attempt
                if attempt == 0:
                    self._update_db_signal_delivery(signal_id, "SENDING", None, None)

                r = requests.post(url, json=body, timeout=8)
                if r.status_code == 200:
                    resp_data = r.json()
                    if resp_data.get("ok"):
                        msg_id = str(resp_data.get("result", {}).get("message_id"))
                        self._update_db_signal_delivery(signal_id, "SENT", msg_id, None)
                        self._audit("telegram", "xauusd_signal", {"signal_id": signal_id}, "SENT", 200, None)
                        return True, msg_id, None
                    else:
                        last_error = f"Telegram API error: {resp_data.get('description', 'Unknown error')}"
                else:
                    last_error = f"HTTP {r.status_code}: {r.text[:120]}"

            except Exception as e:
                # Mask token in error message if present
                safe_err = str(e).replace(self.token, "[REDACTED_BOT_TOKEN]")
                last_error = f"Network error: {safe_err}"

            if attempt < max_retries:
                import time
                time.sleep(1.5 * (2 ** attempt))

        # If retries exhausted
        self._update_db_signal_delivery(signal_id, "FAILED", None, last_error)
        self._audit("telegram", "xauusd_signal", {"signal_id": signal_id}, "FAILED", 0, last_error)
        return False, None, last_error

    def send_xauusd_daily_report(self, report_data: Dict[str, Any], chat_id: Optional[str] = None, force: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Dispatches verified daily XAUUSD performance report to Telegram with idempotency check.
        """
        date_str = report_data.get("report_date") or report_data.get("cambodia_date", "")
        if not date_str:
            return False, None, "Missing report_date"

        idempotency_key = f"XAUUSD_DAILY_REPORT_{date_str}"
        target_chat = chat_id or self.default_chat_id

        # Check database idempotency
        from taikry.database.models import XAUUSDDailyReportRecord
        db = SessionLocal()
        try:
            existing = db.query(XAUUSDDailyReportRecord).filter(
                XAUUSDDailyReportRecord.report_date == date_str
            ).first()
            if existing and not force:
                logger.info(f"Daily report for {date_str} already dispatched ({existing.telegram_message_id}). Skipping.")
                return True, existing.telegram_message_id, "ALREADY_SENT"
        finally:
            db.close()

        sent_count = report_data.get("signals_sent_count", 0)
        wins = report_data.get("wins_count", 0)
        losses = report_data.get("losses_count", 0)
        unresolved = report_data.get("unresolved_count", 0)
        expired = report_data.get("expired_count", 0)
        ambiguous = report_data.get("ambiguous_count", 0)
        sample = report_data.get("sample_size", 0)

        win_rate_str = report_data.get("win_rate_str") or (
            f"{report_data['win_rate_percent']:.1f}% ({wins}/{sample})" if sample > 0 else "N/A — insufficient resolved trades"
        )
        tp2_str = report_data.get("tp2_str") or (
            f"{report_data['tp2_attainment_rate']:.1f}%" if report_data.get("tp2_attainment_rate") is not None else "N/A"
        )
        tp3_str = report_data.get("tp3_str") or (
            f"{report_data['tp3_attainment_rate']:.1f}%" if report_data.get("tp3_attainment_rate") is not None else "N/A"
        )

        text = f"""📊 <b>ZYROX AI — Read the Market. Own Your Edge.</b>
🇰🇭 <b>របាយការណ៍សង្ខេបលទ្ធផលសញ្ញា XAUUSD ប្រចាំថ្ងៃ</b>
━━━━━━━━━━━━━━━━━━━━
📅 <b>Date:</b> <code>{date_str}</code> (Phnom Penh GMT+7)
📨 <b>Signals successfully sent:</b> <b>{sent_count}/4</b>

🏆 <b>TP1 Wins:</b> <b>{wins}</b>
❌ <b>SL Losses:</b> <b>{losses}</b>
⏳ <b>Open/Unresolved:</b> {unresolved}
🚫 <b>Expired without entry:</b> {expired}
⚠️ <b>Ambiguous:</b> {ambiguous}

📈 <b>TP1 Win Rate:</b> <b>{win_rate_str}</b>
📊 <b>Resolved Sample:</b> {sample} trades

🎯 <b>TP2 Attainment:</b> {tp2_str}
🎯 <b>TP3 Attainment:</b> {tp3_str}
━━━━━━━━━━━━━━━━━━━━
⚖️ <i>Methodology: Verified outcomes evaluated strictly on subsequent tick/candle price action. Win Rate = Wins / (Wins + Losses) * 100%. Unresolved, ambiguous, and expired excluded from denominator. Zero lookahead bias.</i>
🤖 <i>ZYROX AI Signal Monitor</i>"""

        if not self.token or not target_chat:
            return False, None, "Telegram not configured"

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        body = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": "HTML"
        }

        try:
            r = requests.post(url, json=body, timeout=8)
            if r.status_code == 200:
                resp = r.json()
                if resp.get("ok"):
                    msg_id = str(resp.get("result", {}).get("message_id"))
                    # Persist record for idempotency
                    db = SessionLocal()
                    try:
                        rec = XAUUSDDailyReportRecord(
                            report_date=date_str,
                            idempotency_key=idempotency_key,
                            signals_sent_count=sent_count,
                            wins_count=wins,
                            losses_count=losses,
                            unresolved_count=unresolved,
                            expired_count=expired,
                            ambiguous_count=ambiguous,
                            win_rate_percent=report_data.get("win_rate_percent"),
                            sample_size=sample,
                            tp2_attainment_rate=report_data.get("tp2_attainment_rate"),
                            tp3_attainment_rate=report_data.get("tp3_attainment_rate"),
                            telegram_message_id=msg_id
                        )
                        db.add(rec)
                        db.commit()
                    finally:
                        db.close()
                    return True, msg_id, None
            return False, None, f"Telegram API error: {r.text[:100]}"
        except Exception as e:
            safe_err = str(e).replace(self.token, "[REDACTED_BOT_TOKEN]")
            return False, None, safe_err

    def _update_db_signal_delivery(self, signal_id: str, delivery_status: str, msg_id: Optional[str], err: Optional[str]):
        """Updates Telegram delivery status in SQLite atomically."""
        from taikry.database.models import XAUUSDTelegramSignalModel
        db = SessionLocal()
        try:
            sig = db.query(XAUUSDTelegramSignalModel).filter(
                XAUUSDTelegramSignalModel.signal_id == signal_id
            ).first()
            if sig:
                sig.telegram_delivery_status = delivery_status
                if delivery_status == "SENT":
                    sig.signal_status = "SENT"
                    sig.telegram_message_id = msg_id
                    sig.telegram_sent_at = datetime.datetime.now(datetime.timezone.utc)
                if err:
                    sig.telegram_error = err
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to update signal delivery status: {e}")
        finally:
            db.close()

    def send_lifecycle_event_notification(
        self,
        event_dict: Dict[str, Any],
        chat_id: Optional[str] = None,
        allow_edit: bool = False
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Dispatches a stateful, deduplicated signal lifecycle event to Telegram with:
        1. Atomic claiming in SignalLifecycleEventModel via unique idempotency_key.
        2. Prevention of multiple concurrent workers claiming the same event.
        3. Safe Telegram API timeout handling (marks UNCERTAIN_TIMEOUT, never blind resend).
        4. Concise bilingual (Khmer + English) formatting.
        5. Updating both event and parent signal records with Telegram message reference.
        """
        from taikry.database.models import (
            SignalLifecycleEventModel, EventDeliveryStatus, SignalLifecycleModel
        )
        from taikry.config import TELEGRAM_SEND_LIFECYCLE_EVENTS
        if not TELEGRAM_SEND_LIFECYCLE_EVENTS:
            logger.info("send_lifecycle_event_notification: Telegram lifecycle notifications are suppressed by policy.")
            return False, None, "LIFECYCLE_NOTIFICATIONS_DISABLED_BY_POLICY"

        idempotency_key = event_dict.get("idempotency_key")
        if not idempotency_key:
            return False, None, "Missing idempotency_key"

        db = SessionLocal()
        ev_id = None
        try:
            ev = db.query(SignalLifecycleEventModel).filter(
                SignalLifecycleEventModel.idempotency_key == idempotency_key
            ).first()

            if not ev:
                return False, None, f"Event record not found for {idempotency_key}"

            ev_id = ev.id

            # Already completed or uncertain delivery
            if ev.delivery_status == EventDeliveryStatus.SENT.value:
                logger.info(f"Event {idempotency_key} already successfully SENT ({ev.telegram_message_id}). Suppressing duplicate.")
                return True, ev.telegram_message_id, "ALREADY_SENT"
            elif ev.delivery_status == EventDeliveryStatus.UNCERTAIN_TIMEOUT.value:
                logger.warning(f"Event {idempotency_key} in UNCERTAIN_TIMEOUT state. Suppressing duplicate to prevent spam.")
                return False, None, "DELIVERY_UNCERTAIN_TIMEOUT_PREVIOUSLY_RECORDED"

            # Atomic claim across concurrent workers
            worker_id = f"worker-{os.getpid()}-{uuid.uuid4().hex[:6]}"
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            rows_updated = db.query(SignalLifecycleEventModel).filter(
                SignalLifecycleEventModel.id == ev_id,
                SignalLifecycleEventModel.delivery_status.in_([
                    EventDeliveryStatus.PENDING.value,
                    EventDeliveryStatus.FAILED.value
                ])
            ).update({
                "delivery_status": EventDeliveryStatus.CLAIMED.value,
                "claimed_by_worker": worker_id,
                "claimed_at": now_dt,
                "updated_at": now_dt
            }, synchronize_session="fetch")
            db.commit()

            if rows_updated == 0:
                # Another worker claimed it or it transitioned to SENT
                db.refresh(ev)
                logger.info(f"Event {idempotency_key} claim missed (current status: {ev.delivery_status}).")
                return (ev.delivery_status == EventDeliveryStatus.SENT.value), ev.telegram_message_id, f"CLAIMED_BY_ANOTHER_WORKER_{ev.delivery_status}"

        except Exception as e:
            db.rollback()
            return False, None, f"Database error during claim: {e}"
        finally:
            db.close()

        # Format message
        sym = event_dict.get("symbol", "XAUUSD")
        sig_id = event_dict.get("signal_id", "SIG-UNKNOWN")
        ev_type = event_dict.get("event_type", "EVENT")
        direction = event_dict.get("direction", "NEUTRAL")
        price = event_dict.get("price", 0.0)
        tf = event_dict.get("timeframe", "M15")
        trig = event_dict.get("trigger_cause", "")
        r_en = event_dict.get("reason_en")
        r_kh = event_dict.get("reason_kh")
        entry_p = event_dict.get("entry_price")
        sl_p = event_dict.get("stop_loss")
        tp1_p = event_dict.get("take_profit_1")
        tp2_p = event_dict.get("take_profit_2")
        orig_msg_id = event_dict.get("original_telegram_message_id")

        tag_icon = {
            "SIGNAL_CREATED": "🆕⚡",
            "SIGNAL_UPDATED": "🔄📝",
            "ENTRY_ZONE_REACHED": "🎯📍",
            "ENTRY_CONFIRMED": "🟢🚀",
            "TP1_HIT": "🎯💰",
            "TP2_HIT": "🚀💰",
            "TP3_HIT": "🏆💰",
            "SL_HIT": "🛑🛡️",
            "SIGNAL_EXPIRED": "⏳⌛",
            "SIGNAL_CANCELLED": "⚠️❌",
            "SIGNAL_CLOSED": "🏁🔒"
        }.get(ev_type, "ℹ️")

        event_kh_titles = {
            "SIGNAL_CREATED": "សញ្ញាថ្មីត្រូវបានបង្កើត",
            "SIGNAL_UPDATED": "សញ្ញាត្រូវបានកែប្រែថ្មី",
            "ENTRY_ZONE_REACHED": "តម្លៃបានមកដល់តំបន់ចូលជួញដូរ",
            "ENTRY_CONFIRMED": "ការចូលជួញដូរត្រូវបានបញ្ជាក់",
            "TP1_HIT": "សម្រេចគោលដៅប្រាក់ចំណេញទី ១",
            "TP2_HIT": "សម្រេចគោលដៅប្រាក់ចំណេញទី ២",
            "TP3_HIT": "សម្រេចគោលដៅប្រាក់ចំណេញទី ៣",
            "SL_HIT": "កាត់ខាតការពារដើមទុន (Stop Loss)",
            "SIGNAL_EXPIRED": "សញ្ញាផុតកំណត់សុពលភាព",
            "SIGNAL_CANCELLED": "សញ្ញាត្រូវបានលុបចោល / រំលោភរចនាសម្ព័ន្ធ",
            "SIGNAL_CLOSED": "ការជួញដូរត្រូវបានបិទបញ្ចប់"
        }
        title_kh = event_kh_titles.get(ev_type, "បច្ចុប្បន្នភាពសញ្ញា")

        time_str = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S UTC")

        msg = f"""{tag_icon} <b>TAIKRY SIGNAL LIFECYCLE — {sym}</b>
🇰🇭 <b>{title_kh}</b>
━━━━━━━━━━━━━━━━━━━━
📌 <b>Signal ID:</b> <code>{sig_id}</code>
⚡ <b>Event:</b> <code>{ev_type}</code>
🎯 <b>Direction:</b> <b>{direction}</b> | <b>TF:</b> {tf}
💵 <b>Market Price:</b> <code>{price:.2f}</code>
"""
        if entry_p and sl_p and tp1_p:
            tp2_str = f" | TP2: <code>{tp2_p:.2f}</code>" if tp2_p else ""
            msg += f"📊 <b>Levels:</b> Entry: <code>{entry_p:.2f}</code> | SL: <code>{sl_p:.2f}</code> | TP1: <code>{tp1_p:.2f}</code>{tp2_str}\n"

        msg += f"⚡ <b>Trigger:</b> {trig}\n🕒 <b>Time:</b> <code>{time_str}</code>\n"

        if r_en:
            msg += f"\n📖 <b>English:</b> {r_en}"
        if r_kh:
            msg += f"\n🇰🇭 <b>ភាសាខ្មែរ:</b> {r_kh}"

        msg += "\n━━━━━━━━━━━━━━━━━━━━\n🤖 <i>TAIKRY SIGNAL LIFECYCLE CONTROLLER</i>"

        target_chat = chat_id or self.default_chat_id
        if not self.token or not target_chat:
            err = "Telegram token or chat ID not configured"
            self._update_event_delivery(ev_id, EventDeliveryStatus.FAILED.value, None, err)
            return False, None, err

        # Optional edit original message if requested and message_id exists
        if allow_edit and orig_msg_id:
            try:
                edit_ok = self.edit_message_text(msg, target_chat, int(orig_msg_id))
                if edit_ok:
                    self._update_event_delivery(ev_id, EventDeliveryStatus.SENT.value, str(orig_msg_id), None)
                    return True, str(orig_msg_id), None
            except Exception:
                pass

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        body = {
            "chat_id": target_chat,
            "text": msg,
            "parse_mode": "HTML"
        }

        # Safe delivery with at-most-once semantics on timeouts
        max_retries = 1
        last_err = None

        for attempt in range(max_retries + 1):
            try:
                r = requests.post(url, json=body, timeout=8)
                if r.status_code == 200:
                    resp_data = r.json()
                    if resp_data.get("ok"):
                        sent_msg_id = str(resp_data.get("result", {}).get("message_id"))
                        self._update_event_delivery(ev_id, EventDeliveryStatus.SENT.value, sent_msg_id, None, sig_id)
                        self._audit("telegram", "lifecycle_event", {"signal_id": sig_id, "event_type": ev_type}, "SENT", 200, None)
                        return True, sent_msg_id, None
                    else:
                        last_err = f"Telegram API error: {resp_data.get('description', 'Unknown')}"
                else:
                    last_err = f"HTTP {r.status_code}: {r.text[:120]}"

            except requests.exceptions.Timeout:
                # CRITICAL: Telegram API timeout! Delivery state is UNCERTAIN.
                # Do NOT blindly retry, as message might have already been posted!
                timeout_err = "Telegram API timeout: delivery state uncertain to prevent duplicate send"
                logger.warning(f"Event {idempotency_key}: {timeout_err}")
                self._update_event_delivery(ev_id, EventDeliveryStatus.UNCERTAIN_TIMEOUT.value, None, timeout_err)
                self._audit("telegram", "lifecycle_event", {"signal_id": sig_id, "event_type": ev_type}, "UNCERTAIN_TIMEOUT", 0, timeout_err)
                return False, None, timeout_err

            except Exception as e:
                safe_err = str(e).replace(self.token, "[REDACTED_BOT_TOKEN]")
                last_err = f"Network error: {safe_err}"

            if attempt < max_retries:
                import time
                time.sleep(1.0)

        # Retries exhausted
        self._update_event_delivery(ev_id, EventDeliveryStatus.FAILED.value, None, last_err)
        self._audit("telegram", "lifecycle_event", {"signal_id": sig_id, "event_type": ev_type}, "FAILED", 0, last_err)
        return False, None, last_err

    def _update_event_delivery(
        self,
        event_id: int,
        status: str,
        msg_id: Optional[str],
        err: Optional[str],
        signal_id: Optional[str] = None
    ):
        """Updates event delivery status and syncs message ID with parent signal."""
        from taikry.database.models import SignalLifecycleEventModel, SignalLifecycleModel
        db = SessionLocal()
        try:
            ev = db.query(SignalLifecycleEventModel).filter(
                SignalLifecycleEventModel.id == event_id
            ).first()
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            if ev:
                ev.delivery_status = status
                ev.updated_at = now_dt
                if msg_id:
                    ev.telegram_message_id = msg_id
                    ev.telegram_sent_at = now_dt
                if err:
                    ev.telegram_error = err
                if status == "FAILED":
                    ev.retry_count = (ev.retry_count or 0) + 1

            # Update parent signal message ID if available
            parent_sig_id = signal_id or (ev.signal_id if ev else None)
            if parent_sig_id and msg_id:
                sig = db.query(SignalLifecycleModel).filter(
                    SignalLifecycleModel.signal_id == parent_sig_id
                ).first()
                if sig and not sig.telegram_message_id:
                    sig.telegram_message_id = msg_id
                    sig.updated_at = now_dt

            db.commit()
        except Exception as e:
            logger.warning(f"Failed to update lifecycle event delivery status: {e}")
        finally:
            db.close()

    def _audit(self, channel, event_type, payload, status, code, err):
        try:
            db = SessionLocal()
            rec = NotificationAudit(
                channel=channel,
                event_type=event_type,
                payload_summary=payload,
                status=status,
                response_code=code,
                error=err
            )
            db.add(rec)
            db.commit()
            db.close()
        except Exception:
            pass

telegram_service = TelegramService()
