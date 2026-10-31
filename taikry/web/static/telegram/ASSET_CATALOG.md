# ZYROX AI Telegram media catalog

These are original near-black/emerald ZYROX visual assets, designed as compact Telegram-ready square stickers plus one lightweight 3-second loading animation.

| Asset | File | Telegram type |
|---|---|---|
| ZYROX_AI_SCANNING | `ZYROX_AI_SCANNING.mp4` | Animation |
| MARKET_SCANNING | `MARKET_SCANNING.webp` | Static sticker |
| AI_ANALYZING | `AI_ANALYZING.webp` | Static sticker |
| DATA_VERIFIED | `DATA_VERIFIED.webp` | Static sticker |
| RISK_CHECK | `RISK_CHECK.webp` | Static sticker |
| BUY_SIGNAL | `BUY_SIGNAL.webp` | Static sticker |
| SELL_SIGNAL | `SELL_SIGNAL.webp` | Static sticker |
| SIGNAL_APPROVED | `SIGNAL_APPROVED.webp` | Static sticker |
| TP1_HIT | `TP1_HIT.webp` | Static sticker |
| TP2_HIT | `TP2_HIT.webp` | Static sticker |
| TP3_HIT | `TP3_HIT.webp` | Static sticker |
| BREAKEVEN | `BREAKEVEN.webp` | Static sticker |
| STOP_LOSS | `STOP_LOSS.webp` | Static sticker |
| NEWS_ALERT | `NEWS_ALERT.webp` | Static sticker |
| SIGNAL_INVALIDATED | `SIGNAL_INVALIDATED.webp` | Static sticker |
| SIGNAL_CLOSED | `SIGNAL_CLOSED.webp` | Static sticker |

All image assets are 512×512 WEBP. The scanning loop is 512×512 H.264 MP4, 3 seconds, dark background, subtle emerald scanner, and no fake progress percentage.

## Register and send

Register/refresh checksums and database rows without posting into a chat:

```powershell
python -m taikry.notifications.telegram_media_catalog
```

To send one chosen asset to the configured Telegram chat (an explicit send action):

```powershell
python -m taikry.notifications.telegram_media_catalog --send BUY_SIGNAL:sticker:1
```

`telegram_media_assets` stores the checksum and Telegram `file_id`. The media service reuses the cached file ID; when Telegram explicitly rejects that ID, it clears the stale cache and uploads the checked source once. Network timeouts are reported as uncertain and are not retried blindly.

The animation is optional and is not sent once per agent. Keep analysis progress as one editable text message; use the media sender only for an explicit status announcement or when integrating it as the single progress message.
