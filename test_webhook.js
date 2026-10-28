const url = 'https://hook.us2.make.com/uu21klu4rg3s2l7u2644xi9toeburwhd';

const payload = {
  symbol: 'XAUUSD',
  timeframe: 'M5',
  action: 'analyze',
  test: 'true',
  chat_id: '-1004341134868'
};

async function sendWebhook() {
  console.log(`Sending POST to ${url}...`);
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
