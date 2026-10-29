const url = process.env.MAKE_WEBHOOK_URL || '';
if (!url) {
  console.error('[ERROR] MAKE_WEBHOOK_URL environment variable is required.');
  process.exit(1);
}

const payload = {
  symbol: 'XAUUSD',
  timeframe: 'M5',
  action: 'analyze',
  test: true
};
if (process.env.TELEGRAM_CHAT_ID) {
  payload.chat_id = process.env.TELEGRAM_CHAT_ID;
}

async function sendWebhook() {
  console.log('Sending POST to configured Make webhook...');
  console.log('Payload:', JSON.stringify(payload, null, 2));

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    const text = await res.text();
    console.log(`Status: ${res.status}`);
    console.log(`Response: ${text}`);
  } catch (err) {
    console.error('Error:', err);
  }
}

sendWebhook();
