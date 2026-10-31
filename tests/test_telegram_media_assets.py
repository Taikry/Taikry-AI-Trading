"""Telegram media validation and Telegram file_id caching coverage."""
import base64
from unittest.mock import MagicMock, patch

from taikry.database.models import TelegramMediaAsset
from taikry.database.session import SessionLocal
from taikry.notifications.telegram_service import TelegramService


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j2xoAAAAASUVORK5CYII="
)


def _response(payload, status=200):
    response = MagicMock(status_code=status)
    response.json.return_value = payload
    return response


def _delete_asset(asset_id):
    db = SessionLocal()
    try:
        db.query(TelegramMediaAsset).filter(TelegramMediaAsset.asset_id == asset_id).delete()
        db.commit()
    finally:
        db.close()


def test_media_asset_upload_caches_and_reuses_telegram_file_id(tmp_path):
    service = TelegramService()
    service.token = "unit-test-token"
    service.default_chat_id = "-1001234567890"
    source = tmp_path / "scan.png"
    source.write_bytes(PNG_1X1)
    asset_id = "TEST_MEDIA:photo:1"
    _delete_asset(asset_id)

    with patch.object(service, "_telegram_media_root", return_value=str(tmp_path)):
        registered, registered_id, error = service.register_telegram_media_asset(
            "TEST_MEDIA", "scan.png", "photo", version="1"
        )
        assert registered is True
        assert registered_id == asset_id
        assert error is None

        with patch("requests.post", side_effect=[
            _response({"ok": True, "result": {"message_id": 101, "photo": [{"file_id": "PHOTO-FILE-ID"}]}}),
            _response({"ok": True, "result": {"message_id": 102, "photo": [{"file_id": "PHOTO-FILE-ID"}]}}),
        ]) as post:
            assert service.send_telegram_media_asset(asset_id)[0] is True
            assert service.send_telegram_media_asset(asset_id)[0] is True
            assert post.call_count == 2
            assert "files" in post.call_args_list[0].kwargs
            assert post.call_args_list[1].kwargs["json"]["photo"] == "PHOTO-FILE-ID"

    db = SessionLocal()
    try:
        asset = db.query(TelegramMediaAsset).filter(TelegramMediaAsset.asset_id == asset_id).one()
        assert asset.telegram_file_id == "PHOTO-FILE-ID"
        assert len(asset.checksum) == 64
    finally:
        db.close()
        _delete_asset(asset_id)


def test_media_asset_registration_rejects_svg_and_path_traversal(tmp_path):
    service = TelegramService()
    svg = tmp_path / "not-a-telegram-format.svg"
    svg.write_text("<svg/>", encoding="utf-8")
    root = tmp_path / "media"
    root.mkdir()

    with patch.object(service, "_telegram_media_root", return_value=str(root)):
        ok_svg, _, err_svg = service.register_telegram_media_asset(
            "SVG_ASSET", str(svg), "sticker"
        )
        assert ok_svg is False
        assert "unsupported" in err_svg.lower()

        outside = tmp_path / "outside.png"
        outside.write_bytes(PNG_1X1)
        ok_path, _, err_path = service.register_telegram_media_asset(
            "PATH_ASSET", str(outside), "photo"
        )
        assert ok_path is False
        assert "inside" in err_path.lower()


def test_media_send_failure_does_not_cache_a_file_id(tmp_path):
    service = TelegramService()
    service.token = "unit-test-token"
    service.default_chat_id = "-1001234567890"
    source = tmp_path / "failure.png"
    source.write_bytes(PNG_1X1)
    asset_id = "FAILED_MEDIA:photo:1"
    _delete_asset(asset_id)

    with patch.object(service, "_telegram_media_root", return_value=str(tmp_path)):
        assert service.register_telegram_media_asset("FAILED_MEDIA", "failure.png", "photo")[0] is True
        with patch("requests.post", return_value=_response({"ok": False, "description": "Bad Request: chat not found"}, 400)):
            success, message_id, error = service.send_telegram_media_asset(asset_id)
        assert success is False
        assert message_id is None
        assert "chat not found" in error

    db = SessionLocal()
    try:
        asset = db.query(TelegramMediaAsset).filter(TelegramMediaAsset.asset_id == asset_id).one()
        assert asset.telegram_file_id is None
    finally:
        db.close()
        _delete_asset(asset_id)


def test_telegram_enabled_flag_suppresses_all_message_delivery():
    service = TelegramService()
    service.enabled = False
    service.token = "unit-test-token"
    service.default_chat_id = "-1001234567890"
    with patch("requests.post") as post:
        assert service.is_configured() is False
        assert service.send_text("Should not send")[0] is False
        assert service.send_message("Should not send") is False
        assert service.begin_analysis_run("EURUSD") is None
        post.assert_not_called()
