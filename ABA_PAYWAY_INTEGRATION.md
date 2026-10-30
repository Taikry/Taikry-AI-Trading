# ABA PayWay eCommerce Checkout

The current adapter is deliberately fail-closed. It supports the callback
signature algorithm published in ABA's developer suite, but does not create
checkout requests or query payment status until the merchant-specific request
hash recipes are confirmed.

The schema migration is additive and idempotent. Its downgrade refuses to drop
payment tables while they contain invoice, transaction, or callback records.

## Verified public API facts

- Purchase uses `POST /api/payment-gateway/v1/payments/purchase` with
  `multipart/form-data`. The sandbox host is
  `https://checkout-sandbox.payway.com.kh`; the production host is
  `https://checkout.payway.com.kh`.
- The Purchase response is hosted checkout HTML. The provider's overview says
  the merchant must verify payment status with Check Transaction.
- Check Transaction uses
  `POST /api/payment-gateway/v1/payments/check-transaction-2` and returns
  `payment_status_code`, amount, currency, and status. It only checks
  transactions created within seven days.
- The callback is a JSON POST and carries `X-PayWay-Hmac-Sha512`. The published
  algorithm sorts response keys ascending, concatenates their values, computes
  raw HMAC-SHA512 with the API key, and Base64-encodes the result.

See ABA's [eCommerce Checkout guide](https://developer.payway.com.kh/folder-3158159),
[Purchase reference](https://developer.payway.com.kh/purchase-14530820e0), and
[Check Transaction reference](https://developer.payway.com.kh/check-transaction-14530826e0).
An [older official sandbox integration PDF](https://checkout-sandbox.payway.com.kh/plugins/payway-v2-sandbox.pdf)
also describes a Purchase hash sequence and the legacy Check Transaction API.

## Required before enabling checkout

The current rendered Purchase reference lists submitted fields but does not
expose their exact order in the request hash. The older official PDF supplies a
sequence, but it may predate newer Purchase fields. The current Check
Transaction-2 reference also omits its exact hash recipe, while the older PDF
describes a different legacy endpoint. Do not assume those recipes carry over
or substitute callback signing rules for request signing. Obtain ABA's
merchant-specific integration guide confirming:

1. Whether the older official Purchase HMAC-SHA512 sequence applies to the
   current Purchase endpoint, including which optional fields are hashed.
2. The exact ordered fields and value serialization for the current Check
   Transaction-2 HMAC-SHA512 request.
3. How ABA expects `return_url`, `continue_success_url`, and the callback
   notification URL to be configured for this merchant profile.
4. A sandbox Merchant ID and API key. Configure the values locally or in
   Render's secret settings; do not commit or paste secret values into this
   repository. ABA's current setup materials also require an RSA private key
   for request signing and response verification. Store its PEM in the
   `ABA_PAYWAY_RSA_PRIVATE_KEY` secret, with newlines represented as `\n`.
5. Confirmation that the callback and return domains are whitelisted.

Once confirmed, implement and test those two signing recipes in
`app/payments/providers/aba_payway.py`, then complete an actual sandbox payment
and verify it through Check Transaction. Until then `ABAPayWayAdapter.is_ready`
is false and `ensure_ready()` raises instead of simulating success.

## Environment

Copy the placeholders from `.env.example`. `render.yaml` declares the sandbox
endpoints and marks merchant credentials, the RSA key, and callback/return URLs
as dashboard-managed values (`sync: false`). Configure those values in Render's
environment settings after the exposed private key is rotated and ABA confirms
the merchant guide and sandbox access.
Keep `ABA_PAYWAY_ENV=sandbox` during integration. Do not store card numbers,
CVV, tokens, or raw provider secrets in the database or logs. Use sandbox
credentials only for local and staging tests; do not change production
credentials without a separate deployment approval.
