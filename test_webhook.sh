#!/usr/bin/env bash

if [ -z "$MAKE_WEBHOOK_URL" ]; then
  echo "[ERROR] MAKE_WEBHOOK_URL environment variable is required."
  exit 1
fi

curl --location --request POST "$MAKE_WEBHOOK_URL" \
--header 'Content-Type: application/json' \
--data-raw '{
  "symbol": "XAUUSD",
  "timeframe": "M5",
  "action": "analyze",
  "test": "true"
}'
