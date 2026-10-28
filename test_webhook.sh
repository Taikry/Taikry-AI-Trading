#!/usr/bin/env bash

curl --location --request POST 'https://hook.us2.make.com/uu21klu4rg3s2l7u2644xi9toeburwhd' \
--header 'Content-Type: application/json' \
--data-raw '{
  "symbol": "XAUUSD",
  "timeframe": "M5",
  "action": "analyze",
  "test": "true"
}'
