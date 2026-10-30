# ABA PayWay eCommerce Checkout

The adapter supports one-time sandbox and production checkout. It keeps the
provider API key and merchant settings in local environment variables or
Render-managed secrets, verifies callbacks, and confirms payment through
Check Transaction-2 before granting an entitlement.

The schema migration is additive and idempotent. Its downgrade refuses to drop
payment tables while they contain invoice, transaction, or callback records.

## Verified public API facts

- Purchase uses `POST /api/payment-gateway/v1/payments/purchase` with
  `multipart/form-data`. The sandbox host is
  `https://checkout-sandbox.payway.com.kh`; the production host is
  `https://checkout.payway.com.kh`.
- Purchase signing uses HMAC-SHA512 with the API key and the ordered fields
  shown in ABA's Purchase reference. `return_url` is a Base64-encoded HTTPS
  callback endpoint; the endpoint receives JSON by POST. `continue_success_url`
  is the browser's success redirect. The request sets `payment_gate=0` and
  `view_type=hosted_view` to select the eCommerce hosted checkout when the
  merchant profile also has QR API enabled; those fields are not part of the
  Purchase HMAC sequence.
- The Purchase response is hosted checkout HTML. The provider's overview says
  the merchant must verify payment status with Check Transaction.
- Check Transaction uses
  `POST /api/payment-gateway/v1/payments/check-transaction-2` with a JSON body
  and returns payment data nested under `data`. The status request signs
  `req_time + merchant_id + tran_id`. It only checks transactions created
  within seven days.
- The callback is a JSON POST and carries `X-PayWay-Hmac-Sha512`. The published
  algorithm sorts response keys ascending, concatenates their values, computes
  raw HMAC-SHA512 with the API key, and Base64-encodes the result.

See ABA's [eCommerce Checkout guide](https://developer.payway.com.kh/folder-3158159),
[Purchase reference](https://developer.payway.com.kh/purchase-14530820e0), and
[Check Transaction reference](https://developer.payway.com.kh/check-transaction-14530826e0).
The developer portal also requires the callback and checkout source domains or
IP to be whitelisted by ABA. Confirm these settings with the Integration Team
before expecting a sandbox checkout to complete.

## Sandbox smoke check

On 2026-10-30, the configured sandbox credentials passed a Check Transaction-2
request (a synthetic unknown reference returned the expected not-found result).
A $0.01 Purchase returned a redirect into hosted checkout after setting
`payment_gate=0`; Check Transaction-2 then reported `PENDING` with the expected
amount and currency. No card details were sent and no payment or entitlement
was completed. This confirms request signing and checkout routing, not a full
paid checkout or callback delivery.

## Environment

Copy the placeholders from `.env.example`. `render.yaml` declares the sandbox
endpoints and marks merchant credentials, the RSA key, and callback/return URLs
as dashboard-managed values (`sync: false`). Configure replacement values in
local `.env` or Render's environment settings. Never put real credentials in
`.env.example`, `render.yaml`, or source code.
Keep `ABA_PAYWAY_ENV=sandbox` during integration. Do not store card numbers,
CVV, tokens, or raw provider secrets in the database or logs. Use sandbox
credentials only for local and staging tests; do not change production
credentials without a separate deployment approval.
