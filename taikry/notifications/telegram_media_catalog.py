"""Register the checked-in ZYROX media catalog or send one chosen asset."""
import argparse
import logging

from taikry.notifications.telegram_service import telegram_service

MEDIA_CATALOG = (
    ("ZYROX_AI_SCANNING", "ZYROX_AI_SCANNING.mp4", "animation"),
    ("MARKET_SCANNING", "MARKET_SCANNING.webp", "sticker"),
    ("AI_ANALYZING", "AI_ANALYZING.webp", "sticker"),
    ("DATA_VERIFIED", "DATA_VERIFIED.webp", "sticker"),
    ("RISK_CHECK", "RISK_CHECK.webp", "sticker"),
    ("BUY_SIGNAL", "BUY_SIGNAL.webp", "sticker"),
    ("SELL_SIGNAL", "SELL_SIGNAL.webp", "sticker"),
    ("SIGNAL_APPROVED", "SIGNAL_APPROVED.webp", "sticker"),
    ("TP1_HIT", "TP1_HIT.webp", "sticker"),
    ("TP2_HIT", "TP2_HIT.webp", "sticker"),
    ("TP3_HIT", "TP3_HIT.webp", "sticker"),
    ("BREAKEVEN", "BREAKEVEN.webp", "sticker"),
    ("STOP_LOSS", "STOP_LOSS.webp", "sticker"),
    ("NEWS_ALERT", "NEWS_ALERT.webp", "sticker"),
    ("SIGNAL_INVALIDATED", "SIGNAL_INVALIDATED.webp", "sticker"),
    ("SIGNAL_CLOSED", "SIGNAL_CLOSED.webp", "sticker"),
)


def register_catalog() -> dict[str, str]:
    results = {}
    for asset_name, source_file, asset_type in MEDIA_CATALOG:
        success, asset_id, error = telegram_service.register_telegram_media_asset(
            asset_name, source_file, asset_type, version="1"
        )
        results[asset_name] = asset_id if success else f"ERROR: {error}"
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", metavar="ASSET_ID", help="send exactly one registered asset to the configured Telegram chat")
    parser.add_argument("--chat-id", help="override the configured Telegram chat for the one --send asset")
    args = parser.parse_args()

    results = register_catalog()
    for name, result in results.items():
        print(f"{name}: {result}")

    if args.send:
        if args.send not in {value for value in results.values() if not value.startswith("ERROR:")}:
            print("Send blocked: select a registered asset ID from the catalog output.")
            return 2
        success, message_id, error = telegram_service.send_telegram_media_asset(args.send, chat_id=args.chat_id)
        if not success:
            logging.error("Asset send failed: %s", error)
            return 1
        print(f"Delivered one asset. Telegram message ID: {message_id or 'not returned'}")
    return 0 if all(not value.startswith("ERROR:") for value in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
