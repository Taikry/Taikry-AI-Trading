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
import hashlib
import json
import gzip
import mimetypes
import re
import shutil
import struct
import subprocess
from urllib.parse import quote
from typing import Dict, Any, Optional, List, Tuple
import requests
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

from taikry.config import (
    TELEGRAM_ENABLED,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_ADMIN_IDS,
    TELEGRAM_WEBAPP_URL,
    MAX_RISK_PER_TRADE_PERCENT,
    RISK_PER_TRADE_PERCENT,
    MIN_RISK_REWARD_RATIO,
    MAX_DAILY_LOSS_PERCENT,
    MAX_SIMULTANEOUS_POSITIONS,
    PUBLIC_APP_URL,
)
from taikry.database.session import SessionLocal
from taikry.database.models import (
    NotificationAudit, TelegramNotification, TelegramAnalysisRun, TelegramMediaAsset,
)

logger = logging.getLogger("taikry.notifications.telegram_service")

class TelegramService:
    """Telegram Bot API Interface with Interactive Keyboards & Mini App support."""

    def __init__(self):
        self.enabled = TELEGRAM_ENABLED
        self.token = TELEGRAM_BOT_TOKEN
        self.default_chat_id = TELEGRAM_CHAT_ID
        self.webapp_url = TELEGRAM_WEBAPP_URL

    def is_configured(self) -> bool:
        return bool(self.enabled and self.token and self.default_chat_id)

    def _claim_persistent_notification(
        self,
        idempotency_key: str,
        notification_type: str,
        chat_id: str,
        signal_id: Optional[str],
        event_state: Optional[str],
        payload_summary: Optional[Dict[str, Any]],
    ) -> Tuple[Optional[int], str, Optional[str], Optional[str]]:
        """Create and atomically claim a persistent Telegram delivery record."""
        db = SessionLocal()
        now = datetime.datetime.utcnow()
        try:
            record = db.query(TelegramNotification).filter(
                TelegramNotification.idempotency_key == idempotency_key
            ).first()
            if record is None:
                record = TelegramNotification(
                    signal_id=signal_id,
                    notification_type=notification_type,
                    event_state=event_state,
                    idempotency_key=idempotency_key,
                    telegram_chat_id=str(chat_id),
                    delivery_status="PENDING",
                    attempt_count=0,
                    payload_summary=payload_summary or {},
                    created_at=now,
                    updated_at=now,
                )
                db.add(record)
                try:
                    db.commit()
                except IntegrityError:
                    db.rollback()
                record = db.query(TelegramNotification).filter(
                    TelegramNotification.idempotency_key == idempotency_key
                ).first()
            if record is None:
                return None, "FAILED", None, "Unable to create delivery record"

            if record.delivery_status == "SENT":
                return record.id, "SENT", record.telegram_message_id, None
            if record.delivery_status == "UNCERTAIN":
                return record.id, "UNCERTAIN", None, "Previous Telegram delivery outcome is uncertain"
            if record.delivery_status == "SENDING":
                claimed_at = record.claimed_at
                if claimed_at and claimed_at < now - datetime.timedelta(minutes=10):
                    record.delivery_status = "UNCERTAIN"
                    record.telegram_error = "Delivery worker stopped after claim; automatic resend suppressed"
                    record.updated_at = now
                    db.commit()
                    return record.id, "UNCERTAIN", None, record.telegram_error
                return record.id, "SENDING", None, "Notification is already being delivered"
            if record.next_attempt_at and record.next_attempt_at > now:
                return record.id, record.delivery_status, None, "Retry is not due yet"

            changed = db.query(TelegramNotification).filter(
                TelegramNotification.id == record.id,
                TelegramNotification.delivery_status.in_(["PENDING", "FAILED", "RETRY_PENDING"]),
                or_(TelegramNotification.next_attempt_at.is_(None), TelegramNotification.next_attempt_at <= now),
            ).update({
                "delivery_status": "SENDING",
                "attempt_count": TelegramNotification.attempt_count + 1,
                "claimed_at": now,
                "updated_at": now,
                "telegram_error": None,
            }, synchronize_session=False)
            db.commit()
            if not changed:
                db.refresh(record)
                if record.delivery_status == "SENT":
                    return record.id, "SENT", record.telegram_message_id, None
                return record.id, record.delivery_status, record.telegram_message_id, "Notification could not be claimed"
            return record.id, "SENDING", None, None
        except Exception as exc:
            db.rollback()
            logger.warning("Telegram notification claim failed: %s", self._redact_secret(str(exc)))
            return None, "FAILED", None, "Database error while claiming Telegram notification"
        finally:
            db.close()

    def _set_persistent_notification_status(
        self,
        notification_id: Optional[int],
        status: str,
        message_id: Optional[str] = None,
        error: Optional[str] = None,
        retry_after_seconds: Optional[int] = None,
    ) -> None:
        if notification_id is None:
            return
        db = SessionLocal()
        now = datetime.datetime.utcnow()
        try:
            record = db.query(TelegramNotification).filter(TelegramNotification.id == notification_id).first()
            if record:
                record.delivery_status = status
                record.telegram_message_id = message_id or record.telegram_message_id
                record.telegram_error = self._redact_secret(error) if error else None
                record.updated_at = now
                record.delivered_at = now if status == "SENT" else record.delivered_at
                if retry_after_seconds is not None:
                    record.next_attempt_at = now + datetime.timedelta(seconds=max(1, retry_after_seconds))
                elif status in {"SENT", "UNCERTAIN"}:
                    record.next_attempt_at = None
                db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("Telegram notification status update failed: %s", self._redact_secret(str(exc)))
        finally:
            db.close()

    def _redact_secret(self, value: str) -> str:
        """Remove configured credentials and common URL/query secret forms from diagnostics."""
        safe = str(value)
        if self.token:
            safe = safe.replace(self.token, "[REDACTED_TELEGRAM_TOKEN]")
        for env_name in (
            "DATABASE_URL", "OANDA_API_TOKEN", "MT5_BRIDGE_TOKEN", "TELEGRAM_WEBHOOK_SECRET",
            "ABA_PAYWAY_API_KEY", "ABA_PAYWAY_RSA_PRIVATE_KEY", "SECRET_KEY",
        ):
            secret = os.getenv(env_name)
            if secret:
                safe = safe.replace(secret, f"[REDACTED_{env_name}]")
        safe = re.sub(r"(?i)(postgres(?:ql)?://)[^/@\s]+@", r"\1[REDACTED]@", safe)
        safe = re.sub(r"(?i)(password|passwd|secret|token|api[_-]?key)=([^&\s]+)", r"\1=[REDACTED]", safe)
        return safe

    @staticmethod
    def _telegram_media_root() -> str:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web", "static", "telegram"))

    @staticmethod
    def _read_media_dimensions(path: str, extension: str) -> Optional[Tuple[int, int]]:
        """Read dimensions for common Telegram media formats without trusting filenames."""
        with open(path, "rb") as media_file:
            header = media_file.read(32)
        if extension == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) >= 24:
            return struct.unpack(">II", header[16:24])
        if extension == ".gif" and header[:6] in {b"GIF87a", b"GIF89a"} and len(header) >= 10:
            return struct.unpack("<HH", header[6:10])
        if extension in {".jpg", ".jpeg"} and header.startswith(b"\xff\xd8"):
            with open(path, "rb") as media_file:
                media_file.read(2)
                while True:
                    marker_prefix = media_file.read(1)
                    if not marker_prefix:
                        break
                    if marker_prefix != b"\xff":
                        continue
                    marker = media_file.read(1)
                    while marker == b"\xff":
                        marker = media_file.read(1)
                    if marker in {b"\xd8", b"\xd9"} or not marker:
                        continue
                    size_bytes = media_file.read(2)
                    if len(size_bytes) != 2:
                        break
                    segment_length = struct.unpack(">H", size_bytes)[0]
                    if marker[0] in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                        frame = media_file.read(5)
                        if len(frame) == 5:
                            height, width = struct.unpack(">HH", frame[1:5])
                            return width, height
                        break
                    media_file.seek(max(0, segment_length - 2), os.SEEK_CUR)
            return None
        if extension == ".webp" and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
            if header[12:16] == b"VP8X" and len(header) >= 30:
                width = 1 + int.from_bytes(header[24:27], "little")
                height = 1 + int.from_bytes(header[27:30], "little")
                return width, height
            if header[12:16] == b"VP8L" and len(header) >= 25 and header[20] == 0x2F:
                width = 1 + (((header[22] & 0x3F) << 8) | header[21])
                height = 1 + (((header[24] & 0x0F) << 10) | (header[23] << 2) | ((header[22] & 0xC0) >> 6))
                return width, height
            if header[12:16] == b"VP8 " and len(header) >= 30 and header[23:26] == b"\x9d\x01\x2a":
                width = int.from_bytes(header[26:28], "little") & 0x3FFF
                height = int.from_bytes(header[28:30], "little") & 0x3FFF
                return width, height
            try:
                from PIL import Image
                with Image.open(path) as image_file:
                    return image_file.size
            except ImportError as exc:
                raise ValueError("Pillow is required to validate this WEBP encoding's dimensions.") from exc
        if extension == ".tgs":
            try:
                with gzip.open(path, "rt", encoding="utf-8") as media_file:
                    animation = json.load(media_file)
                return int(animation.get("w", 0)), int(animation.get("h", 0))
            except Exception as exc:
                raise ValueError("TGS sticker is not a valid gzip-compressed animation JSON.") from exc
        if extension in {".mp4", ".webm"}:
            ffprobe = shutil.which("ffprobe")
            if not ffprobe:
                raise ValueError("ffprobe is required to validate video media dimensions.")
            probe = subprocess.run(
                [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", path],
                capture_output=True, text=True, timeout=8, check=False,
            )
            if probe.returncode != 0:
                raise ValueError("Video media could not be decoded for dimension validation.")
            streams = json.loads(probe.stdout or "{}").get("streams") or []
            if streams:
                return int(streams[0].get("width", 0)), int(streams[0].get("height", 0))
        return None

    def register_telegram_media_asset(
        self,
        asset_name: str,
        source_file: str,
        asset_type: str,
        version: str = "1",
        max_bytes: Optional[int] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Validate and persist a branded asset under the repository's media directory."""
        asset_name = str(asset_name or "").strip().upper()
        asset_type = str(asset_type or "").strip().lower()
        version = str(version or "1").strip()
        if not re.fullmatch(r"[A-Z0-9_]{2,100}", asset_name) or not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", version):
            return False, None, "Asset name/version contains unsupported characters."
        accepted = {
            "photo": {".jpg", ".jpeg", ".png"},
            "animation": {".gif", ".mp4"},
            "sticker": {".webp", ".tgs", ".webm"},
        }
        if asset_type not in accepted:
            return False, None, "Asset type must be photo, animation, or sticker."
        media_root = self._telegram_media_root()
        resolved_path = os.path.abspath(source_file if os.path.isabs(source_file) else os.path.join(media_root, source_file))
        try:
            if os.path.commonpath([media_root, resolved_path]) != media_root:
                return False, None, "Media sources must be stored inside taikry/web/static/telegram."
        except ValueError:
            return False, None, "Media sources must be stored inside taikry/web/static/telegram."
        extension = os.path.splitext(resolved_path)[1].lower()
        if extension not in accepted[asset_type] or not os.path.isfile(resolved_path):
            return False, None, f"Missing source file or unsupported {asset_type} format."
        try:
            size_limit = int(max_bytes or os.getenv("TELEGRAM_MEDIA_MAX_BYTES", "10485760"))
        except (TypeError, ValueError):
            return False, None, "TELEGRAM_MEDIA_MAX_BYTES must be a positive integer."
        if size_limit <= 0:
            return False, None, "TELEGRAM_MEDIA_MAX_BYTES must be a positive integer."
        size_bytes = os.path.getsize(resolved_path)
        if size_bytes <= 0 or size_bytes > size_limit:
            return False, None, f"Media file must be between 1 and {size_limit} bytes."
        try:
            dimensions = self._read_media_dimensions(resolved_path, extension)
            if dimensions is None or min(dimensions) <= 0:
                return False, None, "Media dimensions could not be validated."
            width, height = dimensions
            if asset_type == "sticker" and (width > 512 or height > 512):
                return False, None, "Sticker dimensions must not exceed 512 by 512 pixels."
        except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
            return False, None, self._redact_secret(str(exc))

        digest = hashlib.sha256()
        with open(resolved_path, "rb") as media_file:
            for chunk in iter(lambda: media_file.read(1024 * 1024), b""):
                digest.update(chunk)
        asset_id = f"{asset_name}:{asset_type}:{version}"
        db = SessionLocal()
        try:
            record = db.query(TelegramMediaAsset).filter(TelegramMediaAsset.asset_id == asset_id).first()
            if record is None:
                record = TelegramMediaAsset(asset_id=asset_id, asset_name=asset_name, asset_type=asset_type, version=version)
                db.add(record)
            if record.checksum != digest.hexdigest():
                record.telegram_file_id = None
            record.source_file = resolved_path
            record.format = extension.lstrip(".")
            record.checksum = digest.hexdigest()
            record.updated_at = datetime.datetime.utcnow()
            db.commit()
            return True, asset_id, None
        except Exception as exc:
            db.rollback()
            logger.warning("Telegram media asset registration failed: %s", self._redact_secret(str(exc)))
            return False, None, "Media asset could not be stored in the database."
        finally:
            db.close()

    def send_telegram_media_asset(
        self,
        asset_id: str,
        chat_id: Optional[str] = None,
        caption: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Send a registered asset and cache Telegram's reusable file_id after success."""
        target_chat = str(chat_id or self.default_chat_id or "")
        if not self.enabled:
            return False, None, "Telegram notifications are disabled."
        if not self.token or not target_chat:
            return False, None, "Telegram bot token or chat ID is not configured."
        db = SessionLocal()
        try:
            record = db.query(TelegramMediaAsset).filter(TelegramMediaAsset.asset_id == asset_id).first()
            if not record:
                return False, None, "Telegram media asset is not registered."
            snapshot = {
                "asset_id": record.asset_id,
                "asset_type": record.asset_type,
                "source_file": record.source_file,
                "format": record.format,
                "telegram_file_id": record.telegram_file_id,
            }
        finally:
            db.close()
        field_name = {"photo": "photo", "animation": "animation", "sticker": "sticker"}.get(snapshot["asset_type"])
        if not field_name:
            return False, None, "Registered Telegram media type is invalid."
        endpoint = {"photo": "sendPhoto", "animation": "sendAnimation", "sticker": "sendSticker"}[snapshot["asset_type"]]
        url = f"https://api.telegram.org/bot{self.token}/{endpoint}"
        body: Dict[str, Any] = {"chat_id": target_chat}
        if caption and snapshot["asset_type"] != "sticker":
            body["caption"] = caption[:1024]
            body["parse_mode"] = "HTML"
        if reply_markup:
            body["reply_markup"] = reply_markup

        def post_media(use_upload: bool):
            if not use_upload:
                cached_body = dict(body)
                cached_body[field_name] = snapshot["telegram_file_id"]
                return requests.post(url, json=cached_body, timeout=20)
            with open(snapshot["source_file"], "rb") as media_file:
                files = {
                    field_name: (
                        os.path.basename(snapshot["source_file"]),
                        media_file,
                        mimetypes.guess_type(snapshot["source_file"])[0] or "application/octet-stream",
                    )
                }
                return requests.post(url, data=body, files=files, timeout=30)

        try:
            response = post_media(not bool(snapshot["telegram_file_id"]))
            try:
                response_data = response.json()
            except Exception:
                response_data = {}
            if (
                snapshot["telegram_file_id"]
                and response.status_code == 400
                and any(term in str(response_data.get("description", "")).lower() for term in ("wrong file identifier", "file identifier is invalid", "file_id_invalid"))
            ):
                db = SessionLocal()
                try:
                    record = db.query(TelegramMediaAsset).filter(TelegramMediaAsset.asset_id == asset_id).first()
                    if record:
                        record.telegram_file_id = None
                        record.updated_at = datetime.datetime.utcnow()
                        db.commit()
                finally:
                    db.close()
                response = post_media(True)
                try:
                    response_data = response.json()
                except Exception:
                    response_data = {}
            if response.status_code != 200 or not response_data.get("ok"):
                description = self._redact_secret(str(response_data.get("description") or f"Telegram API returned HTTP {response.status_code}"))
                self._audit("telegram", "media_asset", {"asset_id": asset_id, "asset_type": snapshot["asset_type"]}, "FAILED", response.status_code, description)
                return False, None, description

            message = response_data.get("result") or {}
            message_id = str(message.get("message_id") or "") or None
            media_result = message.get("photo")
            if isinstance(media_result, list) and media_result:
                telegram_file_id = media_result[-1].get("file_id")
            elif isinstance(media_result, dict):
                telegram_file_id = media_result.get("file_id")
            else:
                media_result = message.get(snapshot["asset_type"])
                telegram_file_id = media_result.get("file_id") if isinstance(media_result, dict) else None
            if telegram_file_id:
                db = SessionLocal()
                try:
                    record = db.query(TelegramMediaAsset).filter(TelegramMediaAsset.asset_id == asset_id).first()
                    if record:
                        record.telegram_file_id = str(telegram_file_id)
                        record.updated_at = datetime.datetime.utcnow()
                        db.commit()
                except Exception as exc:
                    db.rollback()
                    logger.warning("Telegram media file_id cache failed: %s", self._redact_secret(str(exc)))
                finally:
                    db.close()
            self._audit("telegram", "media_asset", {"asset_id": asset_id, "asset_type": snapshot["asset_type"], "message_id": message_id}, "SENT", response.status_code, None)
            return True, message_id, None
        except requests.exceptions.RequestException as exc:
            error = f"Telegram media delivery outcome is uncertain: {self._redact_secret(str(exc))}"
            self._audit("telegram", "media_asset", {"asset_id": asset_id, "asset_type": snapshot["asset_type"]}, "UNCERTAIN", 0, error)
            return False, None, error
        except Exception as exc:
            return False, None, self._redact_secret(str(exc))

    def _dispatch_persistent_message(
        self,
        text: str,
        idempotency_key: str,
        notification_type: str,
        signal_id: Optional[str] = None,
        event_state: Optional[str] = None,
        chat_id: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
        payload_summary: Optional[Dict[str, Any]] = None,
        analysis_run_id: Optional[str] = None,
        analysis_agent_statuses: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str], Optional[str], str]:
        """Send a keyed signal message with persistent dedupe and uncertainty handling."""
        target_chat = str(chat_id or self.default_chat_id or "")
        if not self.enabled:
            return False, None, "Telegram notifications are disabled", "SUPPRESSED"
        if not target_chat:
            return False, None, "Telegram chat ID is not configured", "FAILED"
        notification_id, state, existing_message_id, claim_error = self._claim_persistent_notification(
            idempotency_key=idempotency_key,
            notification_type=notification_type,
            chat_id=target_chat,
            signal_id=signal_id,
            event_state=event_state,
            payload_summary=payload_summary,
        )
        if state == "SENT":
            return True, existing_message_id, None, state
        if state != "SENDING":
            return False, None, claim_error or f"Telegram delivery state: {state}", state
        if not self.token:
            error = "Telegram bot token is not configured"
            self._set_persistent_notification_status(notification_id, "FAILED", error=error, retry_after_seconds=300)
            return False, None, error, "FAILED"

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        body: Dict[str, Any] = {"chat_id": target_chat, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            body["reply_markup"] = reply_markup
        try:
            progress_run = self._get_analysis_run(analysis_run_id)
            edit_url = f"https://api.telegram.org/bot{self.token}/editMessageText"
            editing_progress = bool(
                progress_run
                and progress_run.get("message_id")
                and str(progress_run.get("chat_id")) == target_chat
            )
            if editing_progress:
                edit_body = dict(body)
                edit_body["message_id"] = int(progress_run["message_id"])
                response = requests.post(edit_url, json=edit_body, timeout=8)
            else:
                response = requests.post(url, json=body, timeout=8)
            try:
                response_data = response.json()
            except Exception:
                response_data = {}
            not_modified = "message is not modified" in str(response_data.get("description", "")).lower()
            if editing_progress and response.status_code == 400:
                description_lower = str(response_data.get("description", "")).lower()
                edit_unavailable = any(token in description_lower for token in (
                    "message to edit not found",
                    "message can't be edited",
                    "message_id_invalid",
                    "message identifier is not specified",
                ))
                if edit_unavailable:
                    # The API explicitly rejected the edit; send one controlled replacement.
                    response = requests.post(url, json=body, timeout=8)
                    try:
                        response_data = response.json()
                    except Exception:
                        response_data = {}
                    editing_progress = False
            if response.status_code == 200 and response_data.get("ok"):
                message_id = str(response_data.get("result", {}).get("message_id") or "") or None
                if editing_progress and progress_run:
                    message_id = str(progress_run["message_id"])
                self._set_persistent_notification_status(notification_id, "SENT", message_id=message_id)
                self._audit("telegram", notification_type, payload_summary or {}, "SENT", 200, None)
                self._persist_analysis_run_result(
                    analysis_run_id, "APPROVED", message_id, analysis_agent_statuses, signal_id
                )
                return True, message_id, None, "SENT"
            if not_modified and editing_progress and progress_run:
                message_id = str(progress_run["message_id"])
                self._set_persistent_notification_status(notification_id, "SENT", message_id=message_id)
                self._persist_analysis_run_result(
                    analysis_run_id, "APPROVED", message_id, analysis_agent_statuses, signal_id
                )
                return True, message_id, None, "SENT"

            description = str(response_data.get("description") or f"Telegram API returned HTTP {response.status_code}")
            if response.status_code == 429:
                retry_after = response_data.get("parameters", {}).get("retry_after", 60)
                try:
                    retry_after = min(3600, max(1, int(retry_after)))
                except (TypeError, ValueError):
                    retry_after = 60
                self._set_persistent_notification_status(
                    notification_id, "RETRY_PENDING", error=description, retry_after_seconds=retry_after
                )
                self._audit("telegram", notification_type, payload_summary or {}, "RETRY_PENDING", 429, description)
                return False, None, description, "RETRY_PENDING"
            if response.status_code >= 500 or not response_data:
                state = "UNCERTAIN"
                retry_after = None
            else:
                state = "FAILED"
                retry_after = 300
            self._set_persistent_notification_status(
                notification_id, state, error=description, retry_after_seconds=retry_after
            )
            self._audit("telegram", notification_type, payload_summary or {}, state, response.status_code, description)
            self._persist_analysis_run_result(
                analysis_run_id, "DELIVERY_UNCERTAIN" if state == "UNCERTAIN" else "FAILED",
                progress_run.get("message_id") if progress_run else None,
                analysis_agent_statuses, signal_id, description,
            )
            return False, None, description, state
        except Exception as exc:
            safe_error = self._redact_secret(str(exc))
            error = f"Telegram request outcome is uncertain: {safe_error}"
            self._set_persistent_notification_status(notification_id, "UNCERTAIN", error=error)
            self._audit("telegram", notification_type, payload_summary or {}, "UNCERTAIN", 0, error)
            self._persist_analysis_run_result(
                analysis_run_id, "DELIVERY_UNCERTAIN", None, analysis_agent_statuses, signal_id, error
            )
            return False, None, error, "UNCERTAIN"

    def _fanout_plan_signal(
        self,
        message: str,
        *,
        source_key: str,
        notification_type: str,
        signal_id: Optional[str],
        symbol: str,
        direction: Optional[str],
        timeframe: str,
        reply_markup: Optional[Dict[str, Any]],
        exclude_chat_id: Optional[str] = None,
        notification_preference: str = "signal_generated",
    ) -> Tuple[int, int]:
        """Deliver an already-approved signal to active, opted-in plan members."""
        if not self.enabled or not self.token:
            return 0, 0
        db = SessionLocal()
        try:
            from taikry.saas.entitlement_service import get_telegram_signal_recipients
            recipients = get_telegram_signal_recipients(
                db, notification_preference=notification_preference
            )
        except Exception as exc:
            logger.warning("Could not resolve subscription signal recipients: %s", self._redact_secret(str(exc)))
            return 0, 0
        finally:
            db.close()

        excluded = str(exclude_chat_id or "")
        delivered = 0
        eligible = 0
        quota_suppressed = 0
        for recipient in recipients:
            target_chat = str(recipient.get("chat_id") or "")
            if not target_chat or target_chat == excluded:
                continue
            eligible += 1
            digest = hashlib.sha256(
                f"{notification_type}:{source_key}:{target_chat}".encode("utf-8")
            ).hexdigest()
            outbox_key = f"plan-signal:{digest}"
            quota_key = None
            if notification_type in {"SIGNAL", "XAUUSD_SIGNAL"}:
                already_sent_db = SessionLocal()
                try:
                    prior_delivery = already_sent_db.query(TelegramNotification).filter(
                        TelegramNotification.idempotency_key == outbox_key
                    ).first()
                    if prior_delivery and prior_delivery.delivery_status == "SENT":
                        delivered += 1
                        continue
                except Exception as exc:
                    logger.warning("Could not verify prior plan signal delivery: %s", self._redact_secret(str(exc)))
                    continue
                finally:
                    already_sent_db.close()

                from taikry.saas.signal_quota_service import (
                    cambodia_date_str,
                    release_signal_alert_slot,
                    reserve_signal_alert_slot,
                    signal_quota_idempotency_key,
                )
                business_date = cambodia_date_str()
                quota_key = signal_quota_idempotency_key(
                    int(recipient["user_id"]), business_date, outbox_key
                )
                quota_db = SessionLocal()
                try:
                    reserved, quota_status = reserve_signal_alert_slot(
                        quota_db,
                        user_id=int(recipient["user_id"]),
                        business_date=business_date,
                        daily_limit=int(recipient.get("max_signal_alerts_per_day") or 0),
                        idempotency_key=quota_key,
                    )
                except Exception as exc:
                    quota_db.rollback()
                    logger.warning(
                        "Could not reserve signal quota for plan %s: %s",
                        recipient.get("plan_id", "unknown"), self._redact_secret(str(exc)),
                    )
                    continue
                finally:
                    quota_db.close()
                if not reserved:
                    quota_suppressed += 1
                    logger.info(
                        "Plan signal cap reached for %s on %s; configured cap is %s",
                        recipient.get("plan_id", "unknown"), business_date,
                        recipient.get("max_signal_alerts_per_day"),
                    )
                    continue

            sent, _message_id, error, state = self._dispatch_persistent_message(
                message,
                idempotency_key=outbox_key,
                notification_type=notification_type,
                signal_id=signal_id,
                event_state="APPROVED",
                chat_id=target_chat,
                reply_markup=reply_markup,
                payload_summary={
                    "symbol": symbol,
                    "direction": direction,
                    "timeframe": timeframe,
                    "plan_id": recipient.get("plan_id"),
                    "delivery_scope": "subscription_member",
                },
            )
            if sent:
                delivered += 1
            else:
                if quota_key and state == "FAILED":
                    quota_db = SessionLocal()
                    try:
                        release_signal_alert_slot(quota_db, quota_key)
                    except Exception as exc:
                        quota_db.rollback()
                        logger.warning("Could not release failed signal quota: %s", self._redact_secret(str(exc)))
                    finally:
                        quota_db.close()
                logger.info(
                    "Subscription signal delivery not confirmed for plan %s (%s): %s",
                    recipient.get("plan_id", "unknown"), state,
                    self._redact_secret(str(error or state)),
                )
        logger.info(
            "Plan signal fanout completed: %s/%s linked recipients confirmed for %s; %s suppressed by daily cap",
            delivered, eligible, notification_type, quota_suppressed,
        )
        return delivered, eligible

    def _fanout_plan_lifecycle_event(
        self,
        event_dict: Dict[str, Any],
        message: str,
        primary_chat_id: Optional[str],
    ) -> Tuple[int, int]:
        event_type = str(event_dict.get("event_type") or "").upper()
        preference = (
            "signal_invalidated"
            if event_type in {"SL_HIT", "SIGNAL_EXPIRED", "SIGNAL_CANCELLED", "SIGNAL_CLOSED", "INVALIDATED"}
            else "signal_generated"
        )
        source_key = str(event_dict.get("idempotency_key") or "").strip()
        if not source_key:
            return 0, 0
        return self._fanout_plan_signal(
            message,
            source_key=source_key,
            notification_type="SIGNAL_LIFECYCLE",
            signal_id=str(event_dict.get("signal_id") or "") or None,
            symbol=str(event_dict.get("symbol") or "XAUUSD").upper(),
            direction=str(event_dict.get("direction") or "NEUTRAL").upper(),
            timeframe=str(event_dict.get("timeframe") or "M15"),
            reply_markup=None,
            exclude_chat_id=primary_chat_id,
            notification_preference=preference,
        )

    @staticmethod
    def _signal_idempotency_key(consensus_result: Dict[str, Any], chat_id: str) -> str:
        """Stable per-day setup fingerprint; later valid setups remain eligible."""
        symbol = str(consensus_result.get("symbol") or "").strip().upper()
        direction = str(consensus_result.get("proposed_direction") or "").strip().upper()
        timeframe = str(consensus_result.get("timeframe") or "M15").strip().upper()
        decimals = 3 if "JPY" in symbol else (2 if symbol.startswith(("XAU", "XAG")) else 5)
        try:
            levels = [
                round(float(consensus_result[key]), decimals)
                for key in ("entry_price", "stop_loss", "take_profit_1")
            ]
        except (KeyError, TypeError, ValueError):
            return "signal-invalid:" + uuid.uuid4().hex
        try:
            from zoneinfo import ZoneInfo
            day = datetime.datetime.now(ZoneInfo("Asia/Phnom_Penh")).date().isoformat()
        except Exception:
            day = datetime.datetime.utcnow().date().isoformat()
        identity = json.dumps([day, symbol, direction, timeframe, *levels, str(chat_id)], separators=(",", ":"))
        return "signal:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @staticmethod
    def _stable_signal_id(consensus_result: Dict[str, Any]) -> str:
        """Create a deterministic display/audit ID for generic setups when none exists."""
        symbol = re.sub(r"[^A-Z0-9]", "", str(consensus_result.get("symbol") or "MARKET").upper())[:10] or "MARKET"
        identity = TelegramService._signal_idempotency_key(consensus_result, "signal-id")
        digest = identity.rsplit(":", 1)[-1][:10].upper()
        try:
            from zoneinfo import ZoneInfo
            date_part = datetime.datetime.now(ZoneInfo("Asia/Phnom_Penh")).strftime("%Y%m%d")
        except Exception:
            date_part = datetime.datetime.utcnow().strftime("%Y%m%d")
        return f"SIG-{date_part}-{symbol}-{digest}"

    def begin_analysis_run(self, symbol: str, chat_id: Optional[str] = None, timeframe: str = "M15") -> Optional[str]:
        """Send one truthful start message and persist its message link for an on-demand scan."""
        target_chat = str(chat_id or self.default_chat_id or "")
        if not self.enabled or not self.token or not target_chat:
            return None
        safe_symbol = html.escape(str(symbol).upper())
        safe_timeframe = html.escape(str(timeframe).upper())
        progress_text = (
            "🧠 <b>ZYROX AI — MARKET ANALYSIS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Market:</b> {safe_symbol} · <b>Timeframe:</b> {safe_timeframe}\n\n"
            "● Market data — VERIFYING\n"
            "○ AI analysis — WAITING\n"
            "○ Risk validation — WAITING\n\n"
            "<b>System status:</b> ANALYZING\n"
            "<i>Updates will reflect backend results. No progress percentage is estimated.</i>"
        )
        sent, message_id, error = self.send_text(progress_text, chat_id=target_chat)
        if not sent or not message_id:
            logger.info("Telegram analysis progress message was not started: %s", self._redact_secret(error or "no message ID"))
            return None

        run_id = uuid.uuid4().hex
        now = datetime.datetime.utcnow()
        db = SessionLocal()
        try:
            db.add(TelegramAnalysisRun(
                run_id=run_id,
                symbol=str(symbol).upper(),
                timeframe=str(timeframe).upper(),
                signal_candidate_id=run_id,
                telegram_chat_id=target_chat,
                telegram_message_id=str(message_id),
                message_type="text",
                status="RUNNING",
                agent_statuses={"market_data": "RUNNING", "ai_analysis": "QUEUED", "risk_validation": "QUEUED"},
                created_at=now,
                updated_at=now,
            ))
            db.commit()
            return run_id
        except Exception as exc:
            db.rollback()
            logger.warning("Failed to persist Telegram analysis run: %s", self._redact_secret(str(exc)))
            self.edit_message_text(
                "⚠️ <b>Analysis progress tracking unavailable.</b> No signal was fabricated.",
                target_chat,
                int(message_id),
            )
            return None
        finally:
            db.close()

    def update_analysis_run_progress(self, run_id: Optional[str], stage: str, backend_statuses: Dict[str, Any]) -> bool:
        """Edit a user-requested progress message only with confirmed backend stage results."""
        run = self._get_analysis_run(run_id)
        if not run or not run.get("message_id"):
            return False
        stage = str(stage).upper()
        market_status = "VERIFIED" if stage in {"MARKET_DATA_VERIFIED", "AGENTS_COMPLETED", "RISK_CHECKING", "RISK_APPROVED", "RISK_REJECTED"} else "RUNNING"
        ai_status = "COMPLETED" if stage in {"AGENTS_COMPLETED", "RISK_CHECKING", "RISK_APPROVED", "RISK_REJECTED"} else "RUNNING"
        risk_status = {
            "MARKET_DATA_VERIFIED": "WAITING",
            "AGENTS_COMPLETED": "WAITING",
            "RISK_CHECKING": "CHECKING",
            "RISK_APPROVED": "APPROVED",
            "RISK_REJECTED": "REJECTED",
        }.get(stage, "WAITING")
        actual_agents = backend_statuses.get("agent_statuses", backend_statuses) if isinstance(backend_statuses, dict) else {}
        agent_lines = []
        if isinstance(actual_agents, dict):
            priority = (
                "technical_analyst", "ict_smc_analyst", "macro_analyst", "risk_validator",
                "data_quality_agent", "orderflow_sentiment_analyst", "fractal_mtf_analyst",
                "regime_detection_agent", "quantitative_research_agent", "ml_forecast_agent",
                "counter_analysis_agent", "portfolio_analysis_agent", "execution_simulation_agent",
                "concept_recommender", "consensus_engine",
            )
            ordered_agents = sorted(
                actual_agents.items(),
                key=lambda pair: (priority.index(str(pair[0])) if str(pair[0]) in priority else len(priority), str(pair[0])),
            )
            for agent_id, status in ordered_agents[:15]:
                if isinstance(status, (dict, list)):
                    continue
                agent_lines.append(f"• {html.escape(str(agent_id))}: <b>{html.escape(str(status))}</b>")
        progress_text = (
            "🧠 <b>ZYROX AI — MARKET ANALYSIS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Market:</b> {html.escape(run['symbol'])} · <b>Timeframe:</b> {html.escape(run['timeframe'])}\n\n"
            f"● Market data — {market_status}\n"
            f"● AI analysis — {ai_status}\n"
            f"{'◐' if risk_status == 'CHECKING' else ('●' if risk_status in {'APPROVED', 'REJECTED'} else '○')} Risk validation — {risk_status}"
        )
        if agent_lines:
            progress_text += "\n\n<b>Agent execution results</b>\n" + "\n".join(agent_lines)
        progress_text += "\n\n<i>Status reflects completed backend stages; no progress percentage is estimated.</i>"

        edited, edit_error, edit_state = self.edit_message_text_detailed(
            progress_text, run["chat_id"], int(run["message_id"])
        )
        db = SessionLocal()
        try:
            record = db.query(TelegramAnalysisRun).filter(TelegramAnalysisRun.run_id == run_id).first()
            if record:
                current = record.agent_statuses if isinstance(record.agent_statuses, dict) else {}
                current.update({
                    "market_data": market_status,
                    "ai_analysis": ai_status,
                    "risk_validation": risk_status,
                    "agents": actual_agents if isinstance(actual_agents, dict) else {},
                })
                record.agent_statuses = current
                if not edited and edit_state == "UNCERTAIN":
                    record.error = self._redact_secret(edit_error or "Progress edit outcome is uncertain")
                record.updated_at = datetime.datetime.utcnow()
                db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("Could not persist Telegram progress stage: %s", self._redact_secret(str(exc)))
        finally:
            db.close()
        return edited

    def _get_analysis_run(self, run_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not run_id:
            return None
        db = SessionLocal()
        try:
            run = db.query(TelegramAnalysisRun).filter(TelegramAnalysisRun.run_id == run_id).first()
            if not run:
                return None
            return {
                "run_id": run.run_id,
                "symbol": run.symbol,
                "timeframe": run.timeframe,
                "signal_candidate_id": run.signal_candidate_id,
                "chat_id": run.telegram_chat_id,
                "message_id": run.telegram_message_id,
                "message_type": run.message_type,
                "status": run.status,
            }
        finally:
            db.close()

    def finish_analysis_run(
        self,
        run_id: Optional[str],
        status: str,
        final_text: str,
        agent_statuses: Optional[Dict[str, Any]] = None,
        signal_id: Optional[str] = None,
    ) -> bool:
        """Finalize an on-demand progress message; on an editable-message failure, fallback once."""
        run = self._get_analysis_run(run_id)
        if not run:
            return False
        message_id = run.get("message_id")
        edited = False
        delivery_confirmed = False
        edit_state = "REJECTED"
        edit_error = None
        if message_id:
            try:
                edited, edit_error, edit_state = self.edit_message_text_detailed(
                    final_text, run["chat_id"], int(message_id)
                )
            except (TypeError, ValueError):
                edited = False
        if not edited and edit_state == "UNCERTAIN":
            self._persist_analysis_run_result(
                run_id, "DELIVERY_UNCERTAIN", message_id, agent_statuses, signal_id,
                edit_error or "Progress-message edit outcome is uncertain; fallback suppressed.",
            )
            return False
        delivery_confirmed = edited
        if not edited:
            sent, fallback_id, error = self.send_text(final_text, chat_id=run["chat_id"])
            if sent and fallback_id:
                message_id = fallback_id
                delivery_confirmed = True
            else:
                logger.warning("Telegram analysis progress finalization failed: %s", self._redact_secret(error or "unknown error"))
                self._persist_analysis_run_result(
                    run_id, "DELIVERY_FAILED", message_id, agent_statuses, signal_id,
                    error or "Final progress message could not be confirmed as delivered.",
                )
                return False

        db = SessionLocal()
        now = datetime.datetime.utcnow()
        try:
            record = db.query(TelegramAnalysisRun).filter(TelegramAnalysisRun.run_id == run_id).first()
            if record:
                record.status = str(status).upper()
                record.telegram_message_id = str(message_id) if message_id else record.telegram_message_id
                record.agent_statuses = agent_statuses or record.agent_statuses
                record.signal_id = signal_id or record.signal_id
                record.signal_candidate_id = signal_id or record.signal_candidate_id
                record.error = None if str(status).upper() in {"APPROVED", "COMPLETED"} else self._redact_secret(final_text[:500])
                record.updated_at = now
                record.completed_at = now
                db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("Failed to persist Telegram analysis completion: %s", self._redact_secret(str(exc)))
        finally:
            db.close()
        return delivery_confirmed

    def _persist_analysis_run_result(
        self,
        run_id: Optional[str],
        status: str,
        message_id: Optional[str],
        agent_statuses: Optional[Dict[str, Any]] = None,
        signal_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        if not run_id:
            return
        db = SessionLocal()
        now = datetime.datetime.utcnow()
        try:
            record = db.query(TelegramAnalysisRun).filter(TelegramAnalysisRun.run_id == run_id).first()
            if record:
                record.status = str(status).upper()
                record.telegram_message_id = str(message_id) if message_id else record.telegram_message_id
                record.agent_statuses = agent_statuses or record.agent_statuses
                record.signal_id = signal_id or record.signal_id
                record.signal_candidate_id = signal_id or record.signal_candidate_id
                record.error = self._redact_secret(error) if error else None
                record.updated_at = now
                record.completed_at = now
                db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("Failed to persist Telegram analysis completion: %s", self._redact_secret(str(exc)))
        finally:
            db.close()

    @staticmethod
    def _agent_status_snapshot(result: Dict[str, Any]) -> Dict[str, Any]:
        """Persist only actual agent status values, not analysis payloads or fabricated progress."""
        raw = result.get("agent_run_summary") or result.get("agents") or result.get("agent_opinions") or {}
        if isinstance(raw, dict) and isinstance(raw.get("agent_statuses"), dict):
            raw = raw["agent_statuses"]
        statuses: Dict[str, Any] = {}
        if isinstance(raw, dict):
            for agent_id, detail in raw.items():
                if isinstance(detail, dict):
                    statuses[str(agent_id)] = str(detail.get("status") or detail.get("execution_status") or "UNKNOWN")
                elif isinstance(detail, str):
                    statuses[str(agent_id)] = detail
                else:
                    statuses[str(agent_id)] = "UNKNOWN"
        elif isinstance(raw, list):
            for index, detail in enumerate(raw):
                if isinstance(detail, dict):
                    agent_id = str(detail.get("agent_id") or detail.get("id") or f"agent_{index + 1}")
                    statuses[agent_id] = str(detail.get("status") or detail.get("execution_status") or "UNKNOWN")
        return statuses

    @classmethod
    def _format_agent_execution_summary(cls, result: Dict[str, Any], limit: int = 12) -> str:
        """Render only reported backend agent statuses for signal transparency."""
        statuses = cls._agent_status_snapshot(result)
        if not statuses:
            return ""
        counts: Dict[str, int] = {}
        for status in statuses.values():
            normalized = str(status).upper()
            counts[normalized] = counts.get(normalized, 0) + 1
        counts_text = " · ".join(
            f"{html.escape(status)} {count}"
            for status, count in sorted(counts.items())
        )
        priority = (
            "technical_analyst", "ict_smc_analyst", "macro_analyst", "risk_validator",
            "data_quality_agent", "orderflow_sentiment_analyst", "fractal_mtf_analyst",
            "regime_detection_agent", "quantitative_research_agent", "ml_forecast_agent",
            "counter_analysis_agent", "portfolio_analysis_agent", "execution_simulation_agent",
            "concept_recommender", "consensus_engine",
        )
        ordered = sorted(
            statuses.items(),
            key=lambda pair: (priority.index(str(pair[0])) if str(pair[0]) in priority else len(priority), str(pair[0])),
        )
        lines = [
            f"• {html.escape(str(agent_id))}: <b>{html.escape(str(status))}</b>"
            for agent_id, status in ordered[:max(1, int(limit))]
        ]
        if len(ordered) > len(lines):
            lines.append(f"• +{len(ordered) - len(lines)} additional reported agents")
        return "🧠 <b>AI agent execution:</b> " + counts_text + "\n" + "\n".join(lines)

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

        # Row 4: Website signal subscription tiers
        keyboard.append([
            {"text": "📦 Normal / Pro / Premium", "callback_data": "account:plans"},
            {"text": "📊 My Signal Plan", "callback_data": "account:myplan"}
        ])

        # Keep the old private VIP-channel membership flow clearly separate.
        keyboard.append([
            {"text": "👑 VIP Channel Plans (separate)", "callback_data": "sub:plans"}
        ])

        return {"inline_keyboard": keyboard}

    def _load_linked_saas_entitlement(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Resolve this private Telegram chat to its website account entitlement."""
        try:
            private_chat_id = int(str(chat_id).strip())
        except (TypeError, ValueError):
            return None
        if private_chat_id <= 0:
            return None

        from taikry.database.models import NotificationPreferences, TelegramLink
        from taikry.saas.entitlement_service import get_user_entitlement

        db = SessionLocal()
        try:
            link = db.query(TelegramLink).filter(
                TelegramLink.telegram_chat_id == str(private_chat_id),
                TelegramLink.is_linked.is_(True),
            ).first()
            if not link:
                return None
            entitlement = get_user_entitlement(db, int(link.user_id))
            preferences = db.query(NotificationPreferences).filter(
                NotificationPreferences.user_id == int(link.user_id)
            ).first()
            entitlement["telegram_signal_notifications_enabled"] = (
                preferences.signal_generated if preferences else True
            )
            return entitlement
        except Exception as exc:
            logger.warning("Telegram SaaS plan lookup failed: %s", self._redact_secret(str(exc)))
            return {"lookup_error": True}
        finally:
            db.close()

    def _consume_linked_plan_analysis_quota(
        self,
        user_id: int,
        chat_id: str,
        request_type: str,
        symbol: str,
    ) -> Optional[str]:
        """Apply website AI quotas to linked Telegram users' interactive scans."""
        if self._is_telegram_admin(user_id):
            return None
        try:
            private_chat_id = int(str(chat_id).strip())
        except (TypeError, ValueError):
            return None
        if private_chat_id <= 0:
            return None

        from taikry.database.models import TelegramLink
        from taikry.saas.entitlement_service import check_and_consume_quota, get_user_entitlement

        db = SessionLocal()
        try:
            link = db.query(TelegramLink).filter(
                TelegramLink.telegram_chat_id == str(private_chat_id),
                TelegramLink.is_linked.is_(True),
            ).first()
            if not link:
                return None

            entitlement = get_user_entitlement(db, int(link.user_id))
            if not entitlement.get("is_active"):
                return (
                    "⛔ <b>Your website plan or trial is inactive.</b> Renew or activate a plan to use Telegram AI scans.\n"
                    "🇰🇭 គម្រោង ឬការសាកល្បងរបស់អ្នកអសកម្ម។ សូមបន្ត ឬបើកគម្រោង ដើម្បីប្រើ AI scan ក្នុង Telegram។"
                )
            if request_type == "deep_analysis" and not entitlement.get("quotas", {}).get("agent_debate_enabled"):
                return (
                    "🔒 <b>AI Agent Debate is not included in your current tier.</b> Upgrade from the website plan page to unlock it.\n"
                    "🇰🇭 កញ្ចប់បច្ចុប្បន្នមិនរួមបញ្ចូល AI Agent Debate ទេ។ សូមដំឡើងគម្រោងនៅគេហទំព័រ។"
                )

            allowed, reason, _current_entitlement = check_and_consume_quota(
                db,
                int(link.user_id),
                request_type,
                symbol=symbol,
            )
            if not allowed:
                return f"⏳ <b>Plan quota reached:</b> {html.escape(str(reason))}\n🇰🇭 អ្នកបានប្រើកូតាប្រចាំថ្ងៃអស់ហើយ។ សូមពិនិត្យ /myplan។"
            return None
        except Exception as exc:
            db.rollback()
            logger.warning("Telegram plan quota check failed: %s", self._redact_secret(str(exc)))
            return (
                "⚠️ <b>Could not verify your plan quota.</b> The scan was not started; please retry shortly.\n"
                "🇰🇭 មិនអាចផ្ទៀងផ្ទាត់កូតាគម្រោងបានទេ។ មិនបានចាប់ផ្តើមស្កេនឡើយ សូមសាកល្បងម្ដងទៀត។"
            )
        finally:
            db.close()

    def _billing_keyboard(self) -> Dict[str, Any]:
        rows = [[{"text": "📊 My Signal Plan", "callback_data": "account:myplan"}]]
        billing_url = f"{PUBLIC_APP_URL.rstrip('/')}/dashboard/billing.html" if PUBLIC_APP_URL else ""
        if billing_url.startswith("https://"):
            rows.insert(0, [{"text": "🌐 Manage plan on website", "url": billing_url}])
        return {"inline_keyboard": rows}

    def build_saas_plan_catalog_message(self) -> Tuple[str, Dict[str, Any]]:
        """Show the same Normal/Trial, Pro, and Premium entitlements as the website."""
        from taikry.saas.entitlement_service import get_all_plans

        db = SessionLocal()
        try:
            plans = get_all_plans(db)
        except Exception as exc:
            logger.warning("Telegram plan catalog could not load: %s", self._redact_secret(str(exc)))
            return (
                "⚠️ <b>Plan catalog is temporarily unavailable.</b> Please open the website billing page and try again.\n"
                "🇰🇭 បញ្ជីកញ្ចប់មិនអាចបង្ហាញបានឥឡូវនេះទេ។ សូមពិនិត្យទំព័រ Billing នៅលើគេហទំព័រ។",
                self._billing_keyboard(),
            )
        finally:
            db.close()

        plans.sort(key=lambda plan: {"free_trial": 0, "pro": 1, "premium": 2}.get(str(plan.get("id") or "").lower(), 3))

        tier_names = {
            "free_trial": ("NORMAL / 14-Day Trial", "NORMAL / សាកល្បង ១៤ ថ្ងៃ"),
            "pro": ("PRO", "PRO"),
            "premium": ("PREMIUM", "PREMIUM"),
        }
        lines = [
            "📦 <b>ZYROX WEBSITE SIGNAL PLANS</b>",
            "🇰🇭 <b>កញ្ចប់សញ្ញា Telegram តាមគម្រោងគេហទំព័រ</b>",
            "━━━━━━━━━━━━━━━━━━━━",
        ]
        for plan in plans:
            plan_id = str(plan.get("id") or "").lower()
            english_name, khmer_name = tier_names.get(
                plan_id,
                (str(plan.get("name_en") or plan_id.upper()), str(plan.get("name_kh") or plan_id.upper())),
            )
            price = float(plan.get("price_usd") or 0)
            interval = str(plan.get("billing_interval") or "monthly")
            price_text = "FREE" if price <= 0 else f"${price:,.2f} USD / {html.escape(interval)}"
            target = max(0, int(plan.get("signal_alerts_target_min_per_day") or 0))
            cap = max(0, int(plan.get("max_signal_alerts_per_day") or 0))
            lines.extend([
                f"<b>{html.escape(english_name)}</b> — {price_text}",
                f"🇰🇭 <b>{html.escape(khmer_name)}</b>",
                f"• Approved Telegram signals: <b>{target}–{cap}/day target, {cap} max</b>",
                f"• សញ្ញាដែលបានអនុម័ត៖ គោលដៅ <b>{target}–{cap}/ថ្ងៃ</b> អតិបរមា <b>{cap}</b>",
                f"• AI scans/day: {int(plan.get('max_ai_scans_per_day') or 0)} · Deep analyses/day: {int(plan.get('max_deep_analysis_per_day') or 0)}",
                f"• Watchlists: {int(plan.get('max_watchlists') or 0)} · Agent debate: {'included' if plan.get('agent_debate_enabled') else 'not included'}",
                "",
            ])
        lines.extend([
            "⚠️ Daily signal counts are targets and caps, not guaranteed minimums. Only validated setups are sent; some days can have fewer or no signals.",
            "🇰🇭 ចំនួនសញ្ញាជាគោលដៅ និងអតិបរមា មិនមែនជាការធានាចំនួនអប្បបរមាទេ។ ផ្ញើតែ setup ដែលឆ្លងការផ្ទៀងផ្ទាត់ ហើយថ្ងៃខ្លះអាចមានសញ្ញាតិច ឬគ្មានសញ្ញា។",
            "XAUUSD has an additional global limit of 4 signals/day; plan caps apply across all eligible markets combined.",
            "XAUUSD មានកំណត់អតិបរមាសកលបន្ថែម ៤ សញ្ញា/ថ្ងៃ; កូតាគម្រោងរាប់រួមគ្រប់ទីផ្សារដែលមានសិទ្ធិ។",
            "Use /myplan after linking your website account to see your active tier and daily usage.",
        ])
        return "\n".join(lines), self._billing_keyboard()

    def build_saas_plan_status_message(
        self,
        chat_id: str,
        entitlement: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Show the linked website plan, current quotas, and Telegram signal capacity."""
        if entitlement is None:
            entitlement = self._load_linked_saas_entitlement(chat_id)
        if entitlement is None:
            billing_url = f"{PUBLIC_APP_URL.rstrip('/')}/dashboard/" if PUBLIC_APP_URL else ""
            rows = [[{"text": "📦 View Normal / Pro / Premium", "callback_data": "account:plans"}]]
            if billing_url.startswith("https://"):
                rows.insert(0, [{"text": "🔗 Sign in & link Telegram", "url": billing_url}])
            return (
                "🔗 <b>This private Telegram chat is not linked to a website account.</b>\n"
                "Sign in to the website, connect Telegram in Account Center, then run /myplan again.\n\n"
                "🇰🇭 គណនី Telegram នេះមិនទាន់ភ្ជាប់ទៅគណនីគេហទំព័រទេ។ សូមចូលគណនី ភ្ជាប់ Telegram នៅ Account Center ហើយសាកល្បង /myplan ម្តងទៀត។",
                {"inline_keyboard": rows},
            )
        if entitlement.get("lookup_error"):
            return (
                "⚠️ <b>Could not load your website plan right now.</b> Please try /myplan again shortly.\n"
                "🇰🇭 មិនអាចទាញយកព័ត៌មានគម្រោងបានទេ។ សូមសាកល្បងម្ដងទៀតបន្តិចទៀត។",
                self._billing_keyboard(),
            )

        plan = entitlement.get("plan") or {}
        quotas = entitlement.get("quotas") or {}
        plan_id = str(plan.get("id") or "free_trial").lower()
        tier_name = {"free_trial": "NORMAL / TRIAL", "pro": "PRO", "premium": "PREMIUM"}.get(plan_id, plan_id.upper())
        active = bool(entitlement.get("is_active"))
        status = html.escape(str(entitlement.get("subscription_status") or "unknown"))
        signal_cap = max(0, int(quotas.get("max_signal_alerts_per_day") or 0))
        signal_target = max(0, int(quotas.get("signal_alerts_target_min_per_day") or 0))
        signal_used = max(0, int(quotas.get("signal_alerts_reserved_today") or 0))
        signal_remaining = max(0, int(quotas.get("signal_alerts_remaining_today") or 0))
        active_line = "🟢 Active" if active else "🔴 Inactive — signal delivery paused"
        active_line_kh = "🟢 សកម្ម" if active else "🔴 អសកម្ម — ផ្អាកការផ្ញើសញ្ញា"
        text = f"""📊 <b>MY WEBSITE SIGNAL PLAN</b>
🇰🇭 <b>ស្ថានភាពគម្រោងសញ្ញារបស់ខ្ញុំ</b>
━━━━━━━━━━━━━━━━━━━━
🏷️ <b>Tier:</b> {html.escape(tier_name)} · {html.escape(str(plan.get('name_en') or ''))}
📌 <b>Status:</b> {active_line} (<code>{status}</code>)
🇰🇭 <b>គម្រោង:</b> {html.escape(tier_name)} · {active_line_kh}
⏳ <b>Access remaining:</b> {max(0, int(entitlement.get('days_remaining') or 0))} days · {max(0, int(entitlement.get('hours_remaining') or 0))} hours
🇰🇭 <b>សុពលភាពនៅសល់:</b> {max(0, int(entitlement.get('days_remaining') or 0))} ថ្ងៃ · {max(0, int(entitlement.get('hours_remaining') or 0))} ម៉ោង

📨 <b>Telegram signal slots today:</b> {signal_used}/{signal_cap} allocated · {signal_remaining} remaining
🎯 <b>Daily signal target:</b> {signal_target}–{signal_cap} maximum (not guaranteed)
🔎 <b>AI scans:</b> {int(quotas.get('standard_scans_used_today') or 0)}/{int(quotas.get('max_ai_scans_per_day') or 0)} used
🧠 <b>Deep analyses:</b> {int(quotas.get('deep_analysis_used_today') or 0)}/{int(quotas.get('max_deep_analysis_per_day') or 0)} used
📚 <b>Watchlists:</b> {int(quotas.get('max_watchlists') or 0)} · Backtesting: {'Yes' if quotas.get('backtesting_enabled') else 'No'} · Agent debate: {'Yes' if quotas.get('agent_debate_enabled') else 'No'}
📡 <b>Telegram alerts included:</b> {'Yes' if quotas.get('telegram_alerts_enabled') else 'No'}
🔔 <b>Your signal notification preference:</b> {'On' if entitlement.get('telegram_signal_notifications_enabled') else 'Off'}

🇰🇭 <b>ការប្រើប្រាស់ថ្ងៃនេះ:</b> សញ្ញាបានកក់ {signal_used}/{signal_cap} · នៅសល់ {signal_remaining}
ចំនួនសញ្ញាជាគោលដៅ និងអតិបរមា។ ផ្ញើតែ setup ដែលបានផ្ទៀងផ្ទាត់ប៉ុណ្ណោះ; មិនធានាចំនួនអប្បបរមាទេ។"""
        return text, self._billing_keyboard()

    def build_signal_keyboard(self, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """Builds contextual action buttons for signal alerts."""
        keyboard: List[List[Dict[str, Any]]] = []
        clean_symbol = str(symbol or "XAUUSD").strip().upper()
        if not re.fullmatch(r"[A-Z0-9/_-]{1,20}", clean_symbol):
            clean_symbol = "XAUUSD"
        tradingview_symbol = clean_symbol
        if clean_symbol.endswith("USDT"):
            tradingview_symbol = f"BINANCE:{clean_symbol}"
        elif len(clean_symbol) == 6 and clean_symbol.isalpha():
            tradingview_symbol = f"OANDA:{clean_symbol}"
        elif clean_symbol in {"XAUUSD", "XAGUSD"}:
            tradingview_symbol = f"OANDA:{clean_symbol}"

        if self.webapp_url:
            keyboard.append([
                {"text": "📊 OPEN DASHBOARD", "web_app": {"url": self.webapp_url}}
            ])

        keyboard.append([
            {"text": "🔍 FULL ANALYSIS", "callback_data": f"debate:{clean_symbol}"},
            {"text": "📰 NEWS RISK", "callback_data": "calendar:news"}
        ])

        keyboard.append([
            {"text": "📈 OPEN CHART", "url": f"https://www.tradingview.com/chart/?symbol={quote(tradingview_symbol, safe='')}"},
            {"text": f"↻ SCAN {clean_symbol}", "callback_data": f"scan:{clean_symbol}"}
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
            str(consensus_result.get("setup_timeframe") or consensus_result.get("timeframe") or "M15").upper(),
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
        agent_summary = TelegramService._format_agent_execution_summary(consensus_result)
        agent_block = f"\n{agent_summary}" if agent_summary else ""
        signal_id = html.escape(str(consensus_result.get("signal_id") or "N/A"))
        source = html.escape(str(consensus_result.get("price_source") or "N/A"))
        updated_at = html.escape(str(consensus_result.get("timestamp_utc") or "N/A"))
        invalidation = html.escape(str(
            consensus_result.get("invalidation_rules")
            or "Setup invalid if its verified market data or structure becomes stale."
        ))

        return f"""{icon} <b>ZYROX AI — MARKET INTELLIGENCE</b>
━━━━━━━━━━━━━━━━━━━━
🟡 <b>{symbol}</b> · <b>{html.escape(str(consensus_result.get("trade_style") or "INTRADAY").upper())}</b>
⭐ <b>AI SCORE:</b> {score:.0f}% · {label}
🎯 <b>ACTION:</b> {direction}
💵 <b>ENTRY / តម្លៃចូល:</b> <code>{entry:.{decimals}f}</code>
🛑 <b>STOP LOSS / កាត់ខាត:</b> <code>{stop_loss:.{decimals}f}</code>
🎯 <b>TAKE PROFIT 1 / គោលដៅចំណេញទី ១:</b> <code>{take_profit:.{decimals}f}</code>
🚀 <b>TAKE PROFIT 2 / គោលដៅចំណេញទី ២:</b> <code>{tp2}</code>
{agent_block}
⚖️ <b>RISK / REWARD:</b> {rr}
⚠️ <b>INVALIDATION:</b> {invalidation}
📡 <b>DATA SOURCE:</b> {source}
🕒 <b>UPDATED:</b> {updated_at} UTC
🆔 <b>SIGNAL ID:</b> <code>{signal_id}</code>
🇰🇭 <b>សកម្មភាព:</b> {action_kh}
⚠️ <i>Analysis is probabilistic. Trading involves risk; no broker order is placed by this alert.</i>
🤖 <i>ZYROX AI · Smarter Analysis. Better Decisions.</i>"""

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
        if not self.enabled or not self.token:
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
            response_data = r.json()
            if r.status_code == 200 and response_data.get("ok"):
                self._audit("telegram", "message", {"text_len": len(text)}, "SENT", 200, None)
                return True
            else:
                error = self._redact_secret(str(response_data.get("description") or f"HTTP {r.status_code}"))
                self._audit("telegram", "message", {"text_len": len(text)}, "FAILED", r.status_code, error)
                return False
        except Exception as e:
            self._audit("telegram", "message", {"text_len": len(text)}, "FAILED", 0, self._redact_secret(str(e)))
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
        if not self.enabled:
            return False, None, "Telegram notifications are disabled"
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
            safe_err = self._redact_secret(str(e))
            self._audit("telegram", "text_message", {"text_len": len(text)}, "FAILED", 0, safe_err)
            return False, None, safe_err


    def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False
    ) -> bool:
        """Acknowledges incoming callback query to remove loading spinner in Telegram."""
        if not self.enabled or not self.token or not callback_query_id:
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
            logger.warning("Failed to answer callback query: %s", self._redact_secret(str(e)))
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
        success, _, _ = self.edit_message_text_detailed(
            text, chat_id, message_id, reply_markup=reply_markup, parse_mode=parse_mode
        )
        return success

    def edit_message_text_detailed(
        self,
        text: str,
        chat_id: str,
        message_id: int,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = "HTML",
    ) -> Tuple[bool, Optional[str], str]:
        """Return edit outcome as SUCCESS, REJECTED, or UNCERTAIN for safe fallback decisions."""
        if not self.enabled:
            return False, "Telegram notifications are disabled", "REJECTED"
        if not self.token:
            return False, "Telegram bot token is not configured", "REJECTED"

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
            response = requests.post(url, json=body, timeout=6)
            try:
                data = response.json()
            except Exception:
                data = {}
            description = str(data.get("description") or "")
            if response.status_code == 200 and data.get("ok"):
                return True, None, "SUCCESS"
            if "message is not modified" in description.lower():
                return True, None, "SUCCESS"
            error = self._redact_secret(description or f"Telegram edit returned HTTP {response.status_code}")
            if response.status_code >= 500 or not data:
                return False, error, "UNCERTAIN"
            return False, error, "REJECTED"
        except requests.exceptions.RequestException as exc:
            error = self._redact_secret(str(exc))
            logger.warning("Telegram message edit outcome is uncertain: %s", error)
            return False, error, "UNCERTAIN"
        except Exception as exc:
            error = self._redact_secret(str(exc))
            logger.warning("Telegram message edit failed: %s", error)
            return False, error, "REJECTED"

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
        if not self.enabled:
            return False, None, "Telegram notifications are disabled."
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
        if not self.enabled:
            return False, "Telegram notifications are disabled."
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
        if not self.enabled:
            return False, "Telegram notifications are disabled."
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
        if not self.enabled:
            return False, None, "Telegram notifications are disabled."
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
        """Compatibility wrapper. `force` no longer bypasses approval or signal safety."""
        if force:
            logger.warning("Ignoring legacy force=True; Telegram signals must pass strict validation")
        symbol = str(consensus_result.get("symbol") or "").strip().upper()
        if symbol in {"XAUUSD", "GOLD", "XAU/USD", "XAU_USD"}:
            logger.info("Generic Telegram sender refuses XAUUSD; use the dedicated quota-checked XAUUSD pipeline")
            return False
        return self.send_validated_signal_report(consensus_result, with_buttons=with_buttons)

    def send_validated_signal_report(
        self,
        consensus_result: Dict[str, Any],
        with_buttons: bool = True,
        chat_id: Optional[str] = None,
        analysis_run_id: Optional[str] = None,
    ) -> bool:
        """Send an automatic signal only when the original consensus plan is fully validated."""
        consensus_result = dict(consensus_result or {})
        if not consensus_result.get("signal_id"):
            consensus_result["signal_id"] = self._stable_signal_id(consensus_result)
        symbol = str(consensus_result.get("symbol") or "").strip().upper()
        target_chat = str(chat_id or self.default_chat_id or "")
        if not symbol or symbol in {"XAUUSD", "GOLD", "XAU/USD", "XAU_USD"} or not self.token or not target_chat:
            if analysis_run_id:
                self.finish_analysis_run(
                    analysis_run_id,
                    "REJECTED" if symbol in {"XAUUSD", "GOLD", "XAU/USD", "XAU_USD"} else "FAILED",
                    "⚠️ <b>Signal was not sent.</b> Use the dedicated gold pipeline for XAUUSD and configure a Telegram bot/chat for other symbols.",
                    self._agent_status_snapshot(consensus_result),
                    str(consensus_result.get("signal_id") or "") or None,
                )
            return False

        message = self._format_approved_signal(consensus_result)
        if not message:
            if analysis_run_id:
                self.finish_analysis_run(
                    analysis_run_id,
                    "REJECTED",
                    "⚠️ <b>No signal approved.</b> Freshness, direction, risk/return or required price levels did not pass validation.",
                    self._agent_status_snapshot(consensus_result),
                    str(consensus_result.get("signal_id") or "") or None,
                )
            return False
        idempotency_key = self._signal_idempotency_key(consensus_result, target_chat)
        signal_id = str(consensus_result.get("signal_id") or "") or None
        agent_statuses = self._agent_status_snapshot(consensus_result)
        sent, message_id, error, state = self._dispatch_persistent_message(
            message,
            idempotency_key=idempotency_key,
            notification_type="SIGNAL",
            signal_id=signal_id,
            event_state="APPROVED",
            chat_id=target_chat,
            reply_markup=self.build_signal_keyboard(symbol) if with_buttons else None,
            payload_summary={"symbol": symbol, "direction": consensus_result.get("proposed_direction"), "timeframe": consensus_result.get("timeframe", "M15")},
            analysis_run_id=analysis_run_id,
            analysis_agent_statuses=agent_statuses,
        )
        if analysis_run_id and not sent:
            self.finish_analysis_run(
                analysis_run_id,
                "DELIVERY_UNCERTAIN" if state == "UNCERTAIN" else "FAILED",
                f"⚠️ <b>Signal was not confirmed as delivered.</b> {html.escape(str(error or state))}\n\nNo automatic resend was attempted.",
                agent_statuses,
                signal_id,
            )
        elif analysis_run_id and sent:
            run = self._get_analysis_run(analysis_run_id)
            if run and run.get("status") == "RUNNING":
                self.finish_analysis_run(
                    analysis_run_id,
                    "COMPLETED",
                    f"✅ <b>This approved setup was already delivered.</b> No duplicate signal was sent.\nMessage ID: <code>{html.escape(str(message_id or 'N/A'))}</code>",
                    agent_statuses,
                    signal_id,
                )
        if sent and message_id and signal_id:
            self._link_lifecycle_signal_message(signal_id, str(message_id))
        if sent and chat_id is None:
            self._fanout_plan_signal(
                message,
                source_key=signal_id or idempotency_key,
                notification_type="SIGNAL",
                signal_id=signal_id,
                symbol=symbol,
                direction=str(consensus_result.get("proposed_direction") or ""),
                timeframe=str(consensus_result.get("timeframe") or "M15"),
                reply_markup=self.build_signal_keyboard(symbol) if with_buttons else None,
                exclude_chat_id=target_chat,
            )
        return sent

    def _link_lifecycle_signal_message(self, signal_id: str, message_id: str) -> None:
        """Attach a generic signal's Telegram message ID to its lifecycle row."""
        from taikry.database.models import SignalLifecycleModel
        db = SessionLocal()
        try:
            db.query(SignalLifecycleModel).filter(
                SignalLifecycleModel.signal_id == signal_id
            ).update({"telegram_message_id": str(message_id), "updated_at": datetime.datetime.utcnow()}, synchronize_session=False)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("Could not link Telegram message to signal lifecycle: %s", self._redact_secret(str(exc)))
        finally:
            db.close()

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
ជ្រើសរើសមុខងារខាងក្រោម៖ <code>/plans</code> មើល Normal/Pro/Premium, <code>/myplan</code> មើលគម្រោងដែលភ្ជាប់, <code>/scan EURUSD</code> វិភាគទីផ្សារ, <code>/news</code> មើលព័ត៌មាន។
Use <code>/vip</code> only for the separate legacy VIP Channel membership."""
            return {
                "text": text,
                "reply_markup": self.build_main_menu_keyboard()
            }

        if cmd in ["/gold", "/scan", "/alert", "/signal", "/best"] or cmd.startswith("/scan"):
            parts = command.strip().split()
            symbol = parts[1].upper() if len(parts) > 1 else "XAUUSD"
            quota_message = self._consume_linked_plan_analysis_quota(
                user_id, chat_id, "standard_scan", symbol
            )
            if quota_message:
                return {"text": quota_message}
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
            quota_message = self._consume_linked_plan_analysis_quota(
                user_id, chat_id, "deep_analysis", "XAUUSD"
            )
            if quota_message:
                return {"text": quota_message}
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

        # Website SaaS plan commands; legacy private VIP-channel plans stay under /vip.
        if cmd in ["/plans", "/pricing", "/subscription", "/subscribe"]:
            text, buttons = self.build_saas_plan_catalog_message()
            return {"text": text, "reply_markup": buttons}

        if cmd in ["/account", "/plan", "/signalplan"]:
            text, buttons = self.build_saas_plan_status_message(chat_id)
            return {"text": text, "reply_markup": buttons}

        if cmd == "/myplan":
            linked_entitlement = self._load_linked_saas_entitlement(chat_id)
            if linked_entitlement is not None:
                text, buttons = self.build_saas_plan_status_message(chat_id, linked_entitlement)
                return {"text": text, "reply_markup": buttons}
            from taikry.subscriptions.vip_manager import vip_subscription_manager
            text, buttons = vip_subscription_manager.build_user_status_message(user_id)
            text += "\n\nFor website signal plans, use /plans. Link your website account to Telegram to show that tier here.\n"
            text += "🇰🇭 សម្រាប់គម្រោងសញ្ញានៅគេហទំព័រ សូមប្រើ /plans ហើយភ្ជាប់គណនី Telegram របស់អ្នក។"
            return {"text": text, "reply_markup": buttons}

        if cmd == "/vip":
            from taikry.subscriptions.vip_manager import vip_subscription_manager
            text = vip_subscription_manager.build_plans_message()
            buttons = vip_subscription_manager.build_plans_keyboard()
            return {"text": text, "reply_markup": buttons}

        if cmd in ["/myvip", "/status_vip", "/statusvip"]:
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

        if data == "account:plans":
            text, buttons = self.build_saas_plan_catalog_message()
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            else:
                self.send_message(text, chat_id=chat_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "account_plans"}

        elif data == "account:myplan":
            text, buttons = self.build_saas_plan_status_message(chat_id)
            if message_id:
                self.edit_message_text(text, chat_id, message_id, reply_markup=buttons)
            else:
                self.send_message(text, chat_id=chat_id, reply_markup=buttons)
            return {"status": "SUCCESS", "action": "account_myplan"}

        # 1. Scan asset
        if data.startswith("scan:"):
            symbol = data.split(":", 1)[1].strip().upper()
            from taikry.config import WATCHLIST
            allowed_symbols = {str(item.get("symbol", "")).upper() for item in WATCHLIST if isinstance(item, dict)}
            from taikry.trading.xauusd_signal_engine import normalize_xauusd_symbol, xauusd_signal_engine
            canonical_gold = normalize_xauusd_symbol(symbol)
            if not canonical_gold and symbol not in allowed_symbols:
                return {"status": "FORBIDDEN", "action": "scan", "message": "Unsupported market symbol."}
            quota_message = self._consume_linked_plan_analysis_quota(
                user_id, chat_id, "standard_scan", canonical_gold or symbol
            )
            if quota_message:
                self.send_message(quota_message, chat_id=chat_id)
                return {"status": "FORBIDDEN", "action": "scan", "message": "Plan quota denied"}
            analysis_run_id = self.begin_analysis_run(symbol, chat_id=str(chat_id), timeframe="M15")

            if canonical_gold:
                progress_callback = (
                    lambda stage, statuses: self.update_analysis_run_progress(analysis_run_id, stage, statuses)
                ) if analysis_run_id else None
                result = xauusd_signal_engine.generate_xauusd_signal(
                    canonical_gold, progress_callback=progress_callback
                )
                if not result.get("success"):
                    reason = html.escape(str(result.get("error") or result.get("status") or "No validated setup"))
                    if analysis_run_id:
                        self.finish_analysis_run(
                            analysis_run_id,
                            "REJECTED",
                            f"⚠️ <b>XAUUSD scan suppressed</b>\n\n{reason}\n\n🇰🇭 មិនមានសញ្ញាដែលបានឆ្លងការត្រួតពិនិត្យទាំងអស់ទេ។",
                            self._agent_status_snapshot(result),
                        )
                    else:
                        self.send_message(
                            f"⚠️ <b>XAUUSD scan suppressed</b>\n\n{reason}\n\n🇰🇭 មិនមានសញ្ញាដែលបានឆ្លងការត្រួតពិនិត្យទាំងអស់ទេ។",
                            chat_id=chat_id,
                        )
                    return {"status": "SUPPRESSED", "action": "scan", "symbol": canonical_gold, "reason": result.get("status")}
                sent, message_id_sent, error = self.send_xauusd_signal_alert(
                    result, chat_id=str(chat_id), analysis_run_id=analysis_run_id
                )
                if sent:
                    feedback = f"✅ <b>XAUUSD signal delivered</b>\nSignal ID: <code>{html.escape(str(result.get('signal_id')))}</code>\nMessage ID: <code>{html.escape(str(message_id_sent or 'N/A'))}</code>"
                else:
                    feedback = f"⚠️ <b>XAUUSD signal not delivered</b>\n{html.escape(str(error or 'Delivery unavailable'))}"
                if not analysis_run_id:
                    self.send_message(feedback, chat_id=chat_id)
                return {"status": "SUCCESS" if sent else "FAILED", "action": "scan", "symbol": canonical_gold, "telegram_message_id": message_id_sent}

            from taikry.agents.consensus_engine import ai_consensus_engine
            progress_callback = (
                lambda stage, statuses: self.update_analysis_run_progress(analysis_run_id, stage, statuses)
            ) if analysis_run_id else None
            result = ai_consensus_engine.analyze_symbol(
                symbol, force_refresh=True, progress_callback=progress_callback
            )
            sent = self.send_validated_signal_report(result, chat_id=str(chat_id), analysis_run_id=analysis_run_id)
            if sent:
                feedback = f"✅ <b>{html.escape(symbol)} signal delivered</b>. Entry, SL and targets are in the new signal message."
            else:
                feedback = f"⚠️ <b>{html.escape(symbol)} signal suppressed</b>. The setup is not fresh/approved, lacks valid levels, or delivery is pending/uncertain."
            if not analysis_run_id:
                self.send_message(feedback, chat_id=chat_id)
            return {"status": "SUCCESS" if sent else "SUPPRESSED", "action": "scan", "symbol": symbol}

        # 2. AI Debate
        elif data.startswith("debate:"):
            requested_symbol = data.split(":", 1)[1].strip().upper()
            from taikry.config import WATCHLIST
            allowed_symbols = {str(item.get("symbol", "")).upper() for item in WATCHLIST if isinstance(item, dict)}
            from taikry.trading.xauusd_signal_engine import normalize_xauusd_symbol
            canonical_gold = normalize_xauusd_symbol(requested_symbol)
            if not canonical_gold and requested_symbol not in allowed_symbols:
                if callback_query_id:
                    self.answer_callback_query(callback_query_id, text="Unsupported market symbol.", show_alert=True)
                return {"status": "FORBIDDEN", "action": "debate", "message": "Unsupported market symbol."}
            symbol = canonical_gold or requested_symbol
            quota_message = self._consume_linked_plan_analysis_quota(
                user_id, chat_id, "deep_analysis", symbol
            )
            if quota_message:
                self.send_message(quota_message, chat_id=chat_id)
                return {"status": "FORBIDDEN", "action": "debate", "message": "Plan quota denied"}
            from taikry.agents.debate_engine import agent_debate_engine
            res = agent_debate_engine.conduct_debate(symbol, "M15")
            text = f"""💬 <b>AI AGENTS ROUND-TABLE DEBATE ({html.escape(symbol)})</b>
━━━━━━━━━━━━━━━━━━━━
🏛 <b>Consensus:</b> {html.escape(str(res.get('status', 'UNKNOWN')))}
⚖️ <b>Ruling:</b> {html.escape(str(res.get('verdict', {}).get('decision', 'UNKNOWN')))}

🇰🇭 <b>សេចក្តីសម្រេច និងការវាយតម្លៃហានិភ័យ:</b>
{html.escape(str(res.get('debate_summary_kh', '')))}

🇬🇧 <b>Institutional Synthesis:</b>
{html.escape(str(res.get('debate_summary_en', '')))}"""
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
                lines.append(f"🔴 <b>{html.escape(str(ev.get('title', 'Unknown event')))}</b> ({html.escape(str(ev.get('country', 'N/A')))})")
                lines.append(f"🇰🇭 <i>{html.escape(str(ev.get('title_kh', '')))}</i>")
                lines.append(f"⏳ <b>Time:</b> {html.escape(str(ev.get('time_until', 'N/A')))} | <b>FC:</b> {html.escape(str(ev.get('forecast', 'N/A')))} | <b>Prev:</b> {html.escape(str(ev.get('previous', 'N/A')))}")
                lines.append(f"💡 {html.escape(str(ev.get('gold_impact_kh', '')))}\n")

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

    def send_xauusd_signal_alert(
        self,
        signal_data: Dict[str, Any],
        chat_id: Optional[str] = None,
        analysis_run_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Dispatches validated XAUUSD-only trading signal to Telegram with strict response verification,
        persistent delivery status tracking, and idempotency protection.
        """
        signal_id = str(signal_data.get("signal_id") or "").strip()

        def reject(reason: str) -> Tuple[bool, Optional[str], Optional[str]]:
            if analysis_run_id:
                self.finish_analysis_run(
                    analysis_run_id,
                    "REJECTED",
                    f"⚠️ <b>XAUUSD signal suppressed.</b> {html.escape(str(reason))}",
                    self._agent_status_snapshot(signal_data),
                    signal_id or None,
                )
            return False, None, reason

        if not self.enabled:
            return reject("Telegram notifications are disabled.")

        raw_sym = str(signal_data.get("canonical_symbol") or signal_data.get("symbol") or "").upper()
        if raw_sym != "XAUUSD":
            err_msg = f"Strict XAUUSD policy rejected non-gold instrument: {raw_sym}"
            logger.error(err_msg)
            return reject(err_msg)

        if signal_data.get("success") is not True or signal_data.get("status") != "VALIDATED":
            return reject("XAUUSD signal must come from the validated signal engine.")
        if not signal_id:
            return reject("Persisted signal ID is required before Telegram delivery.")
        from taikry.database.models import XAUUSDTelegramSignalModel
        db = SessionLocal()
        persisted_state: Dict[str, Any] = {}
        try:
            persisted_signal = db.query(XAUUSDTelegramSignalModel).filter(
                XAUUSDTelegramSignalModel.signal_id == signal_id
            ).first()
            if persisted_signal is not None:
                persisted_state = {
                    "delivery_status": persisted_signal.telegram_delivery_status,
                    "signal_status": persisted_signal.signal_status,
                    "telegram_message_id": persisted_signal.telegram_message_id,
                    "idempotency_key": str(persisted_signal.idempotency_key or "").strip(),
                    "expires_at": persisted_signal.expires_at,
                }
        finally:
            db.close()
        if not persisted_state:
            return reject("XAUUSD signal is not persisted; Telegram delivery was blocked.")
        if persisted_state["delivery_status"] == "SENT":
            if analysis_run_id:
                self.finish_analysis_run(
                    analysis_run_id,
                    "COMPLETED",
                    f"✅ <b>This XAUUSD signal was already delivered.</b> No duplicate was sent.\nMessage ID: <code>{html.escape(str(persisted_state['telegram_message_id'] or 'N/A'))}</code>",
                    self._agent_status_snapshot(signal_data),
                    signal_id,
                )
            return True, persisted_state["telegram_message_id"], "ALREADY_SENT"
        if persisted_state["delivery_status"] == "DELIVERY_UNKNOWN":
            return reject("Previous XAUUSD delivery outcome is uncertain; automatic resend suppressed.")
        if persisted_state["delivery_status"] == "SENDING":
            return reject("XAUUSD signal delivery is already in progress.")
        if persisted_state["signal_status"] != "VALIDATED":
            return reject(f"XAUUSD signal is no longer dispatchable ({persisted_state['signal_status']}).")
        expires_at = persisted_state.get("expires_at")
        if expires_at:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            if expires_at <= now_utc:
                return reject("XAUUSD setup has expired; the engine must create and validate a fresh signal.")
        source_idempotency_key = persisted_state["idempotency_key"]
        provided_idempotency_key = str(signal_data.get("idempotency_key") or "").strip()
        if not source_idempotency_key or (provided_idempotency_key and provided_idempotency_key != source_idempotency_key):
            return reject("XAUUSD signal idempotency key does not match the persisted record.")
        direction = str(signal_data.get("direction") or "").upper()
        if direction not in ("BUY", "SELL", "LONG", "SHORT"):
            return reject("Signal has no valid direction.")
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
            return reject("Signal is missing required entry, stop, target, or score data.")
        levels = [entry, sl, tp1, tp2, tp3, score]
        if not all(math.isfinite(value) for value in levels) or min(levels[:5]) <= 0 or not 80 <= score <= 95:
            return reject("Signal contains invalid price levels or score.")
        if (action_name == "BUY" and not sl < entry < tp1 < tp2 < tp3) or (action_name == "SELL" and not sl > entry > tp1 > tp2 > tp3):
            return reject("Signal price levels do not match the trade direction.")
        try:
            entry_low = float(signal_data.get("entry_zone_low")) if signal_data.get("entry_zone_low") is not None else None
            entry_high = float(signal_data.get("entry_zone_high")) if signal_data.get("entry_zone_high") is not None else None
        except (TypeError, ValueError):
            entry_low = entry_high = None
        entry_str = f"{entry_low:.2f} — {entry_high:.2f}" if (entry_low is not None and entry_high is not None and entry_low <= entry_high) else f"{entry:.2f}"
        risk_distance = abs(entry - sl)
        rr1 = abs(tp1 - entry) / risk_distance
        rr2 = abs(tp2 - entry) / risk_distance
        rr3 = abs(tp3 - entry) / risk_distance
        if not all(math.isfinite(value) for value in (rr1, rr2, rr3)) or rr1 < MIN_RISK_REWARD_RATIO:
            return reject(f"Signal reward/risk is below the required 1:{MIN_RISK_REWARD_RATIO:.2f} minimum.")
        timeframes = html.escape(", ".join(map(str, signal_data.get("timeframes_analyzed") or ["N/A"])))
        evidence = signal_data.get("supporting_evidence", [])
        evidence_text = "\n".join([f"• {html.escape(str(ev))}" for ev in evidence[:4]]) if evidence else "• No supporting evidence was attached."
        agent_summary = self._format_agent_execution_summary(signal_data)
        agent_block = f"\n{agent_summary}" if agent_summary else ""
        expires_at = html.escape(str(signal_data.get("expires_at") or "N/A"))
        source = html.escape(str(signal_data.get("price_source") or signal_data.get("broker") or "N/A"))
        quote_timestamp = html.escape(str(signal_data.get("quote_timestamp_utc") or "N/A"))
        invalidation_en = html.escape(str(signal_data.get("invalidation_conditions_en") or "N/A"))
        invalidation_kh = html.escape(str(signal_data.get("invalidation_conditions_kh") or "N/A"))
        try:
            bid_ask = f"Bid {float(signal_data['bid_price']):.2f} · Ask {float(signal_data['ask_price']):.2f}"
        except (KeyError, TypeError, ValueError):
            bid_ask = "Bid/Ask N/A"
        spread_text = html.escape(str(signal_data.get("spread_points") if signal_data.get("spread_points") is not None else "N/A"))
        safe_signal_id = html.escape(signal_id)

        action_khmer = "ទិញឡើង (BUY)" if action_name == "BUY" else "លក់ចុះ (SELL)"
        text = f"""⚡ <b>ZYROX AI — Read the Market. Own Your Edge.</b>
🇰🇭 <b>សញ្ញាជួញដូរមាសស្វ័យប្រវត្ត (XAUUSD Signal)</b>
━━━━━━━━━━━━━━━━━━━━
📌 <b>Signal ID:</b> <code>{safe_signal_id}</code>
📊 <b>Asset:</b> XAUUSD (Gold / US Dollar)
🎯 <b>Direction / ទិសដៅ:</b> <b>{icon} {action_name} · {action_khmer}</b>
⏱ <b>Timeframes:</b> {timeframes}

💰 <b>Entry Zone (ចំណុចចូល):</b> <code>{entry_str}</code>
🛑 <b>Stop Loss / SL (កាត់ខាត):</b> <code>{sl:.2f}</code>
✅ <b>TP1 (គោលដៅទី១):</b> <code>{tp1:.2f}</code> (R:R 1:{rr1:.2f})
✅ <b>TP2 (គោលដៅទី២):</b> <code>{tp2:.2f}</code> (R:R 1:{rr2:.2f})
✅ <b>TP3 (គោលដៅទី៣):</b> <code>{tp3:.2f}</code> (R:R 1:{rr3:.2f})

🧠 <b>Setup Score / ពិន្ទុវិភាគ:</b> <b>{score}/100</b>
<i>(Institutional setup score, not a guaranteed win rate)</i>
🧭 <b>Trade style:</b> {html.escape(str(signal_data.get("trade_style") or "INTRADAY").upper())} · <b>Execution mode:</b> {html.escape(str(signal_data.get("execution_mode") or "SHADOW_PAPER"))}
🔎 <b>Key Technical Confluence (ភស្តុតាងបច្ចេកទេស):</b>
{evidence_text}
{agent_block}
📡 <b>DATA SOURCE:</b> {source} · {bid_ask} · Spread {spread_text} points
🕒 <b>UPDATED:</b> {quote_timestamp} UTC
⚠️ <b>INVALIDATION:</b> {invalidation_en}
🇰🇭 <b>លក្ខខណ្ឌលុបសញ្ញា:</b> {invalidation_kh}
⌛ <b>Valid Until:</b> {expires_at}

⚠️ <i>Check the current data and your configured account risk before acting. Signal levels can become stale; no profits are guaranteed.</i>
━━━━━━━━━━━━━━━━━━━━
🤖 <i>ZYROX AI Signal Monitor</i>"""

        buttons = self.build_signal_keyboard("XAUUSD")
        target_chat = str(chat_id or self.default_chat_id or "")
        self._update_db_signal_delivery(signal_id, "SENDING", None, None, target_chat)
        notification_fingerprint = hashlib.sha256(
            f"XAUUSD|{source_idempotency_key}|{target_chat}".encode("utf-8")
        ).hexdigest()
        ok, message_id, error, delivery_state = self._dispatch_persistent_message(
            text,
            idempotency_key=f"xauusd:{notification_fingerprint}",
            notification_type="XAUUSD_SIGNAL",
            signal_id=signal_id,
            event_state="APPROVED",
            chat_id=target_chat,
            reply_markup=buttons,
            payload_summary={"symbol": "XAUUSD", "direction": action_name, "source_idempotency_key": source_idempotency_key},
            analysis_run_id=analysis_run_id,
            analysis_agent_statuses=self._agent_status_snapshot(signal_data),
        )
        model_status = {
            "SENT": "SENT",
            "UNCERTAIN": "DELIVERY_UNKNOWN",
            "RETRY_PENDING": "FAILED",
            "FAILED": "FAILED",
        }.get(delivery_state, "SENDING")
        self._update_db_signal_delivery(signal_id, model_status, message_id, error, target_chat)
        if analysis_run_id and not ok:
            self.finish_analysis_run(
                analysis_run_id,
                "DELIVERY_UNCERTAIN" if delivery_state == "UNCERTAIN" else "FAILED",
                f"⚠️ <b>XAUUSD signal was not confirmed as delivered.</b> {html.escape(str(error or delivery_state))}\n\nNo automatic resend was attempted.",
                self._agent_status_snapshot(signal_data),
                signal_id,
            )
        elif analysis_run_id and ok:
            run = self._get_analysis_run(analysis_run_id)
            if run and run.get("status") == "RUNNING":
                self.finish_analysis_run(
                    analysis_run_id,
                    "COMPLETED",
                    f"✅ <b>This XAUUSD setup was already delivered.</b> No duplicate signal was sent.\nMessage ID: <code>{html.escape(str(message_id or 'N/A'))}</code>",
                    self._agent_status_snapshot(signal_data),
                    signal_id,
                )
        if ok and chat_id is None:
            self._fanout_plan_signal(
                text,
                source_key=source_idempotency_key,
                notification_type="XAUUSD_SIGNAL",
                signal_id=signal_id,
                symbol="XAUUSD",
                direction=action_name,
                timeframe=str(signal_data.get("timeframe") or "M15"),
                reply_markup=buttons,
                exclude_chat_id=target_chat,
            )
        return ok, message_id, error

    def send_xauusd_daily_report(self, report_data: Dict[str, Any], chat_id: Optional[str] = None, force: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Dispatches verified daily XAUUSD performance report to Telegram with idempotency check.
        """
        date_str = report_data.get("report_date") or report_data.get("cambodia_date", "")
        if not self.enabled:
            return False, None, "Telegram notifications are disabled"
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
            return False, None, self._redact_secret(f"Telegram API error: {r.text[:100]}")
        except Exception as e:
            safe_err = self._redact_secret(str(e))
            return False, None, safe_err

    def _update_db_signal_delivery(
        self,
        signal_id: str,
        delivery_status: str,
        msg_id: Optional[str],
        err: Optional[str],
        chat_id: Optional[str] = None,
    ):
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
                if chat_id:
                    sig.telegram_chat_id = str(chat_id)
                sig.telegram_error = self._redact_secret(err) if err else None
                db.commit()
        except Exception as e:
            logger.warning("Failed to update signal delivery status: %s", self._redact_secret(str(e)))
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
        if not self.enabled:
            return False, None, "TELEGRAM_NOTIFICATIONS_DISABLED"

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
            elif ev.delivery_status == EventDeliveryStatus.SUPPRESSED.value:
                return False, None, "PRIMARY_SIGNAL_MESSAGE_HANDLES_CREATION"

            # The consolidated approved signal message is the creation notice;
            # don't send an additional standalone SIGNAL_CREATED notification.
            if ev.event_type == "SIGNAL_CREATED":
                ev.delivery_status = EventDeliveryStatus.SUPPRESSED.value
                ev.telegram_error = "Suppressed: the consolidated signal message already reports creation."
                ev.updated_at = datetime.datetime.now(datetime.timezone.utc)
                db.commit()
                return False, None, "PRIMARY_SIGNAL_MESSAGE_HANDLES_CREATION"

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
            return False, None, self._redact_secret(f"Database error during claim: {e}")
        finally:
            db.close()

        # Format message
        sym = html.escape(str(event_dict.get("symbol", "XAUUSD")))
        sig_id = html.escape(str(event_dict.get("signal_id", "SIG-UNKNOWN")))
        ev_type = html.escape(str(event_dict.get("event_type", "EVENT")))
        direction = html.escape(str(event_dict.get("direction", "NEUTRAL")))
        price = event_dict.get("price", 0.0)
        tf = html.escape(str(event_dict.get("timeframe", "M15")))
        trig = html.escape(str(event_dict.get("trigger_cause", "")))
        r_en = html.escape(str(event_dict.get("reason_en"))) if event_dict.get("reason_en") else None
        r_kh = html.escape(str(event_dict.get("reason_kh"))) if event_dict.get("reason_kh") else None
        entry_p = event_dict.get("entry_price")
        sl_p = event_dict.get("stop_loss")
        tp1_p = event_dict.get("take_profit_1")
        tp2_p = event_dict.get("take_profit_2")
        tp3_p = event_dict.get("take_profit_3")
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
            tp3_str = f" | TP3: <code>{tp3_p:.2f}</code>" if tp3_p else ""
            msg += f"📊 <b>Levels:</b> Entry: <code>{entry_p:.2f}</code> | SL: <code>{sl_p:.2f}</code> | TP1: <code>{tp1_p:.2f}</code>{tp2_str}{tp3_str}\n"

        reached = {
            "TP1_HIT": "✓ TP1",
            "TP2_HIT": "✓ TP1 · ✓ TP2",
            "TP3_HIT": "✓ TP1 · ✓ TP2 · ✓ TP3",
        }.get(ev_type)
        if reached:
            msg += f"💎 <b>Targets reached:</b> {reached}\n"
        elif ev_type in {"SL_HIT", "SIGNAL_CLOSED", "SIGNAL_CANCELLED", "SIGNAL_EXPIRED"}:
            msg += f"🔒 <b>Signal status:</b> {html.escape(ev_type)}\n"

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
                edit_ok, edit_error, edit_state = self.edit_message_text_detailed(msg, target_chat, int(orig_msg_id))
                if edit_ok:
                    self._update_event_delivery(ev_id, EventDeliveryStatus.SENT.value, str(orig_msg_id), None)
                    if chat_id is None:
                        self._fanout_plan_lifecycle_event(event_dict, msg, target_chat)
                    return True, str(orig_msg_id), None
                if edit_state == "UNCERTAIN":
                    error = edit_error or "Telegram message edit outcome uncertain; replacement suppressed."
                    self._update_event_delivery(ev_id, EventDeliveryStatus.UNCERTAIN_TIMEOUT.value, None, error)
                    self._audit("telegram", "lifecycle_event", {"signal_id": sig_id, "event_type": ev_type}, "UNCERTAIN_TIMEOUT", 0, error)
                    return False, None, error
            except Exception as exc:
                error = self._redact_secret(str(exc))
                self._update_event_delivery(ev_id, EventDeliveryStatus.UNCERTAIN_TIMEOUT.value, None, error)
                return False, None, error

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        body = {
            "chat_id": target_chat,
            "text": msg,
            "parse_mode": "HTML"
        }

        # One request per claim. A timeout/5xx can follow an accepted message,
        # so keep the event uncertain instead of risking a duplicate send.
        try:
            response = requests.post(url, json=body, timeout=8)
            try:
                response_data = response.json()
            except Exception:
                response_data = {}
            if response.status_code == 200 and response_data.get("ok"):
                sent_msg_id = str(response_data.get("result", {}).get("message_id") or "") or None
                if not sent_msg_id:
                    raise ValueError("Telegram accepted lifecycle notification without returning a message ID")
                self._update_event_delivery(ev_id, EventDeliveryStatus.SENT.value, sent_msg_id, None, sig_id)
                self._audit("telegram", "lifecycle_event", {"signal_id": sig_id, "event_type": ev_type}, "SENT", 200, None)
                if chat_id is None:
                    self._fanout_plan_lifecycle_event(event_dict, msg, target_chat)
                return True, sent_msg_id, None

            description = self._redact_secret(
                str(response_data.get("description") or f"Telegram API returned HTTP {response.status_code}")
            )
            if response.status_code >= 500 or not response_data:
                status = EventDeliveryStatus.UNCERTAIN_TIMEOUT.value
                error = f"Telegram delivery outcome is uncertain: {description}"
            else:
                status = EventDeliveryStatus.FAILED.value
                error = description
            self._update_event_delivery(ev_id, status, None, error)
            self._audit("telegram", "lifecycle_event", {"signal_id": sig_id, "event_type": ev_type}, status, response.status_code, error)
            return False, None, error
        except requests.exceptions.RequestException as exc:
            # A network exception can happen after Telegram accepted the request.
            error = f"Telegram network outcome is uncertain: {self._redact_secret(str(exc))}"
            logger.warning("Event %s: %s", idempotency_key, error)
            self._update_event_delivery(ev_id, EventDeliveryStatus.UNCERTAIN_TIMEOUT.value, None, error)
            self._audit("telegram", "lifecycle_event", {"signal_id": sig_id, "event_type": ev_type}, "UNCERTAIN_TIMEOUT", 0, error)
            return False, None, error
        except Exception as exc:
            # The request was already attempted; malformed/unreadable responses
            # cannot safely be treated as proof of non-delivery.
            error = f"Telegram delivery outcome is uncertain: {self._redact_secret(str(exc))}"
            self._update_event_delivery(ev_id, EventDeliveryStatus.UNCERTAIN_TIMEOUT.value, None, error)
            self._audit("telegram", "lifecycle_event", {"signal_id": sig_id, "event_type": ev_type}, "UNCERTAIN_TIMEOUT", 0, error)
            return False, None, error

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
            logger.warning("Failed to update lifecycle event delivery status: %s", self._redact_secret(str(e)))
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
