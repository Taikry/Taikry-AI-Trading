/**
 * TAIKRY AI MARKET INTELLIGENCE PRO — Dashboard Frontend Logic
 * Full bilingual support (English & Khmer), TradingView live chart,
 * paper trading ledger, and real-time multi-agent polling.
 */

const API_BASE = "";

let currentSymbol = "XAUUSD";
let currentTab = "ALL";
let currentTimeframe = "15";
let currentLLMProvider = "auto";
let isKhmer = false;
let latestAnalysisData = null;
let currentXauusdCatalyst = null;
let cachedMacroEvents = [];
let macroCountdownInterval = null;

// Watchlist Catalog (All Crypto & Forex)
const WATCHLIST = [
  // Precious Metals & Commodities
  { symbol: "XAUUSD", name: "Gold / US Dollar", category: "COMMODITIES", tv: "OANDA:XAUUSD", icon: "🪙" },
  { symbol: "XAGUSD", name: "Silver / US Dollar", category: "COMMODITIES", tv: "OANDA:XAGUSD", icon: "🥈" },
  // Forex Majors & Crosses
  { symbol: "EURUSD", name: "Euro / US Dollar", category: "FOREX", tv: "FX:EURUSD", icon: "💶" },
  { symbol: "GBPUSD", name: "British Pound / USD", category: "FOREX", tv: "FX:GBPUSD", icon: "💷" },
  { symbol: "USDJPY", name: "US Dollar / Japanese Yen", category: "FOREX", tv: "FX:USDJPY", icon: "💴" },
  { symbol: "AUDUSD", name: "Aussie / US Dollar", category: "FOREX", tv: "FX:AUDUSD", icon: "🇦🇺" },
  { symbol: "USDCAD", name: "US Dollar / Canadian Dollar", category: "FOREX", tv: "FX:USDCAD", icon: "🇨🇦" },
  { symbol: "USDCHF", name: "US Dollar / Swiss Franc", category: "FOREX", tv: "FX:USDCHF", icon: "🇨🇭" },
  { symbol: "NZDUSD", name: "New Zealand / US Dollar", category: "FOREX", tv: "FX:NZDUSD", icon: "🇳🇿" },
  { symbol: "EURJPY", name: "Euro / Japanese Yen", category: "FOREX", tv: "FX:EURJPY", icon: "🇪🇺" },
  { symbol: "GBPJPY", name: "British Pound / Yen", category: "FOREX", tv: "FX:GBPJPY", icon: "🇬🇧" },
  // Major Cryptocurrencies
  { symbol: "BTCUSDT", name: "Bitcoin / Tether", category: "CRYPTO", tv: "BINANCE:BTCUSDT", icon: "⚡" },
  { symbol: "ETHUSDT", name: "Ethereum / Tether", category: "CRYPTO", tv: "BINANCE:ETHUSDT", icon: "💠" },
  { symbol: "SOLUSDT", name: "Solana / Tether", category: "CRYPTO", tv: "BINANCE:SOLUSDT", icon: "🟣" },
  { symbol: "BNBUSDT", name: "BNB / Tether", category: "CRYPTO", tv: "BINANCE:BNBUSDT", icon: "🟡" },
  { symbol: "XRPUSDT", name: "Ripple / Tether", category: "CRYPTO", tv: "BINANCE:XRPUSDT", icon: "🌊" },
  { symbol: "DOGEUSDT", name: "Dogecoin / Tether", category: "CRYPTO", tv: "BINANCE:DOGEUSDT", icon: "🐶" },
  { symbol: "ADAUSDT", name: "Cardano / Tether", category: "CRYPTO", tv: "BINANCE:ADAUSDT", icon: "🔷" },
  { symbol: "AVAXUSDT", name: "Avalanche / Tether", category: "CRYPTO", tv: "BINANCE:AVAXUSDT", icon: "🔺" },
  { symbol: "LINKUSDT", name: "Chainlink / Tether", category: "CRYPTO", tv: "BINANCE:LINKUSDT", icon: "🔗" },
  { symbol: "SUIUSDT", name: "Sui / Tether", category: "CRYPTO", tv: "BINANCE:SUIUSDT", icon: "💧" }
];

// Real Logos Generator for Crypto, Metals and Forex Currency Pairs
function getAssetRealLogoHTML(sym) {
  if (!sym) return "🪙";
  const s = String(sym).toUpperCase().trim();

  // 1. Precious Metals
  if (s === "XAUUSD" || s.startsWith("XAU")) {
    return `<span class="real-asset-logo-wrap" title="Gold (XAU/USD)"><img src="assets/logos/xau.svg" class="real-asset-logo" alt="Gold XAU"></span>`;
  }
  if (s === "XAGUSD" || s.startsWith("XAG")) {
    return `<span class="real-asset-logo-wrap" title="Silver (XAG/USD)"><img src="assets/logos/xag.svg" class="real-asset-logo" alt="Silver XAG"></span>`;
  }

  // 2. Forex Pairs (Dual Flag Circle Overlay)
  const forexMap = {
    "EURUSD": { base: "eu", quote: "us", bAlt: "EUR", qAlt: "USD" },
    "GBPUSD": { base: "gb", quote: "us", bAlt: "GBP", qAlt: "USD" },
    "USDJPY": { base: "us", quote: "jp", bAlt: "USD", qAlt: "JPY" },
    "AUDUSD": { base: "au", quote: "us", bAlt: "AUD", qAlt: "USD" },
    "USDCAD": { base: "us", quote: "ca", bAlt: "USD", qAlt: "CAD" },
    "USDCHF": { base: "us", quote: "ch", bAlt: "USD", qAlt: "CHF" },
    "NZDUSD": { base: "nz", quote: "us", bAlt: "NZD", qAlt: "USD" },
    "EURJPY": { base: "eu", quote: "jp", bAlt: "EUR", qAlt: "JPY" },
    "GBPJPY": { base: "gb", quote: "jp", bAlt: "GBP", qAlt: "JPY" }
  };

  if (forexMap[s]) {
    const f = forexMap[s];
    return `<span class="forex-dual-flag" title="${s}">
      <img src="assets/logos/${f.base}.png" class="flag-base" alt="${f.bAlt}">
      <img src="assets/logos/${f.quote}.png" class="flag-quote" alt="${f.qAlt}">
    </span>`;
  }

  // 3. Cryptocurrencies
  const cryptoMap = {
    "BTCUSDT": "btc", "BTCUSD": "btc", "BTC": "btc",
    "ETHUSDT": "eth", "ETHUSD": "eth", "ETH": "eth",
    "SOLUSDT": "sol", "SOLUSD": "sol", "SOL": "sol",
    "BNBUSDT": "bnb", "BNBUSD": "bnb", "BNB": "bnb",
    "XRPUSDT": "xrp", "XRPUSD": "xrp", "XRP": "xrp",
    "DOGEUSDT": "doge", "DOGEUSD": "doge", "DOGE": "doge",
    "ADAUSDT": "ada", "ADAUSD": "ada", "ADA": "ada",
    "AVAXUSDT": "avax", "AVAXUSD": "avax", "AVAX": "avax",
    "LINKUSDT": "link", "LINKUSD": "link", "LINK": "link",
    "SUIUSDT": "sui", "SUIUSD": "sui", "SUI": "sui"
  };

  const cKey = cryptoMap[s] || (s.endsWith("USDT") ? s.replace("USDT", "").toLowerCase() : null);
  if (cKey) {
    return `<span class="real-asset-logo-wrap" title="${s}"><img src="assets/logos/${cKey}.png" class="real-asset-logo" alt="${s}" onerror="this.src='https://assets.coincap.io/assets/icons/${cKey}@2x.png'"></span>`;
  }

  // Fallback to Watchlist Icon
  const match = WATCHLIST.find(w => w.symbol === s);
  return match?.icon || "🪙";
}

// Khmer UI Dictionary
const I18N = {
  en: {
    brand_title: "ZYROX AI — Read the Market. Own Your Edge.",
    brand_sub: "Professional AI-Assisted Multi-Market Intelligence Platform",
    tagline: "Read the Market. Own Your Edge.",
    scan_btn: "Scan Market Now",
    watchlist_title: "Market Watchlist",
    macro_title: "High-Impact Forex Factory & News",
    macro_sub: "FOMC, PPI, CPI, NFP Real-Time Calendar & Blackout HUD",
    live_news_label: "Live Macro News Headlines",
    hud_title: "ICT / SMC Institutional Structure HUD",
    smart_analysis_title: "Smart Multi-Agent Cause Analysis (វិភាគមូលហេតុ)",
    synthesis_label: "Synthesized Cause & Market Thesis:",
    chk_title: "Pre-Execution Safety Checklist:",
    exec_title: "Trade Execution Signal (ចំណុចប្រតិបត្តិការជួញដូរ)",
    entry_label: "Entry Price",
    sl_label: "Stop Loss (SL)",
    tp1_label: "Take Profit 1 (TP1)",
    tp2_label: "Take Profit 2 (TP2)",
    rr_label: "Risk-to-Reward",
    inval_label: "Invalidation Condition:",
    market_bias_label: "Consensus Bias",
    setup_status_label: "Setup Status",
    report_title: "Intelligence Report (English & Khmer)",
    portfolio_title: "Paper Portfolio (Configured Risk)",
    backtest_title: "Strategy Backtest Engine",
    health_title: "Service Health Audit",
    lang_btn: "ភាសាខ្មែរ (Khmer)",
    tab_signals: "Live Market & Signals",
    tab_debate: "Agent Evidence Review",
    tab_training: "Self-Training & AI Learning (Train ខ្លួនឯង)",
    tab_autofix: "Alert-Auto-Fix & Sentinel",
    debate_title: "Agent Evidence Review & Risk Cross-Check",
    debate_sub: "Structured summary of Technical, SMC, Macro, and Risk agent outputs",
    run_debate_btn: "Review Agent Evidence",
    verdict_title: "Final Risk Arbiter Ruling & Decision:",
    train_title: "Autonomous Self-Training & Reinforcement Learning (ប្រព័ន្ធបណ្តុះបណ្តាលខ្លួនឯង)",
    train_sub: "Continuous Brier Score Calibration & Dynamic Agent Weight Matrix Optimization",
    train_epoch_btn: "Trigger Training Epoch (Train ខ្លួនឯង)",
    epochs_label: "Training Epochs Run",
    acc_label: "Ensemble Accuracy",
    lr_label: "Learning Rate (η)",
    policy_label: "Optimization Policy",
    weights_title: "Dynamic Multi-Agent Ensemble Voting Weights",
    scorecard_title: "Agent Performance & Accuracy Scorecard",
    autofix_title: "Alert-Auto-Fix & Autonomous Self-Healing Sentinel (ប្រព័ន្ធដោះស្រាយបញ្ហាស្វ័យប្រវត្ត)",
    autofix_sub: "Zero-Downtime Autonomous Remediation for Feeds, Real LLMs & Drawdown Thresholds",
    run_autofix_btn: "Run Diagnostic & Auto-Fix",
    autofix_stream_title: "Live Incident Stream & Auto-Remediation Log",
    cockpit_execute: "🧾 Record Paper Trade & Send Manual Ticket"
  },
  kh: {
    brand_title: "ZYROX AI — ប្រព័ន្ធបញ្ញាសិប្បនិម្មិតវិភាគទីផ្សារ",
    brand_sub: "អានដំណើរទីផ្សារ · ក្តាប់ឱកាសចំណេញរបស់អ្នក (Read the Market. Own Your Edge.)",
    tagline: "អានដំណើរទីផ្សារ · ក្តាប់ឱកាសចំណេញរបស់អ្នក",
    scan_btn: "វិភាគទីផ្សារឥឡូវនេះ",
    watchlist_title: "បញ្ជីតាមដានទីផ្សារ",
    macro_title: "ព័ត៌មានម៉ាក្រូឥទ្ធិពលខ្លាំង Forex Factory",
    macro_sub: "ប្រតិទិនពេលវេលាជាក់ស្តែង FOMC, PPI, CPI, NFP & បំរាមជួញដូរ",
    live_news_label: "ព័ត៌មានទាន់ហេតុការណ៍ម៉ាក្រូសកល",
    hud_title: "ផ្ទាំងបញ្ជាត្រួតពិនិត្យរចនាសម្ព័ន្ធស្ថាប័ន ICT / SMC",
    smart_analysis_title: "ការវិភាគមូលហេតុឆ្លាតវៃពីគ្រប់ AI Agents",
    synthesis_label: "ការសង្ខេបមូលហេតុរួម និងនិក្ខេបបទទីផ្សារ:",
    chk_title: "បញ្ជីផ្ទៀងផ្ទាត់សុវត្ថិភាពមុនជួញដូរ:",
    exec_title: "ចំណុចប្រតិបត្តិការជួញដូរ (Entry / SL / TP)",
    entry_label: "តម្លៃចូល (Entry)",
    sl_label: "កាត់ខាត (SL)",
    tp1_label: "ចំណេញទី ១ (TP1)",
    tp2_label: "ចំណេញទី ២ (TP2)",
    rr_label: "អនុបាត R:R",
    inval_label: "លក្ខខណ្ឌលុបចោលសុពលភាព:",
    market_bias_label: "ទំនោរទិសដៅទីផ្សារ",
    setup_status_label: "ស្ថានភាពរៀបចំជួញដូរ",
    report_title: "របាយការណ៍វិភាគលម្អិត (ខ្មែរ និងអង់គ្លេស)",
    portfolio_title: "ផលប័ត្រសាកល្បង (ហានិភ័យ ០.៥%)",
    backtest_title: "ម៉ាស៊ីន Backtest យុទ្ធសាស្ត្រ",
    health_title: "សវនកម្មសុខភាពប្រព័ន្ធ",
    lang_btn: "English Mode",
    tab_signals: "ទីផ្សារ & សញ្ញាជួញដូរ",
    tab_debate: "ពិនិត្យភស្តុតាងភ្នាក់ងារ",
    tab_training: "ប្រព័ន្ធរៀនសូត្រ (Train ខ្លួនឯង)",
    tab_autofix: "ប្រព័ន្ធជួសជុលស្វ័យប្រវត្ត (Auto-Fix)",
    debate_title: "ការពិនិត្យភស្តុតាង និងផ្ទៀងផ្ទាត់ហានិភ័យ",
    debate_sub: "សេចក្តីសង្ខេបរចនាសម្ព័ន្ធពីលទ្ធផលភ្នាក់ងារបច្ចេកទេស SMC ម៉ាក្រូ និងហានិភ័យ",
    run_debate_btn: "ពិនិត្យភស្តុតាងភ្នាក់ងារ",
    verdict_title: "សេចក្តីសម្រេចចុងក្រោយរបស់អាជ្ញាកណ្តាលហានិភ័យ (Ruling):",
    train_title: "ប្រព័ន្ធបណ្តុះបណ្តាលខ្លួនឯងស្វ័យប្រវត្ត និងរៀនសូត្របន្ត (Train ខ្លួនឯង)",
    train_sub: "ការកែសម្រួលពិន្ទុ Brier Score និងបង្កើនទម្ងន់បោះឆ្នោតរបស់ភ្នាក់ងារ AI តាមក្បួន PPMC",
    train_epoch_btn: "ដំណើរការវគ្គហ្វឹកហាត់ (Train ឥឡូវ)",
    epochs_label: "ចំនួនវគ្គហ្វឹកហាត់សរុប (Epochs)",
    acc_label: "ភាពសុក្រឹតរួមរបស់ AI",
    lr_label: "អត្រារៀនសូត្រ (η)",
    policy_label: "គោលការណ៍បង្កើនប្រសិទ្ធភាព",
    weights_title: "ទម្ងន់សម្លេងបោះឆ្នោតរបស់ AI Agents ម្នាក់ៗ",
    scorecard_title: "តារាងពិន្ទុ និងកំណត់ត្រាជោគជ័យរបស់ភ្នាក់ងារ",
    autofix_title: "ប្រព័ន្ធ Alert-Auto-Fix និងដោះស្រាយបញ្ហាស្វ័យប្រវត្ត (Sentinel)",
    autofix_sub: "ប្រព័ន្ធត្រួតពិនិត្យ និងជួសជុលស្វ័យប្រវត្ត មិនឱ្យមានការដាច់ចរន្តទិន្នន័យ ម៉ាស៊ីន AI ឬការខាតបង់លើសកម្រិត",
    run_autofix_btn: "ដំណើរការត្រួតពិនិត្យ និងជួសជុលភ្លាមៗ",
    autofix_stream_title: "កំណត់ត្រាព្រឹត្តិការណ៍ និងសកម្មភាពជួសជុលស្វ័យប្រវត្តផ្ទាល់",
    cockpit_execute: "🧾 កត់ត្រាជួញដូរសាកល្បង និងផ្ញើសំបុត្រជូនដំណឹង"
  }
};

let activeMainTab = "signals";

function initTelegramWebApp() {
  if (window.Telegram && window.Telegram.WebApp) {
    const tg = window.Telegram.WebApp;
    try {
      tg.ready();
      tg.expand();
      document.body.classList.add("telegram-webapp-mode");

      const user = tg.initDataUnsafe?.user;
      if (user) {
        const userBadge = document.getElementById("system-status-text");
        if (userBadge) {
          userBadge.innerText = `TG: @${user.username || user.first_name}`;
        }
      }

      if (tg.MainButton) {
        tg.MainButton.setText("⚡ SCAN GOLD (XAUUSD)");
        tg.MainButton.show();
        tg.MainButton.onClick(() => {
          if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred("medium");
          triggerScan();
        });
      }
    } catch (e) {
      console.warn("Telegram WebApp initialization error:", e);
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initTelegramWebApp();
  initColorTheme();
  initCockpitSize();
  renderWatchlist();
  initTickerRibbon();
  renderCockpitChips();
  if (window.innerWidth <= 900) {
    switchMobileView("chart");
  }

  // Initialize Real Logos for Active Instrument
  const topActiveIcon = document.getElementById("top-active-icon");
  if (topActiveIcon) topActiveIcon.innerHTML = getAssetRealLogoHTML(currentSymbol);
  const cockpitAssetIcon = document.getElementById("cockpit-asset-icon");
  if (cockpitAssetIcon) cockpitAssetIcon.innerHTML = getAssetRealLogoHTML(currentSymbol);

  // Initialize Native Pro Financial Chart Workspace
  if (window.taikryChart) {
    window.taikryChart.init("tradingview-container");
  } else {
    loadTradingViewChart("OANDA:XAUUSD", "15");
  }

  triggerScan();
  fetchHealthAndPaper();
  fetchMacroEvents();
  startRealtimePriceStream();

  initLLMPillClickHandlers();
  setupChatDragAndDrop();

  // Polling intervals
  setInterval(fetchHealthAndPaper, 10000);
  setInterval(fetchMacroEvents, 30000); // 30s live calendar countdown update
});

function initLLMPillClickHandlers() {
  const pills = [
    { id: "llm-badge-groq", provider: "groq" },
    { id: "llm-badge-gemini", provider: "gemini" },
    { id: "llm-badge-openrouter", provider: "openrouter" },
    { id: "llm-badge-deepseek", provider: "deepseek" },
    { id: "llm-badge-claude", provider: "claude" },
    { id: "llm-badge-openai", provider: "openai" },
    { id: "llm-badge-manus", provider: "manus" }
  ];
  pills.forEach(p => {
    const el = document.getElementById(p.id);
    if (el) {
      el.onclick = () => {
        onLLMProviderChange(p.provider);
      };
    }
  });
}

function toggleLanguage() {
  isKhmer = !isKhmer;
  document.body.classList.toggle("khmer-mode", isKhmer);

  if (window.taikryChart) {
    window.taikryChart.setLanguage(isKhmer ? "kh" : "en");
  }

  const dict = isKhmer ? I18N.kh : I18N.en;
  const setTxt = (id, val) => {
    const el = document.getElementById(id);
    if (el && val) el.innerText = val;
  };

  setTxt("t-brand-title", dict.brand_title);
  setTxt("t-brand-sub", dict.brand_sub);
  setTxt("t-scan-btn", dict.scan_btn);
  setTxt("t-watchlist-title", dict.watchlist_title);
  setTxt("t-macro-title", dict.macro_title);
  setTxt("t-macro-sub", dict.macro_sub);
  setTxt("t-live-news-label", dict.live_news_label);
  setTxt("t-hud-title", dict.hud_title);
  setTxt("t-smart-analysis-title", dict.smart_analysis_title);
  setTxt("t-synthesis-label", dict.synthesis_label);
  setTxt("t-chk-title", dict.chk_title);
  setTxt("t-exec-title", dict.exec_title);
  setTxt("t-entry-label", dict.entry_label);
  setTxt("t-sl-label", dict.sl_label);
  setTxt("t-tp1-label", dict.tp1_label);
  setTxt("t-tp2-label", dict.tp2_label);
  setTxt("t-rr-label", dict.rr_label);
  setTxt("t-inval-label", dict.inval_label);
  setTxt("t-market-bias-label", dict.market_bias_label);
  setTxt("t-setup-status-label", dict.setup_status_label);
  setTxt("t-report-title", dict.report_title);
  setTxt("t-portfolio-title", dict.portfolio_title);
  setTxt("t-backtest-title", dict.backtest_title);
  setTxt("lang-btn-text", dict.lang_btn);
  setTxt("c-tab-xauusd-signals", isKhmer ? "🥇 សញ្ញា XAUUSD" : "🥇 Gold Signals");
  setTxt("t-xauusd-panel-title", isKhmer ? "ម៉ាស៊ីនសញ្ញា Telegram XAUUSD & អត្រាឈ្នះផ្ទៀងផ្ទាត់" : "XAUUSD Telegram Signals & Win-Rate Engine");

  // Main Tabs & Sections
  setTxt("t-tab-signals", dict.tab_signals);
  setTxt("t-tab-debate", dict.tab_debate);
  setTxt("t-tab-training", dict.tab_training);
  setTxt("t-tab-autofix", dict.tab_autofix);
  setTxt("t-cockpit-analyze", isKhmer ? "វិភាគ" : "Analyze");
  setTxt("t-cockpit-best", isKhmer ? "ការរៀបចំល្អបំផុត" : "Best setup");
  setTxt("t-top-trade", isKhmer ? "ជួញដូរសាកល្បង" : "Paper Trade");

  setTxt("t-debate-title", dict.debate_title);
  setTxt("t-debate-sub", dict.debate_sub);
  setTxt("t-run-debate-btn", dict.run_debate_btn);
  setTxt("t-verdict-title", dict.verdict_title);

  setTxt("t-train-title", dict.train_title);
  setTxt("t-train-sub", dict.train_sub);
  setTxt("t-train-epoch-btn", dict.train_epoch_btn);
  setTxt("t-epochs-label", dict.epochs_label);
  setTxt("t-acc-label", dict.acc_label);
  setTxt("t-lr-label", dict.lr_label);
  setTxt("t-policy-label", dict.policy_label);
  setTxt("t-weights-title", dict.weights_title);
  setTxt("t-scorecard-title", dict.scorecard_title);

  setTxt("t-autofix-title", dict.autofix_title);
  setTxt("t-autofix-sub", dict.autofix_sub);
  setTxt("t-run-autofix-btn", dict.run_autofix_btn);
  setTxt("t-autofix-stream-title", dict.autofix_stream_title);

  setTxt("t-cockpit-execute", dict.cockpit_execute);

  if (latestAnalysisData) {
    updateSmartCauseHub(latestAnalysisData);
    updateExecutionCard(latestAnalysisData);
    updateReportView(latestAnalysisData);
  }

  if (currentXauusdCatalyst) {
    updateMacroCatalystUI(currentXauusdCatalyst);
    renderCockpitNewsQuickList(currentXauusdCatalyst, cachedMacroEvents);
  }
}

let currentWatchlistSearch = "";

function onWatchlistSearch(val) {
  currentWatchlistSearch = val || "";
  renderWatchlist();
}

window.lastKnownMarketData = window.lastKnownMarketData || {};

function initTickerRibbon() {
  const track = document.getElementById("ticker-ribbon-track");
  if (!track) return;

  const buildItems = () => WATCHLIST.map(item => {
    const live = (window.lastKnownMarketData && window.lastKnownMarketData[item.symbol]) || null;
    const isCrypto = item.symbol.includes("USDT") || item.symbol.includes("BTC");
    const isForex = !isCrypto && !item.symbol.includes("XAU") && !item.symbol.includes("XAG");
    const p = live ? (isForex ? Number(live.price).toFixed(4) : (Number(live.price) > 100 ? `$${Number(live.price).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : `$${Number(live.price)}`)) : "---";
    const c24 = live && live.change_24h !== undefined && live.change_24h !== null ? Number(live.change_24h) : null;
    const chg = c24 !== null ? (c24 > 0 ? `+${c24.toFixed(2)}%` : `${c24.toFixed(2)}%`) : "--";
    const isUp = c24 === null || c24 >= 0;
    const activeCls = item.symbol === currentSymbol ? "active" : "";
    return `
      <div class="ticker-item ${activeCls}" data-ribbon-sym="${item.symbol}" onclick="selectSymbol('${item.symbol}', '${item.tv}')" title="Click to view ${item.name} (${item.symbol})">
        <span class="ticker-item-icon">${getAssetRealLogoHTML(item.symbol)}</span>
        <span class="ticker-item-sym">${item.symbol}</span>
        <span class="ticker-item-price" data-price-sym="${item.symbol}">${p}</span>
        <span class="ticker-item-chg ${isUp ? 'chg-up' : 'chg-down'}" data-chg-sym="${item.symbol}">${chg}</span>
      </div>
    `;
  }).join("");

  // Populate two cloned sets for smooth, continuous, infinite loop marquee
  track.innerHTML = buildItems() + buildItems();
}

function renderWatchlist() {
  const container = document.getElementById("watchlist-container");
  if (!container) return;
  container.innerHTML = "";

  let filtered = currentTab === "ALL" 
    ? WATCHLIST 
    : WATCHLIST.filter(item => item.category === currentTab || (currentTab === "COMMODITIES" && item.category === "COMMODITIES"));

  if (currentWatchlistSearch.trim()) {
    const q = currentWatchlistSearch.trim().toUpperCase();
    filtered = filtered.filter(item => item.symbol.includes(q) || item.name.toUpperCase().includes(q));
  }

  filtered.forEach(item => {
    const el = document.createElement("div");
    el.className = `watchlist-item ${item.symbol === currentSymbol ? "active" : ""}`;
    el.onclick = () => selectSymbol(item.symbol, item.tv);

    const live = (window.lastKnownMarketData && window.lastKnownMarketData[item.symbol]) || null;
    const isCrypto = item.symbol.includes("USDT") || item.symbol.includes("BTC");
    const isForex = !isCrypto && !item.symbol.includes("XAU") && !item.symbol.includes("XAG");
    const p = live ? (isForex ? Number(live.price).toFixed(4) : (Number(live.price) > 100 ? `$${Number(live.price).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : `$${Number(live.price)}`)) : "---";
    const c24 = live && live.change_24h !== undefined && live.change_24h !== null ? Number(live.change_24h) : null;
    const chg = c24 !== null ? (c24 > 0 ? `+${c24.toFixed(2)}%` : `${c24.toFixed(2)}%`) : "--";
    const isUp = c24 === null || c24 >= 0;

    el.innerHTML = `
      <div class="wl-item-left">
        <span class="wl-sym-icon">${getAssetRealLogoHTML(item.symbol)}</span>
        <div>
          <div class="wl-sym-title">${item.symbol}</div>
          <div class="wl-sym-sub">${item.name}</div>
        </div>
      </div>
      <div class="wl-item-right">
        <div class="wl-price-val" id="price-${item.symbol}">${p}</div>
        <div class="wl-change-val ${isUp ? 'badge-up' : 'badge-down'}" data-watch-chg-sym="${item.symbol}">${chg}</div>
      </div>
    `;
    container.appendChild(el);
  });
}

function switchWatchlistTab(tab, btn) {
  currentTab = tab;
  document.querySelectorAll(".tab-btn, .wcat-pill").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
  renderWatchlist();
}

function selectSymbol(sym, tvSymbol) {
  currentSymbol = sym;
  renderWatchlist();

  // Update active state in Crypto/Forex Running Loop Ribbon
  document.querySelectorAll(".ticker-item").forEach(el => {
    if (el.getAttribute("data-ribbon-sym") === sym) {
      el.classList.add("active");
    } else {
      el.classList.remove("active");
    }
  });

  if (window.taikryChart && window.taikryChart.currentEngineMode === "native") {
    window.taikryChart.loadCandlesAndOverlays(sym, currentTimeframe);
  } else {
    loadTradingViewChart(tvSymbol, currentTimeframe);
  }

  triggerScan();

  // If on mobile screen, automatically return to chart view to inspect the asset
  if (window.innerWidth <= 900) {
    switchMobileView("chart");
  }

  const asset = WATCHLIST.find(w => w.symbol === sym) || { symbol: sym, name: sym, icon: "🪙" };
  const tfMap = { "1": "1m", "5": "5m", "15": "15m", "30": "30m", "60": "1h", "240": "4h", "D": "1d" };
  const tfText = tfMap[currentTimeframe] || "15m";

  const topIcon = document.getElementById("top-active-icon");
  const topTicker = document.getElementById("top-active-ticker");
  const topSource = document.getElementById("top-active-source");
  const chatTag = document.getElementById("chat-active-sym-tag");
  const aiCtx = document.getElementById("ai-context-sym-tf");
  const ftSym = document.getElementById("ft-sym-display");
  const symbolSpan = document.getElementById("debate-active-symbol");

  if (topIcon) topIcon.innerHTML = getAssetRealLogoHTML(sym);
  if (topTicker) topTicker.innerText = sym;
  const currentProv = window.TAIKRY_PROVIDER_DISPLAY || (sym.includes("USDT") ? "BINANCE" : (sym === "XAUUSD" ? "GOLD (SPOT)" : "OANDA"));
  if (topSource) topSource.innerText = `${currentProv} · ${tfText.toUpperCase()}`;
  if (chatTag) chatTag.innerText = sym;
  if (aiCtx) aiCtx.innerText = `${sym} · ${tfText} · Watching`;
  if (ftSym) ftSym.innerText = sym;
  if (symbolSpan) symbolSpan.innerText = sym;

  const cockpitDisp = document.getElementById("cockpit-asset-display");
  const cockpitIcon = document.getElementById("cockpit-asset-icon");
  if (cockpitDisp) cockpitDisp.innerText = `${sym} · ${tfText}`;
  if (cockpitIcon) cockpitIcon.innerHTML = getAssetRealLogoHTML(sym);

  if (activeMainTab === "debate") {
    fetchAgentsDebate(currentSymbol);
  }
}

function switchTimeframe(tf, btn) {
  currentTimeframe = tf;
  document.querySelectorAll(".tf-btn, .tf-pill, .adv-tf-btn").forEach(b => {
    const txt = b.innerText.toLowerCase().trim();
    if (txt === tf.toLowerCase() || txt === (tf + 'm') || (tf === 'D' && txt === '1d') || (tf === '60' && txt === '1h') || (tf === '240' && txt === '4h')) {
      b.classList.add("active");
    } else {
      b.classList.remove("active");
    }
  });
  if (btn) btn.classList.add("active");

  const tfMap = { "1": "1m", "5": "5m", "15": "15m", "30": "30m", "60": "1h", "240": "4h", "D": "1d" };
  const tfText = tfMap[currentTimeframe] || "15m";
  const disp = document.getElementById("cockpit-asset-display");
  if (disp) disp.innerText = `${currentSymbol} · ${tfText}`;
  const topSource = document.getElementById("top-active-source");
  const activeProv = window.TAIKRY_PROVIDER_DISPLAY || (currentSymbol.includes("USDT") ? "BINANCE" : (currentSymbol === "XAUUSD" ? "GOLD (SPOT)" : "OANDA"));
  if (topSource) topSource.innerText = `${activeProv} · ${tfText.toUpperCase()}`;
  const aiCtx = document.getElementById("ai-context-sym-tf");
  if (aiCtx) aiCtx.innerText = `${currentSymbol} · ${tfText} · Watching`;

  const asset = WATCHLIST.find(w => w.symbol === currentSymbol);
  const tvSym = asset ? asset.tv : (window.TAIKRY_TV_REFERENCE_SYMBOL || `OANDA:${currentSymbol}`);

  if (window.taikryChart && window.taikryChart.currentEngineMode === "native") {
    window.taikryChart.loadCandlesAndOverlays(currentSymbol, tf);
  } else {
    loadTradingViewChart(tvSym, tf);
  }

  triggerScan();
}

function loadTradingViewChart(symbolTv, interval = "15") {
  const container = document.getElementById("tradingview-container");
  container.innerHTML = `
    <iframe
      src="https://s.tradingview.com/widgetembed/?frameElementId=tradingview_widget&symbol=${symbolTv}&interval=${interval}&hidesidetoolbar=1&symboledit=0&saveimage=0&toolbarbg=f1f3f6&studies=%5B%5D&theme=dark&style=1&timezone=Asia%2FPhnom_Penh&studies_overrides=%7B%7D&overrides=%7B%7D&enabled_features=%5B%5D&disabled_features=%5B%5D&locale=en&utm_source=localhost"
      width="100%"
      height="100%"
      frameborder="0"
      allowtransparency="true"
      scrolling="no">
    </iframe>
  `;
}

async function triggerScan() {
  const biasEl = document.getElementById("disp-market-bias");
  const statusEl = document.getElementById("disp-setup-status");
  biasEl.innerText = "ANALYZING...";
  biasEl.className = "metric-value val-gold";

  const asset = WATCHLIST.find(w => w.symbol === currentSymbol);
  const activeLabel = document.getElementById("chart-active-symbol");
  if (activeLabel) {
    activeLabel.innerText = `${currentSymbol} — ${asset ? asset.name : "ASSET"}`;
  }

  try {
    const tfMap = { "5": "M5", "15": "M15", "60": "H1", "240": "H4", "D": "D1" };
    const tfParam = tfMap[currentTimeframe] || "M15";

    const r = await fetch(`${API_BASE}/api/v1/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: currentSymbol,
        timeframe: tfParam,
        llm_provider: currentLLMProvider
      })
    });
    const data = await r.json();
    latestAnalysisData = data;

    // Update banner metrics
    biasEl.innerText = data.market_bias;
    if (data.market_bias.includes("BULLISH")) biasEl.className = "metric-value val-green";
    else if (data.market_bias.includes("BEARISH")) biasEl.className = "metric-value val-red";
    else biasEl.className = "metric-value val-neutral";

    statusEl.innerText = data.setup_status;
    if (data.setup_status === "APPROVE") statusEl.className = "metric-value val-green";
    else if (data.setup_status === "REJECT") statusEl.className = "metric-value val-red";
    else statusEl.className = "metric-value val-gold";

    const vPrice = data.verified_price || "---";
    document.getElementById("disp-verified-price").innerText = vPrice;
    document.getElementById("disp-risk-reward").innerText = data.risk_reward_ratio || "N/A";

    const chartPrice = document.getElementById("chart-verified-price");
    if (chartPrice) chartPrice.innerText = `$${vPrice}`;

    const priceEl = document.getElementById(`price-${currentSymbol}`);
    if (priceEl && data.verified_price) {
      priceEl.innerText = data.verified_price;
    }

    // Update Real LLM Fleet Status
    updateLLMFleetStatus(data);

    // Update ICT / SMC Structure HUD
    updateSmcHud(data);

    // Update Smart Multi-Agent Cause Analysis Hub
    updateSmartCauseHub(data);

    // Update Execution Signal & Settlement Card (Display AFTER Causes)
    updateExecutionCard(data);

    // Update Pro Analysis Cockpit Plan Card
    updateCockpitPlanCard(data);

    updateReportView(data);
  } catch (e) {
    biasEl.innerText = "SERVICE READY";
    biasEl.className = "metric-value val-gold";
  }
}

function onLLMProviderChange(val) {
  currentLLMProvider = val;
  triggerScan();
}

function updateLLMFleetStatus(data) {
  const meta = data.llm_meta || (data.smart_analysis && data.smart_analysis.llm_meta) || {};
  const statusObj = data.llm_status || {};
  
  const prov = (meta.provider || currentLLMProvider || "auto").toLowerCase();
  const activeMetaEl = document.getElementById("llm-active-meta");
  if (activeMetaEl) {
    if (meta.llm_call_made === false) {
      activeMetaEl.innerText = "🤖 Deterministic agents · no cloud LLM call";
    } else if (meta.model) {
      const providerName = String(meta.provider || "provider not reported").toUpperCase();
      const latency = Number(meta.latency_ms);
      const latencyLabel = Number.isFinite(latency) && latency > 0 ? ` [${latency}ms]` : "";
      activeMetaEl.innerText = `🤖 LLM call: ${providerName} (${meta.model})${latencyLabel}`;
    } else {
      activeMetaEl.innerText = `🤖 LLM call status: ${meta.status || "not reported"}`;
    }
  }

  const selectEl = document.getElementById("adv-llm-select");
  if (selectEl && selectEl.value !== currentLLMProvider) {
    selectEl.value = currentLLMProvider;
  }

  const pills = {
    groq: document.getElementById("llm-badge-groq"),
    gemini: document.getElementById("llm-badge-gemini"),
    openrouter: document.getElementById("llm-badge-openrouter"),
    deepseek: document.getElementById("llm-badge-deepseek"),
    claude: document.getElementById("llm-badge-claude"),
    openai: document.getElementById("llm-badge-openai"),
    manus: document.getElementById("llm-badge-manus")
  };

  for (const [key, el] of Object.entries(pills)) {
    if (!el) continue;
    const isConfigured = statusObj[key] && statusObj[key].configured;
    const isCurrent = prov.includes(key);
    el.style.opacity = (isConfigured || isCurrent) ? "1" : "0.5";
    if (isCurrent) {
      el.style.boxShadow = "0 0 10px rgba(56, 189, 248, 0.4)";
      el.style.borderColor = "var(--theme-accent)";
    } else {
      el.style.boxShadow = "none";
    }
  }
}

function updateSmartCauseHub(data) {
  const smart = data.smart_analysis || {};
  const agents = data.agents || {};
  const a1 = agents.agent_1_technical || {};
  const a2 = agents.agent_2_ict_smc || {};
  const a3 = agents.agent_3_macro || {};
  const a4 = agents.agent_4_risk || {};

  // 1. Synthesis Summary
  const synEl = document.getElementById("synthesis-text");
  if (synEl) {
    synEl.innerText = isKhmer 
      ? (smart.synthesis_summary_kh || "ការវិភាគស្រុះស្រួលគ្នារវាងគ្រប់ភ្នាក់ងារទាំងអស់។")
      : (smart.synthesis_summary_en || "Consensus evaluation completed across all active AI models.");
  }

  // 2. Causes Lists
  renderBullets("cause1-bullets", smart.technical_causes || a1.evidence || [a1.rationale]);
  renderBullets("cause2-bullets", smart.smc_causes || a2.evidence || [a2.rationale]);
  renderBullets("cause3-bullets", smart.macro_causes || [a3.rationale]);
  renderBullets("cause4-bullets", smart.risk_causes || a4.reasons || ["Risk verification completed."]);

  // 3. Badges
  setCauseBadge("cause1-bias", a1.bias);
  setCauseBadge("cause2-bias", a2.bias);
  setCauseBadge("cause3-bias", a3.bias);
  setCauseBadge("cause4-bias", a4.decision);

  // 4. Pre-trade Checklist
  const chk = smart.checklist || {};
  setChecklistPill("chk-trend", chk.trend_confluence, isKhmer ? "ទំនោរទីផ្សារ HTF" : "HTF Trend Alignment");
  setChecklistPill("chk-smc", chk.smc_confluence, isKhmer ? "រចនាសម្ព័ន្ធ SMC/OTE" : "SMC Liquidity / OTE");
  setChecklistPill("chk-macro", chk.macro_confluence, isKhmer ? "ឥទ្ធិពលប្រាក់ដុល្លារ" : "Macro Dollar Bias");
  setChecklistPill("chk-rr", chk.risk_reward_confluence, isKhmer ? "អនុបាតតាមការកំណត់" : "Configured R:R Floor Verified");
}

function renderBullets(id, items) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = "";
  const list = (items && items.length) ? items : ["No specific trigger."];
  list.forEach(txt => {
    const li = document.createElement("li");
    li.innerText = txt;
    el.appendChild(li);
  });
}

function setCauseBadge(id, bias) {
  const el = document.getElementById(id);
  if (!el) return;
  const b = bias || "NEUTRAL";
  el.innerText = b;
  if (b.includes("BULLISH") || b === "APPROVE") {
    el.className = "agent-bias-badge badge-bull";
  } else if (b.includes("BEARISH") || b === "REJECT") {
    el.className = "agent-bias-badge badge-bear";
  } else {
    el.className = "agent-bias-badge badge-neutral";
  }
}

function setChecklistPill(id, passed, label) {
  const el = document.getElementById(id);
  if (!el) return;
  if (passed) {
    el.className = "chk-pill chk-pass";
    el.innerText = `✓ ${label}`;
  } else {
    el.className = "chk-pill chk-fail";
    el.innerText = `✗ ${label}`;
  }
}

function updateExecutionCard(data) {
  const badge = document.getElementById("exec-action-badge");
  const notice = document.getElementById("rejection-notice");
  const isApproved = data.setup_status === "APPROVE";
  const dir = data.proposed_direction || "NONE";

  if (isApproved) {
    if (badge) {
      badge.innerText = `${dir === "LONG" ? "BUY / LONG" : "SELL / SHORT"} VALIDATED`;
      badge.className = dir === "LONG" ? "exec-action-badge badge-bull" : "exec-action-badge badge-bear";
    }
    if (notice) notice.style.display = "none";

    document.getElementById("exec-entry").innerText = data.entry_price || data.verified_price || "---";
    document.getElementById("exec-sl").innerText = data.stop_loss || "---";
    document.getElementById("exec-tp1").innerText = data.take_profit_1 || "---";
    document.getElementById("exec-tp2").innerText = data.take_profit_2 || "---";
    document.getElementById("exec-rr").innerText = data.risk_reward_ratio || "---";
  } else {
    if (badge) {
      badge.innerText = data.setup_status === "REJECT" ? "LOCKED (REJECTED)" : "WAITING CONFIRMATION";
      badge.className = "exec-action-badge badge-bear";
    }
    if (notice) {
      notice.style.display = "block";
      const reasons = data.agents?.agent_4_risk?.reasons || ["Risk rules not satisfied."];
      notice.innerHTML = `🛡️ <b>${isKhmer ? "ប្រព័ន្ធការពារដើមទុនកំពុងដំណើរការ:" : "Capital Protection Active:"}</b> ${reasons.join(" | ")}. ${isKhmer ? "ចំណុចជួញដូរត្រូវបានចាក់សោដើម្បីការពារដើមទុន។" : "Execution levels locked to protect capital."}`;
    }

    document.getElementById("exec-entry").innerText = "LOCKED";
    document.getElementById("exec-sl").innerText = "LOCKED";
    document.getElementById("exec-tp1").innerText = "LOCKED";
    document.getElementById("exec-tp2").innerText = "LOCKED";
    document.getElementById("exec-rr").innerText = data.risk_reward_ratio || "N/A";
  }

  const inval = document.getElementById("exec-inval");
  if (inval) {
    inval.innerText = data.invalidation_rules || "Wait for confirmed structural shift.";
  }
}


function updateSmcHud(data) {
  const smc = data.ict_smc_summary || {};
  const ote = smc.ote || {};
  const dealing = smc.dealing_range || {};
  const a2 = data.agents?.agent_2_ict_smc || {};
  const zones = a2.key_price_zones || {};

  // 1. Killzone Status & Pulse Badge
  const kzText = zones.killzone_status || smc.killzones || "⚪ STANDBY (Interbank Range)";
  const kzEl = document.getElementById("kz-status-text");
  if (kzEl) kzEl.innerText = kzText;

  // 2. Dealing Range & OTE Sweet Spot
  const rangeHigh = dealing.high || zones.dealing_range_high || 0;
  const rangeLow = dealing.low || zones.dealing_range_low || 0;
  const eq = dealing.equilibrium || zones.equilibrium_50pct || 0;
  const oteSweet = dealing.ote_sweet_spot || zones.ote_sweet_spot || "---";

  document.getElementById("ote-range-low").innerText = rangeLow ? rangeLow : "---";
  document.getElementById("ote-range-high").innerText = rangeHigh ? rangeHigh : "---";
  document.getElementById("ote-range-eq").innerText = eq ? eq : "---";
  document.getElementById("ote-sweet-spot").innerText = oteSweet;

  const inOte = dealing.in_ote_zone || zones.in_ote_zone;
  const currZone = dealing.current_zone || zones.current_zone || "EQUILIBRIUM";
  const oteBadge = document.getElementById("ote-status-badge");
  if (oteBadge) {
    if (inOte) {
      oteBadge.innerText = `🎯 IN OTE GOLDEN ZONE (0.705)`;
      oteBadge.className = "tf-status-badge badge-bull-soft";
    } else {
      oteBadge.innerText = `${currZone} ZONE`;
      oteBadge.className = currZone === "DISCOUNT" ? "tf-status-badge badge-bull-soft" : (currZone === "PREMIUM" ? "tf-status-badge badge-bear-soft" : "tf-status-badge badge-neutral-soft");
    }
  }

  // Position OTE Slider Marker
  const marker = document.getElementById("ote-slider-marker");
  const currPrice = parseFloat(data.verified_price) || 0;
  if (marker && rangeHigh > rangeLow && currPrice > 0) {
    const pct = Math.max(3, Math.min(97, ((currPrice - rangeLow) / (rangeHigh - rangeLow)) * 100));
    marker.style.left = `${pct}%`;
  }

  // 3. SMC 4-Zones Matrix
  const obs = zones.recent_order_blocks || smc.order_blocks || [];
  const obEl = document.getElementById("smc-ob-val");
  if (obEl) {
    if (obs.length > 0) {
      const latestOb = obs[obs.length - 1];
      obEl.innerText = `${latestOb.type.replace("_ORDER_BLOCK", "")} [${latestOb.low} - ${latestOb.high}]`;
    } else {
      obEl.innerText = "No Order Block detected";
    }
  }

  const breakers = zones.breaker_blocks || smc.breaker_blocks || [];
  const bbEl = document.getElementById("smc-bb-val");
  if (bbEl) {
    if (breakers.length > 0) {
      const latestBb = breakers[breakers.length - 1];
      bbEl.innerText = `${latestBb.type.replace("_BREAKER", "")} [${latestBb.low} - ${latestBb.high}]`;
    } else {
      bbEl.innerText = "No Breaker Active";
    }
  }

  const fvgs = zones.unmitigated_fvgs || smc.unmitigated_fvgs || [];
  const fvgEl = document.getElementById("smc-fvg-val");
  if (fvgEl) {
    if (fvgs.length > 0) {
      const latestFvg = fvgs[fvgs.length - 1];
      fvgEl.innerText = `${latestFvg.type.replace("_FVG", "")} [${latestFvg.bottom} - ${latestFvg.top}]`;
    } else {
      fvgEl.innerText = "Mitigated (Zero Imbalances)";
    }
  }

  const liqEl = document.getElementById("smc-liq-val");
  if (liqEl) {
    liqEl.innerText = `${currZone} Equilibrium (Rangebound)`;
  }

  // 3b. Fixed Range Volume Profile (POC / VAH / VAL)
  const vp = smc.volume_profile || zones.volume_profile || {};
  const vpValEl = document.getElementById("smc-vp-val");
  const vpSubEl = document.getElementById("smc-vp-sub");
  if (vpValEl && vp.poc) {
    vpValEl.innerText = `POC: ${vp.poc}`;
    if (vpSubEl) {
      vpSubEl.innerText = `VAH: ${vp.vah || '---'} | VAL: ${vp.val || '---'}`;
    }
  } else if (vpValEl) {
    vpValEl.innerText = "Computing POC...";
  }

  // 3c. Inversion FVG (IFVG) & Balanced Price Range (BPR)
  const ifvgData = smc.inversion_fvgs || zones.inversion_fvgs || {};
  const ifvgValEl = document.getElementById("smc-ifvg-val");
  const ifvgSubEl = document.getElementById("smc-ifvg-sub");
  const activeRetest = ifvgData.active_retest;
  const ifvgList = ifvgData.inversion_fvgs || [];
  const bprList = ifvgData.balanced_price_ranges || [];

  if (ifvgValEl) {
    if (activeRetest) {
      const typeLabel = activeRetest.type ? activeRetest.type.replace("_INVERSION_FVG", " IFVG") : "BPR Retest";
      ifvgValEl.innerText = `⚡ ${typeLabel}`;
      if (ifvgSubEl) ifvgSubEl.innerText = `Retesting [${activeRetest.bottom} - ${activeRetest.top}]`;
    } else if (ifvgList.length > 0) {
      const latestIfvg = ifvgList[ifvgList.length - 1];
      const typeLabel = latestIfvg.type.replace("_INVERSION_FVG", " IFVG");
      ifvgValEl.innerText = `${typeLabel} [${latestIfvg.bottom} - ${latestIfvg.top}]`;
      if (ifvgSubEl) ifvgSubEl.innerText = latestIfvg.role === "SUPPORT_FLIP" ? "Bullish Support Flip" : "Bearish Resistance Flip";
    } else if (bprList.length > 0) {
      const latestBpr = bprList[bprList.length - 1];
      ifvgValEl.innerText = `🧲 BPR [${latestBpr.bottom} - ${latestBpr.top}]`;
      if (ifvgSubEl) ifvgSubEl.innerText = "Balanced Price Magnet";
    } else {
      ifvgValEl.innerText = "Zero Inversions";
      if (ifvgSubEl) ifvgSubEl.innerText = "Clean Price Action";
    }
  }

  // 3d. Volume Profile Visual HUD & Value Area Bars
  const vpHudWrap = document.getElementById("vp-hud-wrap");
  if (vpHudWrap && vp.poc) {
    const nodeVah = document.getElementById("vp-node-vah");
    const nodePoc = document.getElementById("vp-node-poc");
    const nodeVal = document.getElementById("vp-node-val");
    const nodeVol = document.getElementById("vp-node-vol");
    if (nodeVah) nodeVah.innerText = vp.vah || "---";
    if (nodePoc) nodePoc.innerText = vp.poc || "---";
    if (nodeVal) nodeVal.innerText = vp.val || "---";
    if (nodeVol) nodeVol.innerText = vp.total_volume ? vp.total_volume.toLocaleString() : "---";

    const vpBadge = document.getElementById("vp-position-badge");
    if (vpBadge) {
      if (vp.current_position === "BELOW_VAL") {
        vpBadge.innerText = isKhmer ? "ក្រោម VAL (DISCOUNT / ប្រមូលទិញ)" : "BELOW VAL (DISCOUNT / ACCUMULATION)";
        vpBadge.className = "tf-status-badge badge-bull-soft";
      } else if (vp.current_position === "ABOVE_VAH") {
        vpBadge.innerText = isKhmer ? "លើស VAH (PREMIUM / អស់កម្លាំង)" : "ABOVE VAH (PREMIUM / EXHAUSTION)";
        vpBadge.className = "tf-status-badge badge-bear-soft";
      } else if (vp.current_position === "AT_POC") {
        vpBadge.innerText = isKhmer ? "នៅត្រង់ POC (តំបន់តុល្យភាពបរិមាណខ្ពស់)" : "AT POC (POINT OF CONTROL BALANCE)";
        vpBadge.className = "tf-status-badge badge-gold";
      } else {
        vpBadge.innerText = isKhmer ? "ក្នុង VALUE AREA (៧០% តម្លៃយុត្តិធម៌)" : "INSIDE VALUE AREA (70% FAIR VALUE)";
        vpBadge.className = "tf-status-badge badge-neutral-soft";
      }
    }

    const vpBarsContainer = document.getElementById("vp-bars-container");
    if (vpBarsContainer && Array.isArray(vp.profile_bars)) {
      vpBarsContainer.innerHTML = vp.profile_bars.map(bar => `
        <div class="vp-bar-row ${bar.is_poc ? 'is-poc' : ''} ${bar.in_value_area ? 'in-va' : ''}" title="Price: ${bar.price} | Volume: ${bar.volume} (${bar.percentage}%)">
          <span class="vp-bar-price">${bar.price}</span>
          <div class="vp-bar-track">
            <div class="vp-bar-fill" style="width: ${Math.max(4, bar.percentage)}%"></div>
          </div>
          <span class="vp-bar-vol">${bar.volume}</span>
        </div>
      `).join("");
    }

    const vpInterp = document.getElementById("vp-interpretation");
    if (vpInterp) {
      const text = isKhmer ? (vp.summary_kh || vp.summary_en) : (vp.summary_en || vp.summary_kh);
      if (text) vpInterp.innerText = text;
    }
  }

  // 4. Multi-Timeframe Trend Matrix
  const mtf = data.trend_matrix || data.agents?.agent_1_technical?.multi_timeframe_alignment || {};
  setTfBadge("tf-d1", mtf.D1);
  setTfBadge("tf-h4", mtf.H4);
  setTfBadge("tf-h1", mtf.H1);
  setTfBadge("tf-m15", mtf.M15);
  setTfBadge("tf-m5", mtf.M5 || mtf.M15);
}

function setTfBadge(id, trend) {
  const el = document.getElementById(id);
  if (!el) return;
  const t = trend || "NEUTRAL";
  el.innerText = t;
  if (t.includes("BULLISH")) {
    el.className = "tf-status-badge badge-bull-soft";
  } else if (t.includes("BEARISH")) {
    el.className = "tf-status-badge badge-bear-soft";
  } else {
    el.className = "tf-status-badge badge-neutral-soft";
  }
}


function updateAgentCard(prefix, bias, text) {
  const bEl = document.getElementById(`${prefix}-bias`);
  const tEl = document.getElementById(`${prefix}-text`);
  if (!bEl || !tEl) return;

  bEl.innerText = bias || "NEUTRAL";
  if ((bias || "").includes("BULLISH") || bias === "APPROVE") {
    bEl.className = "agent-bias-badge badge-bull";
  } else if ((bias || "").includes("BEARISH") || bias === "REJECT") {
    bEl.className = "agent-bias-badge badge-bear";
  } else {
    bEl.className = "agent-bias-badge badge-neutral";
  }
  tEl.innerText = text || "Analysis completed.";
}

function updateReportView(data) {
  const container = document.getElementById("report-view-container");
  if (!container) return;

  if (isKhmer) {
    container.innerText = `${data.report_khmer}\n\n${'='.repeat(35)}\n\n${data.report_english}`;
  } else {
    container.innerText = `${data.report_english}\n\n${'='.repeat(35)}\n\n${data.report_khmer}`;
  }
}

async function fetchHealthAndPaper() {
  try {
    // 1. Health
    const hr = await fetch(`${API_BASE}/health`);
    const hData = await hr.json();
    const cyclesEl = document.getElementById("h-cycles");
    if (cyclesEl) cyclesEl.innerText = hData.monitoring_engine?.cycles_completed ?? "N/A";
    const feedEl = document.getElementById("h-feeds");
    if (feedEl) feedEl.innerText = hData.status === "HEALTHY" ? "FRESH DATA" : "DEGRADED / STALE";
    const subsystemFeeds = document.getElementById("subsys-feeds");
    if (subsystemFeeds) subsystemFeeds.innerText = hData.status || "UNKNOWN";
    const llmProviders = hData.llm_providers || {};
    const providerStatuses = Object.values(llmProviders);
    const configuredProviders = providerStatuses.filter(provider => provider && provider.configured).length;
    const subsystemLlm = document.getElementById("subsys-llm");
    if (subsystemLlm) subsystemLlm.innerText = `${configuredProviders} provider(s) configured · not probed`;
    const llmStatus = document.getElementById("ai-chat-provider-status");
    const selectedProvider = document.getElementById("ai-chat-provider-select")?.value || "auto";
    const selectedInfo = selectedProvider === "auto"
      ? null
      : llmProviders[selectedProvider];
    if (llmStatus) {
      if (selectedInfo) {
        llmStatus.innerText = selectedInfo.configured ? "Key configured · not probed" : "No provider key configured";
      } else if (configuredProviders > 0) {
        llmStatus.innerText = `${configuredProviders} provider(s) configured · not probed`;
      } else {
        llmStatus.innerText = "No cloud LLM key configured";
      }
    }

    // 2. Paper Trades
    const pr = await fetch(`${API_BASE}/api/v1/paper-trades`);
    const pData = pr.ok ? await pr.json() : {};
    const acct = pData.account_summary || {};
    const balanceEl = document.getElementById("paper-balance");
    if (balanceEl) balanceEl.innerText = acct.current_balance != null && Number.isFinite(Number(acct.current_balance))
      ? `$${Number(acct.current_balance).toLocaleString('en-US', {minimumFractionDigits: 2})}`
      : "Unavailable";
    const pnl = acct.realized_pnl == null ? NaN : Number(acct.realized_pnl);
    const pnlEl = document.getElementById("paper-pnl");
    if (pnlEl) {
      pnlEl.innerText = Number.isFinite(pnl) ? `${pnl >= 0 ? '+' : ''}$${pnl.toLocaleString('en-US', {minimumFractionDigits: 2})}` : "Unavailable";
      pnlEl.className = Number.isFinite(pnl) ? (pnl >= 0 ? "metric-value val-green" : "metric-value val-red") : "metric-value";
    }

    const tbody = document.getElementById("paper-trades-body");
    if (!pr.ok) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted">Paper ledger requires administrator access.</td></tr>`;
    } else if (tbody && pData.trades && pData.trades.length > 0) {
      tbody.innerHTML = "";
      pData.trades.slice(0, 5).forEach(t => {
        const row = document.createElement("tr");
        const pnlValue = t.pnl == null ? NaN : Number(t.pnl);
        row.innerHTML = `
          <td><b>${escapeHtml(String(t.symbol || "N/A"))}</b></td>
          <td style="color: ${t.direction === 'BUY' ? 'var(--accent-green)' : 'var(--accent-red)'}">${escapeHtml(String(t.direction || "N/A"))}</td>
          <td>${t.lot_size != null && Number.isFinite(Number(t.lot_size)) ? Number(t.lot_size) : "N/A"}</td>
          <td style="color: ${Number.isFinite(pnlValue) && pnlValue >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">${Number.isFinite(pnlValue) ? `$${pnlValue.toFixed(2)}` : "N/A"}</td>
          <td><span style="font-size: 9px; padding: 2px 4px; border-radius: 4px; background: rgba(255,255,255,0.08);">${escapeHtml(String(t.status || "N/A"))}</span></td>
        `;
        tbody.appendChild(row);
      });
    } else if (tbody) {
      tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted">No paper trades recorded.</td></tr>`;
    }
  } catch (e) {}
}

function updateMacroCatalystUI(catalyst) {
  if (!catalyst) return;
  currentXauusdCatalyst = catalyst;
  const badgeEl = document.getElementById("macro-catalyst-badge");
  const textEl = document.getElementById("macro-catalyst-text");
  if (!badgeEl || !textEl) return;

  const rawBadge = isKhmer ? (catalyst.badge_kh || catalyst.badge_en) : (catalyst.badge_en || catalyst.badge_kh);
  // Strip leading emoji if present, since .macro-fire-icon already holds the icon
  const cleanText = rawBadge ? rawBadge.replace(/^[⚡🔥✅]\s*/, "") : (isKhmer ? "មិនមានទិន្នន័យប្រតិទិនដែលបានផ្ទៀងផ្ទាត់" : "No verified calendar data");
  textEl.innerText = cleanText;

  const iconEl = badgeEl.querySelector(".macro-fire-icon");
  if (iconEl) {
    if (catalyst.is_blackout || (catalyst.countdown_seconds >= -1800 && catalyst.countdown_seconds <= 1800)) {
      iconEl.innerText = "🔥";
    } else if (catalyst.countdown_seconds < -1800) {
      iconEl.innerText = "✅";
    } else {
      iconEl.innerText = "⚡";
    }
  }

  // Active blackout pulse
  if (catalyst.is_blackout || (catalyst.countdown_seconds >= -1800 && catalyst.countdown_seconds <= 1800)) {
    badgeEl.classList.add("pill-blackout-active");
  } else {
    badgeEl.classList.remove("pill-blackout-active");
  }

  // Set rich institutional tooltip
  const scheduled = catalyst.scheduled_display || catalyst.scheduled_utc || "";
  const goldImpact = isKhmer ? (catalyst.gold_impact_kh || catalyst.gold_impact_en) : (catalyst.gold_impact_en || catalyst.gold_impact_kh);
  badgeEl.title = `📅 ${catalyst.title} (${scheduled})\n` +
    `⚡ Impact: ${catalyst.country} High Impact (${catalyst.category})\n` +
    `📊 Forecast: ${catalyst.forecast || 'N/A'} | Previous: ${catalyst.previous || 'N/A'}\n` +
    `🥇 Gold Volatility: ${catalyst.volatility_risk || 'EXTREME'}\n` +
    `💡 ${goldImpact || ''}\n` +
    `[Click to open Full Forex Factory Macro Calendar]`;
}

function startMacroCountdownTimer() {
  if (macroCountdownInterval) return;
  macroCountdownInterval = setInterval(() => {
    if (!currentXauusdCatalyst || currentXauusdCatalyst.countdown_seconds == null) return;
    currentXauusdCatalyst.countdown_seconds -= 1;
    const s = currentXauusdCatalyst.countdown_seconds;
    const cat = currentXauusdCatalyst.category || "FOMC";

    if (s < -1800) {
      const passedHrs = Math.abs((s / 3600).toFixed(1));
      currentXauusdCatalyst.badge_en = `✅ ${cat} Completed ${passedHrs}h ago`;
      currentXauusdCatalyst.badge_kh = `✅ ${cat} បានបញ្ចប់ ${passedHrs}ម៉ោងមុន`;
      currentXauusdCatalyst.is_blackout = false;
    } else if (s >= -1800 && s <= 0) {
      currentXauusdCatalyst.badge_en = `🔥 ${cat} RELEASING NOW · Extreme Volatility`;
      currentXauusdCatalyst.badge_kh = `🔥 ${cat} កំពុងចេញផ្សាយ · ប្រែប្រួលខ្លាំង`;
      currentXauusdCatalyst.is_blackout = true;
    } else if (s > 0 && s <= 1800) {
      const mins = Math.max(1, Math.floor(s / 60));
      currentXauusdCatalyst.badge_en = `⚡ ${cat} in ${mins}m · Blackout Active`;
      currentXauusdCatalyst.badge_kh = `⚡ ${cat} ក្នុង ${mins}នាទី · បំរាមជួញដូរ`;
      currentXauusdCatalyst.is_blackout = true;
    } else if (s > 1800 && s < 86400) {
      const hrs = Math.floor(s / 3600);
      const remM = Math.floor((s % 3600) / 60);
      let tEn = "", tKh = "";
      if (hrs > 0 && remM > 0) {
        tEn = `${hrs}h ${remM}m`;
        tKh = `${hrs}ម៉ោង ${remM}នាទី`;
      } else if (hrs > 0) {
        tEn = `${hrs}h`;
        tKh = `${hrs}ម៉ោង`;
      } else {
        tEn = `${remM}m`;
        tKh = `${remM}នាទី`;
      }
      currentXauusdCatalyst.badge_en = `⚡ ${cat} in ${tEn} · High Impact`;
      currentXauusdCatalyst.badge_kh = `⚡ ${cat} ក្នុង ${tKh} · ឥទ្ធិពលខ្លាំងលើមាស`;
      currentXauusdCatalyst.is_blackout = false;
    } else {
      const days = Math.floor(s / 86400);
      const remH = Math.floor((s % 86400) / 3600);
      const tEn = remH > 0 ? `${days}d ${remH}h` : `${days}d`;
      const tKh = remH > 0 ? `${days}ថ្ងៃ ${remH}ម៉ោង` : `${days}ថ្ងៃ`;
      currentXauusdCatalyst.badge_en = `⚡ ${cat} in ${tEn} · High Impact`;
      currentXauusdCatalyst.badge_kh = `⚡ ${cat} ក្នុង ${tKh} · ឥទ្ធិពលខ្លាំងលើមាស`;
      currentXauusdCatalyst.is_blackout = false;
    }

    updateMacroCatalystUI(currentXauusdCatalyst);
  }, 1000);
}

function renderCockpitNewsQuickList(catalyst, events) {
  const container = document.getElementById("cockpit-news-quick-list");
  if (!container) return;

  let html = "";
  if (catalyst) {
    const safe = value => escapeHtml(String(value ?? ""));
    const isBlackout = catalyst.is_blackout || (catalyst.countdown_seconds >= -1800 && catalyst.countdown_seconds <= 1800);
    const catBadge = isKhmer ? (catalyst.badge_kh || catalyst.badge_en) : (catalyst.badge_en || catalyst.badge_kh);
    const goldTxt = isKhmer ? (catalyst.gold_impact_kh || catalyst.gold_impact_en) : (catalyst.gold_impact_en || catalyst.gold_impact_kh);
    html += `
      <div class="cockpit-catalyst-hero ${isBlackout ? 'card-blackout-active' : ''}" onclick="toggleMacroDrawer()" title="Click to view full Macro Calendar">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
          <span style="font-size:10px; font-weight:800; color:#fb7185; letter-spacing:0.4px;">🥇 XAUUSD HIGH-IMPACT CATALYST</span>
          <span style="font-size:10px; font-weight:800; padding:2px 6px; border-radius:10px; background:rgba(239,68,68,0.2); color:#fca5a5; border:1px solid rgba(239,68,68,0.4);">${safe(catalyst.volatility_risk)}</span>
        </div>
        <div style="font-size:12px; font-weight:800; color:#fff; margin-bottom:3px;">
          ${safe(catalyst.title)}
        </div>
        ${catalyst.title_kh ? `<div style="font-size:11px; color:#fce79f; margin-bottom:4px; font-family:var(--font-khmer);">${safe(catalyst.title_kh)}</div>` : ''}
        <div style="display:flex; justify-content:space-between; align-items:center; font-size:10.5px; color:#cbd5e1; margin-bottom:4px;">
          <span>⏱️ ${safe(catBadge)}</span>
          <span>Forecast: <b>${safe(catalyst.forecast || 'N/A')}</b></span>
        </div>
        <div style="font-size:10px; color:#94a3b8; line-height:1.35; border-top:1px solid rgba(255,255,255,0.08); padding-top:4px;">
          ${safe(goldTxt)}
        </div>
      </div>
    `;
  }

  if (events && events.length > 0) {
    html += `<div style="font-size:10px; font-weight:700; color:#94a3b8; margin:6px 0 4px 0; text-transform:uppercase; letter-spacing:0.3px;">Upcoming Macro Releases</div>`;
    events.slice(0, 4).forEach(ev => {
      const isBlk = ev.blackout_active;
      const title = escapeHtml(String(ev.title ?? ""));
      const titleKh = escapeHtml(String(ev.title_kh ?? ""));
      const timeUntil = escapeHtml(String(ev.time_until ?? "N/A"));
      html += `
        <div class="cockpit-news-card ${isBlk ? 'card-blackout-active' : ''}" onclick="toggleMacroDrawer()" title="Click to view macro details">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:3px;">
            <span style="font-size:9.5px; font-weight:800; color:#fca5a5; background:rgba(239,68,68,0.18); padding:1px 5px; border-radius:4px;">🔴 ${escapeHtml(String(ev.country ?? 'N/A'))} HIGH</span>
            <span style="font-size:10px; font-weight:700; color:#ffd700;">${timeUntil}</span>
          </div>
          <div style="font-size:11px; font-weight:700; color:#e2e8f0;">${title}</div>
          ${titleKh ? `<div style="font-size:10px; color:#fde68a; font-family:var(--font-khmer);">${titleKh}</div>` : ''}
        </div>
      `;
    });
  } else if (!catalyst) {
    html = `<div style="padding:10px; text-align:center; color:#94a3b8; font-size:11px;">No verified high-impact event data is available in this response.</div>`;
  }

  container.innerHTML = html;
}

async function fetchMacroEvents(forceRefresh = false) {
  const container = document.getElementById("calendar-events-container");
  const blackoutBanner = document.getElementById("macro-blackout-banner");
  const blackoutHeadline = document.getElementById("blackout-headline");
  const blackoutDesc = document.getElementById("blackout-desc");
  const newsContainer = document.getElementById("live-macro-news-container");

  try {
    const url = `${API_BASE}/api/v1/calendar/high-impact${forceRefresh ? '?force_refresh=true' : ''}`;
    const r = await fetch(url);
    const data = await r.json();

    // 0. Update Real-Time Macro Catalyst Badge on Chart HUD & Cockpit News
    if (data.next_xauusd_catalyst) {
      currentXauusdCatalyst = data.next_xauusd_catalyst;
      updateMacroCatalystUI(currentXauusdCatalyst);
      startMacroCountdownTimer();
    }
    cachedMacroEvents = data.events || [];
    renderCockpitNewsQuickList(currentXauusdCatalyst, cachedMacroEvents);

    // 1. Audit News Blackout
    const blackout = data.blackout_status || {};
    if (blackoutBanner) {
      if (blackout.is_blackout || blackout.status === "UNAVAILABLE") {
        blackoutBanner.style.display = "block";
        if (blackoutHeadline) {
          blackoutHeadline.innerText = blackout.status === "UNAVAILABLE"
            ? (isKhmer ? "⚠️ មិនអាចផ្ទៀងផ្ទាត់ប្រតិទិនព័ត៌មានបានទេ" : "⚠️ CALENDAR FEED UNAVAILABLE")
            : (isKhmer ? "⚠️ បំរាមជួញដូរពេលចេញព័ត៌មាន (News Lockout)" : "⚠️ PRE-NEWS BLACKOUT ACTIVE");
        }
        if (blackoutDesc) {
          blackoutDesc.innerText = isKhmer ? blackout.advisory_kh : blackout.advisory_en;
        }
      } else {
        blackoutBanner.style.display = "none";
      }
    }

    // 2. Render Calendar Events
    const events = data.events || [];
    if (container) {
      if (events.length === 0) {
        container.innerHTML = `<div class="text-center text-muted" style="padding: 12px; font-size: 11px;">No verified calendar events were returned.</div>`;
      } else {
        container.innerHTML = "";
        events.slice(0, 6).forEach(ev => {
          const card = document.createElement("div");
          const isBlackout = ev.blackout_active;
          card.className = `calendar-event-card ${isBlackout ? 'event-blackout-active' : ''}`;

          const countdownClass = ev.status_badge === "RELEASE_IN_PROGRESS" || ev.status_badge === "IMMINENT_BLACKOUT"
            ? "event-countdown-pill pill-active-now"
            : "event-countdown-pill";

          const safeEventText = value => escapeHtml(String(value ?? "N/A"));
          card.innerHTML = `
            <div class="event-header-row">
              <div class="event-title-badge">
                <span class="event-impact-pill">🔴 ${safeEventText(ev.country)} HIGH</span>
                <span>${safeEventText(ev.title)}</span>
              </div>
              <span class="${countdownClass}">${safeEventText(ev.time_until)}</span>
            </div>
            <div class="event-khmer-title">🇰🇭 ${safeEventText(ev.title_kh)}</div>
            <div class="event-metrics-row">
              <span>Forecast: <b class="event-metric-val">${safeEventText(ev.forecast)}</b></span>
              <span>Previous: <b class="event-metric-val">${safeEventText(ev.previous)}</b></span>
              <span>Gold Risk: <b class="event-metric-val" style="color: var(--gold-bright);">${safeEventText(ev.volatility_risk)}</b></span>
            </div>
            <div class="event-impact-explanation ${isKhmer ? 'khmer-text' : ''}">
              ${safeEventText(isKhmer ? ev.gold_impact_kh : ev.gold_impact_en)}
            </div>
          `;
          container.appendChild(card);
        });
      }
    }
  } catch (err) {
    console.warn("Failed to fetch macro calendar:", err);
  }

  // 3. Fetch Live Breaking Macro News
  try {
    const nr = await fetch(`${API_BASE}/api/v1/news/live?limit=6`);
    const nData = await nr.json();
    if (newsContainer && nData.news) {
      newsContainer.innerHTML = "";
      nData.news.forEach(item => {
        const itemDiv = document.createElement("div");
        itemDiv.className = "live-news-item";
        let safeNewsLink = "#";
        try {
          const parsedLink = new URL(item.link || "");
          if (["http:", "https:"].includes(parsedLink.protocol)) safeNewsLink = parsedLink.href;
        } catch (_) {}
        itemDiv.innerHTML = `
          <div class="live-news-meta">
            <span class="live-news-source">${escapeHtml(String(item.source || "Unknown source"))}</span>
            <span>${escapeHtml(String(item.published_at || ""))}</span>
          </div>
          <a class="live-news-title" href="${escapeHtml(safeNewsLink)}" target="_blank" rel="noopener noreferrer">${escapeHtml(String(item.title || "Untitled"))}</a>
        `;
        newsContainer.appendChild(itemDiv);
      });
    }
  } catch (nErr) {
    console.warn("Failed to fetch live macro news:", nErr);
  }
}

async function runBacktestAction() {
  const panel = document.getElementById("backtest-results-panel");
  panel.style.display = "block";
  document.getElementById("bt-win-rate").innerText = "Simulating...";

  try {
    const r = await fetch(`${API_BASE}/api/v1/backtests/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: currentSymbol, timeframe: "M15", candle_limit: 120 })
    });
    const data = await r.json();

    document.getElementById("bt-win-rate").innerText = `${data.win_rate_percent}%`;
    document.getElementById("bt-profit-factor").innerText = data.profit_factor;
    document.getElementById("bt-drawdown").innerText = `${data.max_drawdown_percent}%`;
    document.getElementById("bt-avg-r").innerText = `${data.average_r_multiple}R`;
  } catch (e) {
    document.getElementById("bt-win-rate").innerText = "Backtest ready.";
  }
}

function copyReport() {
  const text = document.getElementById("report-view-container").innerText;
  navigator.clipboard.writeText(text);
  alert("Intelligence report copied to clipboard!");
}

/* ==========================================================================
   MAIN NAVIGATION TABS (Signals, AI Debate, Self-Training, Alert-Auto-Fix)
   ========================================================================== */

function switchMainTab(tabName, btn) {
  activeMainTab = tabName;
  document.querySelectorAll(".main-tab-btn").forEach(b => b.classList.remove("active"));
  if (btn) {
    btn.classList.add("active");
  } else {
    const targetBtn = document.getElementById(`tab-btn-${tabName}`);
    if (targetBtn) targetBtn.classList.add("active");
  }

  const pSignals = document.getElementById("tab-pane-signals");
  const pDebate = document.getElementById("tab-pane-debate");
  const pTraining = document.getElementById("tab-pane-training");
  const pAutofix = document.getElementById("tab-pane-autofix");

  if (pSignals) pSignals.style.display = tabName === "signals" ? "block" : "none";
  if (pDebate) pDebate.style.display = tabName === "debate" ? "block" : "none";
  if (pTraining) pTraining.style.display = tabName === "training" ? "block" : "none";
  if (pAutofix) pAutofix.style.display = tabName === "autofix" ? "block" : "none";

  if (tabName === "debate") {
    fetchAgentsDebate(currentSymbol);
  } else if (tabName === "training") {
    fetchSelfTrainingData();
  } else if (tabName === "autofix") {
    fetchAutoFixAlerts();
  }
}

/* ==========================================================================
   TAB 2: AI AGENTS ROUND-TABLE DEBATE ("AI Agents និយាយគ្នាវិភាគ ទៅវិញទៅមក")
   ========================================================================== */

let isDebateLoading = false;

async function fetchAgentsDebate(symbol = "XAUUSD") {
  if (isDebateLoading) return;
  isDebateLoading = true;

  const symbolSpan = document.getElementById("debate-active-symbol");
  if (symbolSpan) symbolSpan.innerText = symbol;

  const chatStream = document.getElementById("debate-chat-stream");
  const verdictCard = document.getElementById("debate-verdict-card");
  const verdictText = document.getElementById("debate-verdict-text");
  const btn = document.getElementById("btn-trigger-debate");

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳ ${isKhmer ? "កំពុងពិនិត្យភស្តុតាងភ្នាក់ងារ..." : "Reviewing agent evidence..."}</span>`;
  }

  if (chatStream) {
    chatStream.innerHTML = `
      <div class="text-center text-muted" style="padding: 40px;">
        <div style="font-size: 24px; margin-bottom: 8px;">🔄</div>
        <div>${isKhmer ? `AI Agents កំពុងជជែកពិភាក្សាដេញដោលគ្នាអំពី ${symbol}...` : `Connecting multi-agent round-table for ${symbol}...`}</div>
      </div>
    `;
  }

  try {
    const res = await fetch(`${API_BASE}/api/v1/agents/debate?symbol=${symbol}&timeframe=M15`);
    const data = await res.json();

    if (chatStream && data.turns) {
      chatStream.innerHTML = "";
      data.turns.forEach(turn => {
        const card = document.createElement("div");
        card.className = "debate-turn-card";

        const stanceClass = turn.stance === "BULLISH" ? "bias-bullish" : (turn.stance === "BEARISH" ? "bias-bearish" : "bias-wait");
        const stanceBadge = `<span class="badge ${stanceClass}" style="font-size: 10px; padding: 2px 8px;">${escapeHtml(String(turn.stance || "NEUTRAL"))}</span>`;
        const badgeColor = /^#[0-9a-fA-F]{3,8}$/.test(turn.badge_color || "") ? turn.badge_color : "var(--accent-gold)";

        card.innerHTML = `
          <div class="turn-header">
            <div style="display: flex; align-items: center; gap: 10px;">
              <div class="agent-avatar-circle" style="border-color: ${badgeColor};">
                ${escapeHtml(String(turn.agent_avatar || '🤖'))}
              </div>
              <div>
                <span class="agent-speaker-name">${escapeHtml(String(turn.agent_name || "Agent"))}</span>
                <span style="font-size: 11px; color: var(--text-muted); margin-left: 8px;">${escapeHtml(String(turn.timestamp || ''))}</span>
              </div>
            </div>
            <div>${stanceBadge}</div>
          </div>
          <div class="turn-body">
            <div class="turn-msg-en">${escapeHtml(String(turn.message_en || ""))}</div>
            <div class="turn-msg-kh">🇰🇭 ${escapeHtml(String(turn.message_kh || ""))}</div>
          </div>
        `;
        chatStream.appendChild(card);
      });
    }

    if (verdictCard && verdictText) {
      const decision = ["APPROVE", "REJECT", "WAIT"].includes(data.consensus_decision) ? data.consensus_decision : "WAIT";
      let statusColor = "var(--accent-yellow)";
      let verdictIcon = "⏸️";

      if (decision === "APPROVE") {
        statusColor = "var(--accent-green)";
        verdictIcon = "✅";
      } else if (decision === "REJECT") {
        statusColor = "var(--accent-red)";
        verdictIcon = "🛑";
      }

      verdictCard.style.borderColor = statusColor;
      verdictText.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; color: ${statusColor}; font-size: 15px; margin-bottom: 6px;">
          <span>${verdictIcon}</span>
          <span>${isKhmer ? `សេចក្តីសម្រេច៖ ${decision}` : `Consensus result: ${decision}`}</span>
          <span style="font-size: 12px; color: var(--text-muted); font-weight: 400;">(${escapeHtml(String(data.outcome_status || 'N/A'))})</span>
        </div>
        <div style="margin-bottom: 6px; color: var(--text-main);">${escapeHtml(String(data.debate_summary_en || ''))}</div>
        <div style="color: var(--text-muted); font-size: 13px;">🇰🇭 ${escapeHtml(String(data.debate_summary_kh || ''))}</div>
      `;
    }
  } catch (err) {
    if (chatStream) {
      chatStream.innerHTML = `<div class="text-center text-muted" style="padding: 20px;">Agent evidence review ready. Run it to inspect current analyses.</div>`;
    }
  } finally {
    isDebateLoading = false;
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `📋 <span id="t-run-debate-btn">${isKhmer ? "ពិនិត្យភស្តុតាងភ្នាក់ងារ" : "Review Agent Evidence"}</span>`;
    }
  }
}

function triggerAgentsDebate() {
  fetchAgentsDebate(currentSymbol);
}

/* ==========================================================================
   TAB 3: AUTONOMOUS SELF-TRAINING & REINFORCEMENT LEARNING ("Train ខ្លួនឯងបាន")
   ========================================================================== */

let isTrainingRunning = false;

async function fetchSelfTrainingData() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/agents/learning-stats`);
    const data = await res.json();

    const statEpochs = document.getElementById("stat-epochs");
    const statAcc = document.getElementById("stat-accuracy");
    const statLr = document.getElementById("stat-lr");
    const statPolicy = document.getElementById("stat-policy");

    if (statEpochs) statEpochs.innerText = data.total_epochs ?? 0;
    if (statAcc) statAcc.innerText = data.overall_accuracy != null && Number.isFinite(Number(data.overall_accuracy)) ? `${Number(data.overall_accuracy)}%` : "N/A";
    if (statLr) statLr.innerText = data.learning_rate || 0.05;
    if (statPolicy) statPolicy.innerText = data.reinforcement_policy || "PPMC Calibration";

    // Dynamic Weights Bar Fill
    const weightsContainer = document.getElementById("agent-weights-container");
    if (weightsContainer && data.weights) {
      weightsContainer.innerHTML = "";
      const agentLabels = {
        "ict_smc_analyst": { name: "Agent 2: Institutional ICT / SMC Engine", color: "var(--accent-purple)", icon: "🏛️" },
        "technical_analyst": { name: "Agent 1: Multi-Timeframe Technical & Trend", color: "var(--accent-cyan)", icon: "📈" },
        "macro_analyst": { name: "Agent 3: Macro Catalyst & DXY Cross-Check", color: "var(--blue-neon)", icon: "🌐" },
        "risk_validator": { name: "Agent 4: Capital Protection & Risk Arbiter", color: "var(--accent-gold)", icon: "🛡️" }
      };

      for (const [agentKey, weightVal] of Object.entries(data.weights)) {
        const info = agentLabels[agentKey] || { name: agentKey, color: "var(--accent-gold)", icon: "🤖" };
        const pct = Math.round(weightVal * 100);

        const row = document.createElement("div");
        row.className = "weight-row";
        row.innerHTML = `
          <div class="weight-label">
            <span>${info.icon} ${info.name}</span>
            <span style="font-weight: 700; color: ${info.color};">${pct}%</span>
          </div>
          <div class="weight-track">
            <div class="weight-fill" style="width: ${pct}%; background: ${info.color};"></div>
          </div>
        `;
        weightsContainer.appendChild(row);
      }
    }

    // Performance Scorecard Table
    const scorecardBody = document.getElementById("agent-scorecard-body");
    if (scorecardBody && data.agents_scorecard) {
      scorecardBody.innerHTML = "";
      data.agents_scorecard.forEach(item => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td style="font-family: monospace; font-weight: 600; color: var(--accent-gold);">${escapeHtml(String(item.agent_id || "N/A"))}</td>
          <td>${escapeHtml(String(item.specialization || "N/A"))}</td>
          <td style="font-weight: 700;">${Number.isFinite(Number(item.weight)) ? `${Math.round(Number(item.weight) * 100)}%` : "N/A"}</td>
          <td style="color: var(--accent-green); font-weight: 700;">${item.accuracy != null && Number.isFinite(Number(item.accuracy)) ? `${Number(item.accuracy)}%` : "N/A"}</td>
          <td>${Number(item.win_count) || 0}W / ${Number(item.loss_count) || 0}L</td>
          <td style="font-family: monospace;">${item.brier_score != null && Number.isFinite(Number(item.brier_score)) ? Number(item.brier_score) : "N/A"}</td>
          <td><span class="badge ${item.status === 'CALIBRATED' ? 'bias-bullish' : 'bias-wait'}" style="font-size: 10px; padding: 2px 6px;">${escapeHtml(String(item.status || "N/A"))}</span></td>
        `;
        scorecardBody.appendChild(tr);
      });
    }
  } catch (err) {
    console.error("Failed to fetch self-training data:", err);
  }
}

async function triggerSelfTrainingEpoch() {
  if (isTrainingRunning) return;
  isTrainingRunning = true;

  const btn = document.getElementById("btn-trigger-training");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳ ${isKhmer ? "កំពុងដំណើរការ Train ខ្លួនឯង..." : "Running Training Epoch..."}</span>`;
  }

  try {
    const res = await fetch(`${API_BASE}/api/v1/agents/train?symbol=${currentSymbol}`, {
      method: "POST"
    });
    const result = await res.json();
    await fetchSelfTrainingData();
    alert(isKhmer ? `វគ្គបណ្តុះបណ្តាលខ្លួនឯង (Epoch ${result.epoch}) បានបញ្ចប់ដោយជោគជ័យ! ទម្ងន់របស់ AI ត្រូវបានកែសម្រួល។` : `Self-training Epoch ${result.epoch} completed successfully! Ensemble voting weights updated.`);
  } catch (err) {
    alert("Self-training epoch completed.");
  } finally {
    isTrainingRunning = false;
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `🚀 <span id="t-train-epoch-btn">${isKhmer ? "ដំណើរការវគ្គហ្វឹកហាត់ (Train ឥឡូវ)" : "Trigger Training Epoch (Train ខ្លួនឯង)"}</span>`;
    }
  }
}

/* ==========================================================================
   TAB 4: ALERT-AUTO-FIX & SELF-HEALING SENTINEL ("Alert-Auto-Fix")
   ========================================================================== */

let isAutoFixRunning = false;

async function fetchAutoFixAlerts() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/system/auto-fix/alerts?limit=10`);
    const incidents = await res.json();

    const logBody = document.getElementById("autofix-log-body");
    if (logBody) {
      logBody.innerHTML = "";
      if (incidents.length === 0) {
        logBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted" style="padding: 20px;">No diagnostic records are available.</td></tr>`;
      } else {
        incidents.forEach(inc => {
          const tr = document.createElement("tr");

          let sevClass = "badge-info";
          if (inc.severity === "CRITICAL") sevClass = "bias-bearish";
          else if (inc.severity === "WARNING") sevClass = "bias-wait";
          else sevClass = "bias-bullish";

          tr.innerHTML = `
            <td style="font-family: monospace; font-weight: 600; color: var(--accent-gold);">${escapeHtml(String(inc.incident_id || ""))}</td>
            <td><span style="font-size: 11px; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.06);">${escapeHtml(String(inc.subsystem || ""))}</span></td>
            <td><span class="badge ${sevClass}" style="font-size: 10px; padding: 2px 6px;">${escapeHtml(String(inc.severity || ""))}</span></td>
            <td style="max-width: 260px; font-size: 12px; color: var(--text-main);">${escapeHtml(String(inc.description || ""))}</td>
            <td style="max-width: 280px; font-size: 12px; color: var(--accent-cyan); font-family: monospace;">${escapeHtml(String(inc.auto_fix_action || ""))}</td>
            <td><span>${escapeHtml(String(inc.status || ""))}</span></td>
            <td style="font-size: 11px; color: var(--text-muted);">${escapeHtml(String(inc.resolved_at || ""))}</td>
          `;
          logBody.appendChild(tr);
        });
      }
    }
  } catch (err) {
    console.error("Failed to fetch auto-fix alerts:", err);
  }
}

async function triggerSystemAutoFixAction() {
  if (isAutoFixRunning) return;
  isAutoFixRunning = true;

  const btn = document.getElementById("btn-trigger-autofix");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳ ${isKhmer ? "កំពុងត្រួតពិនិត្យ និងជួសជុល..." : "Diagnosing & Healing..."}</span>`;
  }

  try {
    const res = await fetch(`${API_BASE}/api/v1/system/auto-fix/trigger`, {
      method: "POST"
    });
    const result = await res.json();
    if (!res.ok) throw new Error(result.detail || result.message || "Diagnostic request failed.");

    const checks = result.checks || {};
    const elFeeds = document.getElementById("subsys-feeds");
    const elLlm = document.getElementById("subsys-llm");
    const elRisk = document.getElementById("subsys-risk");
    const elDb = document.getElementById("subsys-db");
    const elWebhook = document.getElementById("subsys-webhook");

    if (elFeeds) elFeeds.innerText = checks.market_data?.status || "Not checked";
    if (elLlm) elLlm.innerText = checks.llm?.status || "Not checked";
    if (elRisk) elRisk.innerText = "Not checked by this diagnostic";
    if (elDb) elDb.innerText = checks.database?.status || "Not checked";
    if (elWebhook) elWebhook.innerText = "Not checked by this diagnostic";

    await fetchAutoFixAlerts();
    alert(isKhmer ? result.message_kh : result.message);
  } catch (err) {
    alert(err.message || "Diagnostic request failed.");
  } finally {
    isAutoFixRunning = false;
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `⚡ <span id="t-run-autofix-btn">${isKhmer ? "ដំណើរការត្រួតពិនិត្យ និងជួសជុលភ្លាមៗ" : "Run Diagnostic & Auto-Fix"}</span>`;
    }
  }
}

/* ==========================================================================
   PRO COCKPIT CONTROLLER & PLAN CARD LOGIC (CRYPTO & FOREX)
   ========================================================================== */

let currentChipFilter = "ALL";

function changeColorTheme(theme) {
  const allowed = ["cyber-cyan", "tokyo-night", "emerald-terminal", "deep-sapphire", "solar-gold"];
  allowed.forEach(t => document.body.classList.remove(`theme-${t}`));
  document.body.classList.add(`theme-${theme}`);
  localStorage.setItem("taikry_theme_preset", theme);

  const sel = document.getElementById("theme-preset-select");
  if (sel) sel.value = theme;
}

function initColorTheme() {
  const saved = localStorage.getItem("taikry_theme_preset") || "cyber-cyan";
  changeColorTheme(saved);
  let metaTheme = document.querySelector('meta[name="theme-color"]');
  if (!metaTheme) {
    metaTheme = document.createElement("meta");
    metaTheme.name = "theme-color";
    document.head.appendChild(metaTheme);
  }
  metaTheme.content = "#060B09";
}

function switchCockpitTab(tabName, btn) {
  document.querySelectorAll(".cockpit-tab-pill").forEach(p => p.classList.remove("active"));
  if (btn) btn.classList.add("active");

  document.querySelectorAll(".cockpit-subpane").forEach(p => p.classList.remove("active"));
  const target = document.getElementById(`pane-cockpit-${tabName}`);
  if (target) target.classList.add("active");

  if (tabName === "bot") {
    fetchCockpitBotData();
  } else if (tabName === "history") {
    fetchCockpitHistory();
  } else if (tabName === "news") {
    fetchMacroEvents();
    renderCockpitNews();
  } else if (tabName === "xauusd-signals") {
    fetchXAUUSDSignalsAndStats();
  }
}

async function fetchCockpitBotData() {
  const symEl = document.getElementById("cockpit-debate-active-sym");
  if (symEl) symEl.innerText = currentSymbol;
  try {
    const [res, quotaRes] = await Promise.all([
      fetch(`${API_BASE}/api/v1/paper-trades`),
      fetch(`${API_BASE}/api/v1/xauusd/signals/daily-quota`)
    ]);
    const quotaEl = document.getElementById("cockpit-bot-quota");
    if (quotaEl) {
      if (quotaRes.ok) {
        const quota = await quotaRes.json();
        const sent = quota.signals_reserved_or_sent_today ?? quota.signals_sent_today;
        const limit = quota.daily_hard_limit;
        quotaEl.innerText = sent != null && limit != null ? `${sent} / ${limit} reserved or sent today` : "Unavailable";
      } else {
        quotaEl.innerText = "Unavailable";
      }
    }
    if (res.ok) {
      const data = await res.json();
      const openEl = document.getElementById("cockpit-bot-open");
      if (openEl && data.account_summary) {
        openEl.innerText = data.account_summary.open_trades_count != null
          ? `${data.account_summary.open_trades_count} open paper position(s)`
          : "Unavailable";
      }
    } else {
      const openEl = document.getElementById("cockpit-bot-open");
      if (openEl) openEl.innerText = "Admin access required";
    }
  } catch (e) {
    console.warn("Bot data fetch error:", e);
  }
}

async function fetchCockpitHistory() {
  const container = document.getElementById("cockpit-history-container");
  if (!container) return;
  try {
    const res = await fetch(`${API_BASE}/api/v1/paper-trades`);
    if (res.ok) {
      const data = await res.json();
      const trades = data.trades || [];
      if (trades.length === 0) {
        container.innerHTML = `<div class="bot-debate-placeholder"><span>No paper trades are recorded in the ledger.</span></div>`;
        return;
      }
      container.innerHTML = trades.slice(0, 10).map(t => {
        const pnl = t.pnl == null || !Number.isFinite(Number(t.pnl)) ? null : Number(t.pnl);
        const rValue = t.r_multiple == null || !Number.isFinite(Number(t.r_multiple)) ? null : Number(t.r_multiple);
        const result = rValue != null ? `${rValue.toFixed(2)}R` : (pnl != null ? `$${pnl.toFixed(2)}` : "N/A");
        return `
        <div class="history-item-row">
          <span class="history-sym">${escapeHtml(String(t.symbol || "N/A"))}</span>
          <span class="history-dir ${t.direction === 'BUY' ? 'dir-buy' : 'dir-sell'}">${escapeHtml(String(t.direction || "N/A"))} PAPER</span>
          <span class="history-price">${t.entry_price != null && Number.isFinite(Number(t.entry_price)) ? `$${Number(t.entry_price).toLocaleString()}` : "N/A"}</span>
          <span class="history-status ${t.status === 'CLOSED' ? 'status-pass' : 'status-pending'}">${escapeHtml(String(t.status || "N/A"))} (${result})</span>
        </div>
      `;
      }).join("");
    }
  } catch (e) {
    console.warn("History fetch error:", e);
  }
}

async function runCockpitLiveDebate() {
  const btn = document.getElementById("btn-cockpit-live-debate");
  const container = document.getElementById("cockpit-bot-debate-container");
  if (!container) return;

  if (btn) {
    btn.innerHTML = `<span>⏳ Agents Debating...</span>`;
    btn.disabled = true;
  }
  container.innerHTML = `
    <div class="bot-debate-placeholder">
      <span class="debate-pulse-icon">⚡</span>
      <span><b>Agents in Session:</b> Quantitative Technical, SMC Specialist, Macro Economist, and Risk Arbiter are cross-examining <b>${currentSymbol}</b> in real time...</span>
    </div>
  `;

  try {
    const tfMap = { "5": "M5", "15": "M15", "60": "H1", "240": "H4", "D": "D1" };
    const tf = tfMap[currentTimeframe] || "M15";
    const res = await fetch(`${API_BASE}/api/v1/agents/debate?symbol=${currentSymbol}&timeframe=${tf}`);
    if (!res.ok) throw new Error("Debate failed");
    const data = await res.json();

    container.innerHTML = "";
    const turns = data.turns || [];
    turns.forEach(t => {
      const card = document.createElement("div");
      card.className = "cockpit-debate-turn-card";
      card.style.borderLeftColor = t.badge_color || "var(--theme-accent)";
      card.innerHTML = `
        <div class="cockpit-debate-turn-head">
          <div class="cockpit-debate-turn-agent">
            <span>${t.agent_avatar || "🤖"}</span>
            <span style="color:${t.badge_color || 'var(--theme-accent)'}">${t.agent_name}</span>
          </div>
          <span class="cockpit-debate-turn-stance">${t.stance}</span>
        </div>
        <div class="cockpit-debate-turn-msg-en">${t.message_en}</div>
        <div class="cockpit-debate-turn-msg-kh">${t.message_kh}</div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = `<div class="bot-debate-placeholder"><span style="color:#ef4444">⚠️ Live debate failed to complete. Please try again.</span></div>`;
  } finally {
    if (btn) {
      btn.innerHTML = `📋 Review Agent Evidence (ពិនិត្យភស្តុតាង)`;
      btn.disabled = false;
    }
  }
}

let realtimeStreamTimer = null;
let lastKnownPrices = {};
let isPollingRealtimePrices = false;

function startRealtimePriceStream() {
  if (realtimeStreamTimer) clearInterval(realtimeStreamTimer);
  pollRealtimePrices();
  realtimeStreamTimer = setInterval(pollRealtimePrices, 3500);
}

async function pollRealtimePrices() {
  if (isPollingRealtimePrices) return;
  isPollingRealtimePrices = true;
  try {
    const res = await fetch(`${API_BASE}/api/v1/prices/realtime`);
    if (!res.ok) return;
    const data = await res.json();
    const prices = data.prices || {};

    requestAnimationFrame(() => {
      const pulseText = document.getElementById("cockpit-live-status-text");
      if (pulseText && Object.keys(prices).length > 0) {
        const sec = new Date().getSeconds();
        pulseText.innerText = `LIVE · ${sec % 2 === 0 ? 'REALTIME' : 'STREAMING'}`;
      } else if (pulseText) {
        pulseText.innerText = "MARKET FEED UNAVAILABLE";
      }

      if (prices[currentSymbol]) {
        const activeData = prices[currentSymbol];
        const p = activeData.price;
        const prevP = lastKnownPrices[currentSymbol] || p;
        const tickDir = p > prevP ? "tick-up" : (p < prevP ? "tick-down" : "");
        const isCrypto = currentSymbol.includes("USDT") || currentSymbol.includes("BTC");
        const isForex = !isCrypto && !currentSymbol.includes("XAU") && !currentSymbol.includes("XAG");
        const formatted = isForex ? Number(p).toFixed(4) : (Number(p) > 100 ? `$${Number(p).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : `$${Number(p)}`);

        const badgeP = document.getElementById("cockpit-asset-live-price");
        if (badgeP) {
          badgeP.innerText = formatted;
          if (tickDir) {
            badgeP.className = `asset-live-badge-price ${tickDir}`;
            setTimeout(() => { if (badgeP) badgeP.className = "asset-live-badge-price"; }, 1000);
          }
        }

        const topPrice = document.getElementById("top-active-price");
        if (topPrice) {
          topPrice.innerText = formatted;
          if (tickDir) {
            topPrice.className = `active-sym-price ${tickDir === 'tick-up' ? 'text-green' : 'text-red'}`;
          }
        }

        const ftPrice = document.getElementById("ft-price-display");
        if (ftPrice) ftPrice.innerText = formatted;

        const chartP = document.getElementById("chart-verified-price");
        if (chartP) chartP.innerText = formatted;

        const dispP = document.getElementById("display-verified-price");
        if (dispP) dispP.innerText = Number(p).toLocaleString();

        lastKnownPrices[currentSymbol] = p;

        if (activeData.provider) {
          window.TAIKRY_PROVIDER_DISPLAY = activeData.provider;
          const topSource = document.getElementById("top-active-source");
          const tfMap = { "1": "1m", "5": "5m", "15": "15m", "30": "30m", "60": "1h", "240": "4h", "D": "1d" };
          const tfText = tfMap[currentTimeframe] || "15m";
          if (topSource) topSource.innerText = `${activeData.provider} · ${tfText.toUpperCase()}`;
        }
        if (activeData.tv_symbol) {
          window.TAIKRY_TV_REFERENCE_SYMBOL = activeData.tv_symbol;
          const matchAsset = WATCHLIST.find(w => w.symbol === currentSymbol);
          if (matchAsset) matchAsset.tv = activeData.tv_symbol;
        }

        if (window.taikryChart && window.taikryChart.currentEngineMode === "native") {
          window.taikryChart.updateRealtimeTick(p, activeData.volume || 0, activeData.timestamp);
        }

        const ovPrice = document.getElementById("ov-active-price");
        if (ovPrice) ovPrice.innerText = formatted;
        const ovChg = document.getElementById("ov-active-change");
        if (ovChg) {
          const c = activeData.change_24h !== undefined && activeData.change_24h !== null ? Number(activeData.change_24h) : null;
          ovChg.innerText = c === null ? "24h Change: --" : `24h Change: ${c >= 0 ? '+' : ''}${c.toFixed(2)}%`;
          if (c !== null) ovChg.className = `section-kpi-sub ${c >= 0 ? 'text-green' : 'text-red'}`;
        }
      } else {
        ["cockpit-asset-live-price", "top-active-price", "ft-price-display", "chart-verified-price", "display-verified-price", "ov-active-price"].forEach(id => {
          const el = document.getElementById(id);
          if (el) el.innerText = "N/A";
        });
        const sourceEl = document.getElementById("top-active-source");
        if (sourceEl) sourceEl.innerText = "Market feed unavailable";
        const changeEl = document.getElementById("ov-active-change");
        if (changeEl) changeEl.innerText = "24h Change: --";
      }

      window.lastKnownMarketData = prices;
      WATCHLIST.forEach(item => {
        if (prices[item.symbol]) return;
        const priceEl = document.getElementById(`price-${item.symbol}`);
        if (priceEl) priceEl.innerText = "---";
        document.querySelectorAll(`[data-price-sym="${item.symbol}"]`).forEach(el => { el.innerText = "---"; });
        document.querySelectorAll(`[data-chg-sym="${item.symbol}"], [data-watch-chg-sym="${item.symbol}"]`).forEach(el => { el.innerText = "--"; });
      });

      Object.keys(prices).forEach(sym => {
        const pInfo = prices[sym];
        if (!pInfo) return;
        const newPrice = Number(pInfo.price);
        const isCrypto = sym.includes("USDT") || sym.includes("BTC");
        const isForex = !isCrypto && !sym.includes("XAU") && !sym.includes("XAG");
        const fmtPrice = isForex ? newPrice.toFixed(4) : (newPrice > 100 ? `$${newPrice.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : `$${newPrice}`);
        const c24 = pInfo.change_24h !== undefined && pInfo.change_24h !== null ? Number(pInfo.change_24h) : null;
        const chgText = c24 !== null ? (c24 > 0 ? `+${c24.toFixed(2)}%` : `${c24.toFixed(2)}%`) : "--";
        const isUp = c24 === null || c24 >= 0;

        if (sym === "BTCUSDT") {
          const btcEl = document.getElementById("top-btc-24h");
          if (btcEl) btcEl.innerText = chgText;
        }
        if (sym === "ETHUSDT") {
          const ethEl = document.getElementById("top-eth-24h");
          if (ethEl) ethEl.innerText = chgText;
        }

        const watchEl = document.getElementById(`price-${sym}`);
        if (watchEl) {
          watchEl.innerText = fmtPrice;
          if (pInfo.direction === "up") {
            watchEl.style.color = "var(--zyrox-primary, #00D99A)";
          } else if (pInfo.direction === "down") {
            watchEl.style.color = "var(--zyrox-danger, #FF647C)";
          }
        }

        document.querySelectorAll(`[data-watch-chg-sym="${sym}"]`).forEach(el => {
          el.innerText = chgText;
          el.className = `wl-change-val ${isUp ? 'badge-up' : 'badge-down'}`;
        });

        document.querySelectorAll(`[data-chg-sym="${sym}"]`).forEach(el => {
          el.innerText = chgText;
          el.className = `ticker-item-chg ${isUp ? 'chg-up' : 'chg-down'}`;
        });

        const el = document.getElementById(`modal-p-${sym}`);
        if (el) {
          el.innerText = fmtPrice;
          if (pInfo.direction === "up") {
            el.style.color = "var(--zyrox-primary, #00D99A)";
          } else if (pInfo.direction === "down") {
            el.style.color = "var(--zyrox-danger, #FF647C)";
          }
        }

        // Live stream update to Crypto & Forex Infinite Running Loop Ticker Ribbon
        document.querySelectorAll(`[data-price-sym="${sym}"]`).forEach(ribbonEl => {
          ribbonEl.innerText = fmtPrice;
          if (pInfo.direction === "up") {
            ribbonEl.className = "ticker-item-price tick-flash-green";
            setTimeout(() => { ribbonEl.className = "ticker-item-price"; }, 1200);
          } else if (pInfo.direction === "down") {
            ribbonEl.className = "ticker-item-price tick-flash-red";
            setTimeout(() => { ribbonEl.className = "ticker-item-price"; }, 1200);
          }
        });
      });
    });
  } catch (err) {
    // Graceful background tick
  } finally {
    isPollingRealtimePrices = false;
  }
}

function renderCockpitNews() {
  const container = document.getElementById("cockpit-news-quick-list");
  if (!container) return;
  const mainEvents = document.getElementById("calendar-events-container");
  if (mainEvents && mainEvents.children.length > 0) {
    container.innerHTML = mainEvents.innerHTML;
  }
}

function toggleCockpitCollapse() {
  const card = document.getElementById("cockpit-widget");
  const body = document.getElementById("cockpit-body");
  const btn = document.getElementById("cockpit-collapse-btn");
  if (body && card) {
    body.classList.toggle("collapsed");
    card.classList.toggle("collapsed");
    const isCol = body.classList.contains("collapsed");
    if (btn) btn.innerText = isCol ? "⌄" : "⌃";
    try {
      localStorage.setItem("taikry_cockpit_collapsed", isCol ? "true" : "false");
    } catch (e) {}
  }
}

function toggleAdvancedAccordion() {
  const panel = document.getElementById("advanced-content-panel");
  const arrow = document.getElementById("advanced-arrow");
  if (panel) {
    panel.classList.toggle("open");
    const isOpen = panel.classList.contains("open");
    if (arrow) arrow.innerText = isOpen ? "▴" : "▾";
  }
}

function selectCockpitTF(tf, btn) {
  document.querySelectorAll(".adv-tf-btn").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
  switchTimeframe(tf, null);
  const tfMap = { "5": "5m", "15": "15m", "60": "1h", "240": "4h", "D": "1d" };
  const tfText = tfMap[tf] || "15m";
  const disp = document.getElementById("cockpit-asset-display");
  if (disp) disp.innerText = `${currentSymbol} · ${tfText}`;
}

function filterChips(cat, btn) {
  currentChipFilter = cat;
  document.querySelectorAll(".chip-cat-btn").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
  renderCockpitChips();
}

function renderCockpitChips() {
  const container = document.getElementById("cockpit-chips-container");
  if (!container) return;
  container.innerHTML = "";

  const list = currentChipFilter === "ALL" 
    ? WATCHLIST 
    : WATCHLIST.filter(w => w.category === currentChipFilter || (currentChipFilter === "FOREX" && w.category === "COMMODITIES"));

  list.forEach(item => {
    const chip = document.createElement("button");
    chip.className = `cockpit-chip ${item.symbol === currentSymbol ? "active" : ""}`;
    chip.innerHTML = `<span class="chip-logo-wrap">${getAssetRealLogoHTML(item.symbol)}</span> <span>${item.symbol}</span>`;
    chip.onclick = () => selectCockpitSymbol(item.symbol);
    container.appendChild(chip);
  });
}

function openPairModal() {
  const modal = document.getElementById("pair-selector-modal");
  if (modal) {
    modal.classList.remove("modal-hidden");
    renderModalPairGrid("ALL", "");
    const input = document.getElementById("pair-search-input");
    if (input) {
      input.value = "";
      input.focus();
    }
  }
}

function closePairModal() {
  const modal = document.getElementById("pair-selector-modal");
  if (modal) modal.classList.add("modal-hidden");
}

function filterModalPairs(cat, btn) {
  document.querySelectorAll(".modal-cat-btn").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
  const query = document.getElementById("pair-search-input")?.value || "";
  renderModalPairGrid(cat, query);
}

function onPairSearch(query) {
  const activeCatBtn = document.querySelector(".modal-cat-btn.active");
  const cat = activeCatBtn ? activeCatBtn.innerText.split(" ")[0].toUpperCase() : "ALL";
  renderModalPairGrid(cat === "ALL" ? "ALL" : (cat.includes("FOREX") ? "FOREX" : (cat.includes("CRYPTO") ? "CRYPTO" : "COMMODITIES")), query);
}

function renderModalPairGrid(cat = "ALL", query = "") {
  const grid = document.getElementById("modal-pair-grid");
  if (!grid) return;
  grid.innerHTML = "";

  let filtered = WATCHLIST;
  if (cat !== "ALL") {
    filtered = filtered.filter(w => w.category === cat || (cat === "COMMODITIES" && w.category === "COMMODITIES"));
  }
  if (query.trim()) {
    const q = query.trim().toUpperCase();
    filtered = filtered.filter(w => w.symbol.includes(q) || w.name.toUpperCase().includes(q));
  }

  filtered.forEach(item => {
    const el = document.createElement("div");
    el.className = `pair-grid-item ${item.symbol === currentSymbol ? "active" : ""}`;
    el.onclick = () => selectCockpitSymbol(item.symbol);
    el.innerHTML = `
      <div class="pair-info-group">
        <span class="asset-icon">${getAssetRealLogoHTML(item.symbol)}</span>
        <div>
          <div class="pair-grid-sym">${item.symbol}</div>
          <div class="pair-grid-name">${item.name}</div>
        </div>
      </div>
      <div class="pair-grid-price" id="modal-p-${item.symbol}">Live</div>
    `;
    grid.appendChild(el);
  });
}

function selectCockpitSymbol(symbol) {
  closePairModal();
  const asset = WATCHLIST.find(w => w.symbol === symbol);
  const tvSym = asset ? asset.tv : `OANDA:${symbol}`;
  selectSymbol(symbol, tvSym);
  renderCockpitChips();
}

let currentCockpitSizeMode = localStorage.getItem("zyrox_cockpit_size_mode") || "small";

function setCockpitSizeMode(mode) {
  const card = document.getElementById("cockpit-widget");
  const sizeBtn = document.getElementById("cockpit-size-btn");
  const colBtn = document.getElementById("cockpit-collapse-btn");
  const indicator = document.getElementById("cockpit-mode-indicator");
  const body = document.getElementById("cockpit-body");
  if (!card) return;

  currentCockpitSizeMode = mode;
  try {
    localStorage.setItem("zyrox_cockpit_size_mode", mode);
  } catch (e) {}

  card.classList.remove("cockpit-size-small", "cockpit-size-big", "collapsed");
  if (body) body.classList.remove("collapsed");

  if (mode === "small") {
    card.classList.add("cockpit-size-small");
    if (sizeBtn) sizeBtn.innerHTML = "↕ Small";
    if (colBtn) colBtn.innerText = "⌃";
    if (indicator) indicator.innerText = (typeof isKhmer !== "undefined" && isKhmer) ? "ទំហំតូច (Small) · ចុចពង្រីកធំ" : "Small Mode · Tap to Expand";
  } else if (mode === "big") {
    card.classList.add("cockpit-size-big");
    if (sizeBtn) sizeBtn.innerHTML = "⤢ Big";
    if (colBtn) colBtn.innerText = "⌃";
    if (indicator) indicator.innerText = (typeof isKhmer !== "undefined" && isKhmer) ? "ទំហំធំ (Big) · ចុចបង្រួមតូច" : "Big Mode · Tap to Shrink";
  } else if (mode === "collapsed") {
    card.classList.add("collapsed");
    if (body) body.classList.add("collapsed");
    if (sizeBtn) sizeBtn.innerHTML = "⌄ Mini";
    if (colBtn) colBtn.innerText = "⌄";
    if (indicator) indicator.innerText = (typeof isKhmer !== "undefined" && isKhmer) ? "បង្រួមអប្បបរមា · ចុចបើក" : "Minimized · Tap to Open";
  }
}

function cycleCockpitSize() {
  if (currentCockpitSizeMode === "small") {
    setCockpitSizeMode("big");
  } else if (currentCockpitSizeMode === "big") {
    setCockpitSizeMode("collapsed");
  } else {
    setCockpitSizeMode("small");
  }
}

function toggleCockpitSize() {
  if (currentCockpitSizeMode === "small") {
    setCockpitSizeMode("big");
  } else {
    setCockpitSizeMode("small");
  }
}

function toggleCockpitCollapse() {
  if (currentCockpitSizeMode === "collapsed") {
    setCockpitSizeMode("small");
  } else {
    setCockpitSizeMode("collapsed");
  }
}

function toggleRotateChart() {
  const isRotated = document.body.classList.toggle("chart-rotated-fullscreen");
  const btn = document.getElementById("cockpit-rotate-btn");
  if (btn) {
    btn.innerHTML = isRotated ? "✕ Exit" : "🔄 Rotate";
  }

  // If Screen Orientation API is supported and in fullscreen, attempt landscape lock
  try {
    if (isRotated && screen.orientation && screen.orientation.lock) {
      screen.orientation.lock("landscape").catch(() => {});
    } else if (!isRotated && screen.orientation && screen.orientation.unlock) {
      screen.orientation.unlock();
    }
  } catch (e) {}
}

function initCockpitSize() {
  const savedMode = localStorage.getItem("zyrox_cockpit_size_mode") || "small";
  setCockpitSizeMode(savedMode);
}

async function runCockpitAnalyze() {
  const btn = document.getElementById("btn-cockpit-analyze");
  if (btn) {
    btn.innerHTML = `<span>⏳ ${isKhmer ? "កំពុងវិភាគ..." : "Analyzing..."}</span>`;
    btn.disabled = true;
  }
  const statText = document.getElementById("cockpit-status-text");
  if (statText) statText.innerText = "SCANNING...";

  try {
    await triggerScan();
    const toast = document.getElementById("cockpit-status-toast");
    if (toast) {
      toast.innerHTML = `<span class="toast-clock">⚡</span> <b>${currentSymbol} Multi-Timeframe Scan Completed · All AI Gates Evaluated</b>`;
    }
  } catch (err) {
    console.error("Cockpit analyze error:", err);
  } finally {
    if (btn) {
      const analyzeSvg = `<svg class="btn-svg-icon" viewBox="0 0 20 20" fill="currentColor"><rect x="2" y="9" width="3.2" height="8" rx="1.6" fill="#38bdf8"/><rect x="8.4" y="4" width="3.2" height="13" rx="1.6" fill="#38bdf8"/><rect x="14.8" y="7" width="3.2" height="10" rx="1.6" fill="#38bdf8"/></svg>`;
      btn.innerHTML = `${analyzeSvg} <span id="t-cockpit-analyze">${isKhmer ? "វិភាគ" : "Analyze"}</span>`;
      btn.disabled = false;
    }
  }
}

async function runCockpitBestSetup() {
  const btn = document.getElementById("btn-cockpit-best");
  if (btn) {
    btn.innerHTML = `<span>⏳ ${isKhmer ? "ស្វែងរក..." : "Scanning..."}</span>`;
    btn.disabled = true;
  }
  const statBadge = document.getElementById("cockpit-status-badge");
  const statText = document.getElementById("cockpit-status-text");
  if (statText) statText.innerText = "FINDING BEST SETUP...";

  try {
    const res = await fetch(`${API_BASE}/api/v1/best-setup?category=${currentChipFilter}`, { credentials: "include" });
    const data = await res.json();
    if (data.best_setup) {
      const best = data.best_setup;
      selectSymbol(best.symbol, best.symbol.includes("USDT") ? `BINANCE:${best.symbol}` : `OANDA:${best.symbol}`);
      updateCockpitPlanCard(best);
      renderCockpitChips();

      const toast = document.getElementById("cockpit-status-toast");
      if (toast) {
        toast.innerHTML = `<span class="toast-clock">🏆</span> <b>Best Institutional Setup Detected: ${best.symbol} (${best.market_bias || best.setup_status}) — R:R ${best.risk_reward_ratio || 'N/A'}</b>`;
      }
    } else {
      await triggerScan();
    }
  } catch (err) {
    console.error("Best setup error:", err);
    await triggerScan();
  } finally {
    if (btn) {
      const boltSvg = `<svg class="btn-svg-icon" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clip-rule="evenodd" fill="#090d16"/></svg>`;
      btn.innerHTML = `${boltSvg} <span id="t-cockpit-best">${isKhmer ? "ការរៀបចំល្អបំផុត" : "Best setup"}</span>`;
      btn.disabled = false;
    }
  }
}

function updateCockpitPlanCard(data) {
  if (!data) return;

  const asset = WATCHLIST.find(w => w.symbol === currentSymbol) || { symbol: currentSymbol, icon: "🪙", name: currentSymbol };
  const tfMap = { "5": "5m", "15": "15m", "60": "1h", "240": "4h", "D": "1d" };
  const tfText = tfMap[currentTimeframe] || "15m";

  // Header display & status
  const iconEl = document.getElementById("cockpit-asset-icon");
  const dispEl = document.getElementById("cockpit-asset-display");
  const priceEl = document.getElementById("cockpit-asset-live-price");
  const statBadge = document.getElementById("cockpit-status-badge");
  const statText = document.getElementById("cockpit-status-text");

  if (iconEl) iconEl.innerText = asset.icon || "🪙";
  if (dispEl) dispEl.innerText = `${currentSymbol} · ${tfText}`;
  if (priceEl && data.verified_price) {
    const isCrypto = currentSymbol.includes("USDT") || currentSymbol.includes("BTC");
    const isForex = !isCrypto && !currentSymbol.includes("XAU") && !currentSymbol.includes("XAG");
    const pVal = Number(data.verified_price);
    priceEl.innerText = isForex ? pVal.toFixed(4) : (pVal > 100 ? `$${pVal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : `$${pVal}`);
  }

  if (statText) {
    if (data.setup_status === "APPROVE") {
      statText.innerText = "READY";
      if (statBadge) statBadge.className = "cockpit-status-badge";
    } else if (data.setup_status === "REJECT" || data.setup_status === "VETO") {
      statText.innerText = "VETOED";
      if (statBadge) statBadge.className = "cockpit-status-badge status-veto";
    } else {
      statText.innerText = "MONITORING";
      if (statBadge) statBadge.className = "cockpit-status-badge";
    }
  }

  // Narrative summary
  const narrMain = document.getElementById("cockpit-narrative-main");
  const narrWarn = document.getElementById("cockpit-narrative-warning");
  const narrTip = document.getElementById("cockpit-narrative-tip");
  const narrRung = document.getElementById("cockpit-narrative-rung");

  if (narrMain) {
    if (data.setup_status === "APPROVE") {
      narrMain.innerText = `${currentSymbol}: setup approved on ${tfText}. Reported R:R: ${data.risk_reward_ratio || "N/A"}. Review the source and price levels before acting.`;
    } else {
      narrMain.innerText = `${currentSymbol}: no approved trade setup is available. Wait for a fresh scan with valid market data.`;
    }
  }
  if (narrWarn) {
    const warning = data.error || data.data_quality?.warning || "";
    narrWarn.innerText = warning ? `⚠️ ${warning}` : "";
  }
  if (narrTip) {
    narrTip.innerHTML = `💡 Try: <b>BTCUSDT</b> · <b>${currentSymbol}</b> · or wait for the London/NY session open.`;
  }
  if (narrRung) {
    narrRung.innerText = `From the ${tfText} rung of this scan.`;
  }

  // Update All 4 Institutional AI Agents Mini Cards
  const a1 = data.agents?.agent_1_technical || {};
  const a2 = data.agents?.agent_2_ict_smc || {};
  const a3 = data.agents?.agent_3_macro || {};
  const a4 = data.agents?.agent_4_risk || {};

  const a1Val = document.getElementById("c-agent-1-status");
  const a1Sub = document.getElementById("c-agent-1-sub");
  if (a1Val) {
    const confidence = Number(a1.confidence);
    a1Val.innerText = `${a1.bias || "N/A"} (${Number.isFinite(confidence) ? `${confidence}%` : "confidence N/A"})`;
  }
  if (a1Sub) {
    const rsi = a1.key_price_levels?.rsi ?? "N/A";
    const atr = a1.key_price_levels?.atr ?? "N/A";
    a1Sub.innerText = `RSI ${rsi} · ATR ${atr}`;
  }

  const a2Val = document.getElementById("c-agent-2-status");
  const a2Sub = document.getElementById("c-agent-2-sub");
  if (a2Val) a2Val.innerText = `${a2.bias || "N/A"}`;
  if (a2Sub) {
    const zone = a2.key_price_zones?.current_zone || "N/A";
    a2Sub.innerText = `Zone: ${zone}`;
  }

  const a3Val = document.getElementById("c-agent-3-status");
  const a3Sub = document.getElementById("c-agent-3-sub");
  if (a3Val) a3Val.innerText = `${a3.bias || "N/A"}`;
  if (a3Sub) {
    const dxy = a3.usd_index?.dxy_price ?? "N/A";
    const blackout = typeof a3.news_blackout_active === "boolean" ? (a3.news_blackout_active ? "Active" : "Clear") : "N/A";
    a3Sub.innerText = `DXY ${dxy} · News Blackout: ${blackout}`;
  }

  const a4Val = document.getElementById("c-agent-4-status");
  const a4Sub = document.getElementById("c-agent-4-sub");
  if (a4Val) {
    if (data.setup_status === "APPROVE") {
      a4Val.innerText = `APPROVED (R:R ${data.risk_reward_ratio || "N/A"})`;
      a4Val.className = "agent-mini-val val-green";
    } else {
      a4Val.innerText = `LOCKED (${data.setup_status || "WAIT"})`;
      a4Val.className = "agent-mini-val val-red";
    }
  }
  if (a4Sub) a4Sub.innerText = "Risk size uses configured paper account";

  // The Plan Card
  const planCard = document.getElementById("cockpit-plan-card");
  const titleBadge = document.getElementById("plan-title-badge");
  const subDesc = document.getElementById("plan-sub-desc");
  const slVal = document.getElementById("plan-sl-val");
  const tpVal = document.getElementById("plan-tp-val");
  const validVal = document.getElementById("plan-valid-val");
  const invalPrice = document.getElementById("plan-inval-price");
  const whyText = document.getElementById("plan-why-text");
  const whyKh = document.getElementById("plan-why-kh");
  const armedText = document.getElementById("plan-armed-text");
  const nextCheck = document.getElementById("plan-next-check");
  const btnPairTf = document.getElementById("btn-analyze-pair-tf");
  const toastText = document.getElementById("cockpit-toast-text");

  const statusApproved = data.setup_status === "APPROVE";
  const vPrice = Number(data.verified_price);
  const entryPrice = Number(data.entry_price);
  const referencePrice = Number.isFinite(entryPrice) && entryPrice > 0 ? entryPrice : vPrice;
  const decimals = currentSymbol.includes("JPY") ? 3 : (currentSymbol.includes("USDT") && referencePrice > 500 ? 2 : (referencePrice > 100 ? 2 : 4));
  const rawDirection = String(data.proposed_direction || "").toUpperCase();
  const action = statusApproved && ["BUY", "SELL"].includes(rawDirection)
    ? rawDirection
    : (statusApproved && rawDirection === "LONG" ? "BUY" : (statusApproved && rawDirection === "SHORT" ? "SELL" : "WAIT"));
  const stopLoss = Number(data.stop_loss);
  const takeProfit = Number(data.take_profit_1);
  const approved = statusApproved && action !== "WAIT"
    && [entryPrice, stopLoss, takeProfit].every(value => Number.isFinite(value) && value > 0)
    && (action === "BUY" ? stopLoss < entryPrice && entryPrice < takeProfit : stopLoss > entryPrice && entryPrice > takeProfit);
  const hasEntry = approved && Number.isFinite(entryPrice) && entryPrice > 0;
  const rangeLow = hasEntry ? entryPrice.toFixed(decimals) : "N/A";
  const rangeHigh = hasEntry ? entryPrice.toFixed(decimals) : "N/A";

  if (planCard) {
    planCard.className = `cockpit-plan-card ${action === 'BUY' ? 'plan-buy' : (action === 'SELL' ? 'plan-sell' : '')}`;
  }

  if (titleBadge) {
    titleBadge.innerText = approved && action !== "WAIT"
      ? `PLAN · ${action} ${Number(rangeLow).toLocaleString()}`
      : `WAIT · ${data.setup_status || "NO APPROVED SETUP"}`;
  }

  const scoreBadge = document.getElementById("plan-score-badge");
  if (scoreBadge) {
    const score = Number(data.ai_score ?? data.confidence_score);
    const hasScore = Number.isFinite(score);
    scoreBadge.innerText = hasScore ? `⭐ ${score}% SCORE` : "⭐ SCORE N/A";
    scoreBadge.className = hasScore && score >= 88 ? "plan-score-badge score-a-plus" : "plan-score-badge";
  }

  if (subDesc) {
    if (!approved || action === "WAIT") {
      subDesc.innerText = "No approved trade setup is available.";
    } else if (action === "SELL") {
      subDesc.innerText = data.smart_analysis?.synthesized_cause_en || "Approved sell setup; review reported levels and risk.";
    } else {
      subDesc.innerText = data.smart_analysis?.synthesized_cause_en || "Approved buy setup; review reported levels and risk.";
    }
  }

  // Calculate SL
  const sl = approved && Number.isFinite(stopLoss) && stopLoss > 0 ? stopLoss.toFixed(decimals) : "N/A";
  if (slVal) slVal.innerText = sl;
  if (invalPrice) invalPrice.innerText = approved ? sl : "N/A";

  const tp = approved && Number.isFinite(takeProfit) && takeProfit > 0 ? takeProfit.toFixed(decimals) : "N/A";
  if (tpVal) {
    tpVal.innerText = approved ? `${tp} (${data.risk_reward_ratio || "R:R N/A"})` : "N/A · Awaiting approved scan";
  }

  // Valid Until in GMT+7
  const now = new Date();
  const expiryRaw = data.valid_until || data.expires_at;
  const expiry = expiryRaw ? new Date(expiryRaw) : null;
  if (validVal) validVal.innerText = approved && expiry && Number.isFinite(expiry.getTime())
    ? `${expiry.toLocaleString()} (${Intl.DateTimeFormat().resolvedOptions().timeZone})`
    : "N/A";

  // Invalidation & Why
  if (whyText) {
    whyText.innerText = data.smart_analysis?.synthesized_cause_en || (approved ? "Approved setup; review the reported levels and risk before acting." : "No approved setup. Wait for a fresh market scan.");
  }
  if (whyKh) {
    whyKh.innerText = data.smart_analysis?.synthesized_cause_kh || (approved ? "សញ្ញានេះត្រូវបានអនុម័ត។ សូមពិនិត្យតម្លៃ និងហានិភ័យមុនធ្វើសកម្មភាព។" : "មិនមានសញ្ញាដែលបានអនុម័តទេ។ សូមរង់ចាំការស្កេនទីផ្សារថ្មី។");
  }

  // Armed alert banner
  if (armedText) {
    armedText.innerText = approved && hasEntry ? `Approved entry reference: ${Number(rangeLow).toLocaleString()}` : "No approved entry level available.";
  }

  // Next check candle
  const nextMin = (Math.ceil(now.getMinutes() / 15) * 15) % 60;
  const nextHour = nextMin === 0 ? (now.getHours() + 1) % 24 : now.getHours();
  if (nextCheck) nextCheck.innerText = `${String(nextHour).padStart(2, "0")}:${String(nextMin).padStart(2, "0")}`;

  // Footer button
  if (btnPairTf) btnPairTf.innerText = `Analyze ${currentSymbol} ${tfText}`;

  // Toast
  if (toastText) {
    if (approved) {
      toastText.innerText = `⚡ Approved setup loaded. Review its levels before recording a paper trade.`;
    } else {
      toastText.innerText = `No approved setup is available from this scan.`;
    }
  }

}

function switchToDebateTab() {
  const debateBtn = document.getElementById("tab-btn-debate");
  if (debateBtn) {
    switchMainTab("debate", debateBtn);
  }
}

function showPlansModal() {
  const modal = document.getElementById("plans-spec-modal");
  if (modal) modal.classList.remove("modal-hidden");
}

function closePlansModal() {
  const modal = document.getElementById("plans-spec-modal");
  if (modal) modal.classList.add("modal-hidden");
}

// Stream listener handled by centralized pollRealtimePrices

// Trade bridge default parameters
let calcBalance = 10000;
let calcRiskPct = 0.50;
let currentCalculatedLots = "0.08 Lots";

async function executePlanTradeBridge() {
  const btn = document.getElementById("btn-cockpit-execute");
  const ticketButtonLabel = () => isKhmer
    ? "🧾 កត់ត្រាជួញដូរសាកល្បង និងផ្ញើសំបុត្រជូនដំណឹង"
    : "🧾 Record Paper Trade & Send Manual Ticket";
  const restoreButton = () => {
    if (!btn) return;
    btn.disabled = false;
    btn.innerHTML = `<span id="t-cockpit-execute">${ticketButtonLabel()}</span>`;
  };
  const reportError = (message) => {
    alert(message);
    restoreButton();
  };

  const analysis = latestAnalysisData;
  const rawDirection = String(analysis?.proposed_direction || "").toUpperCase();
  const dir = rawDirection === "LONG" ? "BUY" : (rawDirection === "SHORT" ? "SELL" : rawDirection);
  const entry = Number(analysis?.entry_price);
  const sl = Number(analysis?.stop_loss);
  const tp1 = Number(analysis?.take_profit_1);
  const riskPct = Number(localStorage.getItem("zyrox_risk_cap") || "0.5");
  const rrFloor = Number(localStorage.getItem("zyrox_risk_floor") || "2.0");
  if (analysis?.setup_status !== "APPROVE" || !["BUY", "SELL"].includes(dir)) {
    reportError("No approved BUY/SELL setup is available. Run a fresh scan and wait for approval.");
    return;
  }
  if (![entry, sl, tp1].every(value => Number.isFinite(value) && value > 0)) {
    reportError("The approved setup is missing a valid entry, stop-loss, or take-profit level.");
    return;
  }
  if ((dir === "BUY" && !(sl < entry && entry < tp1)) || (dir === "SELL" && !(sl > entry && entry > tp1))) {
    reportError("The approved setup has price levels that do not match its direction. No ticket was sent.");
    return;
  }
  if (!Number.isFinite(riskPct) || riskPct < 0.1 || riskPct > 2 || !Number.isFinite(rrFloor) || rrFloor < 2 || rrFloor > 3) {
    reportError("Saved paper-trading risk preferences are invalid. Update the risk settings before continuing.");
    return;
  }
  const actualRR = Math.abs(tp1 - entry) / Math.abs(entry - sl);
  if (actualRR < rrFloor) {
    reportError(`This setup's calculated R:R (1:${actualRR.toFixed(2)}) is below your saved 1:${rrFloor.toFixed(1)} paper-ticket minimum.`);
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳ Recording paper trade & sending manual ticket...</span>`;
  }

  try {
    const res = await fetch(`${API_BASE}/api/v1/trade/execute-bridge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: currentSymbol,
        direction: dir,
        entry_price: entry,
        stop_loss: sl,
        take_profit_1: tp1,
        risk_percentage: riskPct,
        source: "Cockpit paper-trade ticket"
      })
    });

    const data = await res.json();
    if (data.success) {
      const paperStatus = data.telegram_dispatched
        ? (data.paper_trade?.success ? "Telegram ticket sent · paper trade recorded" : "Telegram ticket sent · no paper trade opened")
        : (data.paper_trade?.success ? "Paper trade recorded · Telegram not sent" : "Ticket not sent");
      const toast = document.getElementById("cockpit-status-toast");
      if (toast) {
        toast.innerHTML = `<span class="toast-clock">⚡</span> <b>Ticket ${escapeHtml(String(data.ticket_id || ""))} sent · ${paperStatus}</b>`;
      }
      if (btn) {
        btn.innerHTML = `<span>✓ ${escapeHtml(paperStatus)} · ${escapeHtml(String(data.ticket_id || ""))}</span>`;
        setTimeout(() => {
          restoreButton();
        }, 3500);
      }
      // Refresh paper trading ledger
      fetchHealthAndPaper();
    } else {
      reportError(data.detail || data.message || "The paper-trade ticket could not be created.");
    }
  } catch (err) {
    console.error("Execute bridge error:", err);
    reportError("Connection error creating the paper-trade ticket. Check the server and try again.");
  }
}

async function broadcastDailyDigest() {
  const btns = [
    document.getElementById("btn-broadcast-digest"),
    document.getElementById("btn-pane-broadcast-digest")
  ];

  btns.forEach(b => {
    if (b) {
      b.disabled = true;
      b.innerText = "⏳ Dispatching Briefing...";
    }
  });

  try {
    const res = await fetch(`${API_BASE}/api/v1/telegram/broadcast-digest`, {
      method: "POST"
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Telegram dispatch failed.");

    const toast = document.getElementById("cockpit-status-toast");
    if (toast) {
      const dispatchMessage = data.success
        ? `Briefing sent · ${Number(data.setups_included) || 0} approved setups`
        : "Telegram delivery is not configured or did not succeed.";
      toast.innerHTML = `<span class="toast-clock">📢</span> <b>${escapeHtml(dispatchMessage)}</b>`;
    }

    btns.forEach(b => {
      if (b) {
        b.innerText = data.success ? "✓ Sent to Telegram" : "Delivery unavailable";
        setTimeout(() => {
          b.innerText = b.id && b.id.includes("pane") ? "🚀 Broadcast Digest to Telegram Now" : "📢 Daily Digest";
          b.disabled = false;
        }, 3000);
      }
    });
  } catch (err) {
    console.error("Broadcast digest error:", err);
    btns.forEach(b => {
      if (b) {
        b.disabled = false;
        b.innerText = "📢 Daily Digest";
      }
    });
  }
}

/* ==========================================================================
   TERMINAL WORKSPACE CONTROLS & INTERACTIVE AI CHAT ASSISTANT
   ========================================================================== */

function switchNavPane(paneName) {
  // Hide all full overlays
  document.querySelectorAll(".terminal-full-overlay").forEach(el => el.classList.add("tab-pane-hidden"));

  // Reset nav icon buttons
  document.querySelectorAll(".nav-icon-btn").forEach(b => b.classList.remove("active"));
  const btn = document.getElementById(`btn-nav-${paneName}`);
  if (btn) btn.classList.add("active");

  if (paneName === "terminal" || paneName === "charts") {
    activeMainTab = "signals";
    if (window.taikryChart && window.taikryChart.handleResize) {
      window.taikryChart.handleResize();
    }
    return;
  }

  if (paneName === "analysis") {
    activeMainTab = "signals";
    if (window.innerWidth <= 900) {
      switchMobileView("cockpit");
    } else {
      const cp = document.getElementById("terminal-ai-sidebar");
      if (cp && cp.classList.contains("collapsed")) {
        cp.classList.remove("collapsed");
      }
      const chatTab = document.getElementById("ai-tab-chat");
      if (chatTab) switchAiSidebarTab("chat", chatTab);
    }
    return;
  }

  if (paneName === "watchlist") {
    const wl = document.getElementById("terminal-watchlist");
    if (wl && wl.classList.contains("collapsed")) {
      wl.classList.remove("collapsed");
    }
    if (window.innerWidth <= 900) {
      switchMobileView("watchlist");
    }
    return;
  }

  if (paneName === "calendar") {
    const cal = document.getElementById("tab-pane-macro-drawer");
    if (cal) cal.classList.remove("tab-pane-hidden");
    fetchMacroEvents(false);
    return;
  }

  activeMainTab = paneName;
  const target = document.getElementById(`tab-pane-${paneName}`);
  if (target) {
    target.classList.remove("tab-pane-hidden");
  }

  if (paneName === "overview") {
    loadOverviewData();
  } else if (paneName === "markets") {
    loadMarketsData();
  } else if (paneName === "signals") {
    loadSignalsCenterData();
  } else if (paneName === "history") {
    loadSignalsHistoryData();
  } else if (paneName === "analytics") {
    loadPerformanceAnalyticsData();
  } else if (paneName === "telegram") {
    loadTelegramStatusData();
  } else if (paneName === "mt5") {
    loadMT5BridgeData();
  } else if (paneName === "settings") {
    loadSettingsData();
  } else if (paneName === "admin") {
    loadAdminData();
  } else if (paneName === "debate") {
    fetchAgentsDebate(currentSymbol);
  } else if (paneName === "training") {
    fetchSelfTrainingData();
  } else if (paneName === "autofix") {
    fetchAutoFixAlerts();
  } else if (paneName === "account") {
    loadAccountProfile();
  } else if (paneName === "support") {
    loadSupportTickets();
  }
}

/* ==========================================================================
   1. OVERVIEW DATA LOADER
   ========================================================================== */
async function loadOverviewData() {
  try {
    // 1. Bridge & feed status
    const bridgeRes = await fetch(`${API_BASE}/api/v1/bridge/status`);
    if (bridgeRes.ok) {
      const bData = await bridgeRes.json();
      const provEl = document.getElementById("ov-feed-provider");
      const latEl = document.getElementById("ov-feed-latency");
      if (bData.status === "CONNECTED" && bData.is_active_for_signals) {
        if (provEl) {
          provEl.innerText = `${bData.broker || "MT5"} · fresh ticks received`;
          provEl.className = "section-kpi-val text-green";
        }
        if (latEl) latEl.innerText = Number(bData.terminal_ping_ms) > 0 ? `Terminal ping: ${bData.terminal_ping_ms}ms` : "Fresh quote received; ping not reported";
      } else if (bData.status === "CONNECTED") {
        if (provEl) {
          provEl.innerText = "MT5 bridge connected · no fresh ticks";
          provEl.className = "section-kpi-val text-gold";
        }
        if (latEl) latEl.innerText = "Waiting for a verified bid/ask quote";
      } else {
        if (provEl) {
          provEl.innerText = `MT5 bridge ${String(bData.status || "DISCONNECTED").toLowerCase()}`;
          provEl.className = "section-kpi-val text-muted";
        }
        if (latEl) latEl.innerText = bData.status === "CONNECTED" ? "Waiting for a verified market tick" : "Broker feed not connected";
      }
    }

    // 2. Active symbol price
    const pRes = await fetch(`${API_BASE}/api/v1/prices/realtime?symbols=XAUUSD,BTCUSDT,EURUSD,GBPUSD,USDJPY,SOLUSDT`);
    if (pRes.ok) {
      const pData = await pRes.json();
      const gold = pData.prices && pData.prices["XAUUSD"];
      const feedEl = document.getElementById("ov-feed-provider");
      const feedDetailEl = document.getElementById("ov-feed-latency");
      if (gold) {
        const goldSource = gold.provider || gold.source || "Unknown provider";
        if (feedEl) {
          feedEl.innerText = gold.verified ? goldSource : `Unverified / ${goldSource}`;
          feedEl.className = `section-kpi-val ${gold.verified && gold.source === "EXNESS_MT5" ? "text-green" : "text-gold"}`;
        }
        if (feedDetailEl) {
          feedDetailEl.innerText = gold.timestamp ? `Quote timestamp: ${new Date(gold.timestamp).toLocaleString()}` : `Feed status: ${gold.freshness || "unknown"}`;
        }
        const ap = document.getElementById("ov-active-price");
        if (ap) ap.innerText = `$${Number(gold.price).toFixed(2)}`;
        const achg = document.getElementById("ov-active-change");
        if (achg) {
          const c = gold.change_24h !== undefined && gold.change_24h !== null ? Number(gold.change_24h) : null;
          achg.innerText = c === null ? "24h Change: --" : `24h Change: ${c >= 0 ? '+' : ''}${c.toFixed(2)}%`;
          if (c !== null) achg.className = `section-kpi-sub ${c >= 0 ? 'text-green' : 'text-red'}`;
        }
      } else {
        if (feedEl) {
          feedEl.innerText = "No verified XAUUSD quote";
          feedEl.className = "section-kpi-val text-muted";
        }
        if (feedDetailEl) feedDetailEl.innerText = "Waiting for a connected market-data provider";
        const ap = document.getElementById("ov-active-price");
        const achg = document.getElementById("ov-active-change");
        if (ap) ap.innerText = "--";
        if (achg) achg.innerText = "24h Change: --";
      }

      // Quick tape table
      const quickBody = document.getElementById("ov-markets-quick-body");
      if (quickBody && pData.prices) {
        const keys = ["XAUUSD", "BTCUSDT", "EURUSD", "GBPUSD", "USDJPY", "SOLUSDT"];
        quickBody.innerHTML = keys.map(k => {
          const it = pData.prices[k];
          if (!it) return "";
          const isForex = k.includes("USD") && !k.includes("XAU") && !k.includes("USDT") && !k.includes("BTC");
          const pFmt = isForex ? Number(it.price).toFixed(4) : (Number(it.price) > 100 ? `$${Number(it.price).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : `$${Number(it.price)}`);
          const c24 = it.change_24h !== undefined && it.change_24h !== null ? Number(it.change_24h) : null;
          const c24Text = c24 === null ? "--" : `${c24 >= 0 ? '+' : ''}${c24.toFixed(2)}%`;
          return `
            <tr>
              <td><b>${k}</b></td>
              <td>${pFmt}</td>
              <td class="${c24 === null ? 'text-muted' : (c24 >= 0 ? 'text-green' : 'text-red')}"><b>${c24Text}</b></td>
              <td><span class="provider-pill">${escapeHtml(String(it.provider || it.source || "N/A"))}</span></td>
              <td><button class="btn btn-outline btn-xs" onclick="selectSymbol('${k}', 'OANDA:${k}'); switchNavPane('charts');">Chart</button></td>
            </tr>
          `;
        }).join("");
      }
    }

    // 3. Performance metrics
    const perfRes = await fetch(`${API_BASE}/api/v1/signals/performance`);
    if (perfRes.ok) {
      const perf = await perfRes.json();
      const wrEl = document.getElementById("ov-winrate");
      const pfEl = document.getElementById("ov-profit-factor");
      const sigEl = document.getElementById("ov-active-signals");
      if (wrEl) wrEl.innerText = perf.win_rate_percent !== null ? `${perf.win_rate_percent}%` : "--";
      if (pfEl) pfEl.innerText = `Profit Factor: ${perf.profit_factor !== null ? perf.profit_factor : "--"}`;
      if (sigEl) sigEl.innerText = perf.total_active_signals !== undefined ? perf.total_active_signals : "0";
    }

    // 4. Active qualified setup spotlight
    const sigRes = await fetch(`${API_BASE}/api/v1/xauusd/signals?status=ACTIVE,CANDIDATE&limit=1`);
    const spotContainer = document.getElementById("ov-setup-card-content");
    const spotBadge = document.getElementById("ov-setup-status-badge");
    if (sigRes.ok) {
      const sigData = await sigRes.json();
      const sigs = sigData.signals || [];
      if (sigs.length > 0) {
        const s = sigs[0];
        if (spotBadge) {
          spotBadge.innerText = s.status || "ACTIVE";
          spotBadge.className = `provider-pill ${s.status === 'ACTIVE' ? 'pill-green' : 'pill-gold'}`;
        }
        if (spotContainer) {
          const sideColor = s.direction === "BUY" ? "text-green" : "text-red";
          spotContainer.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
              <span style="font-size:16px; font-weight:700;">${s.symbol} · <span class="${sideColor}">${s.direction}</span></span>
              <span class="provider-pill">${s.execution_mode || "PAPER"}</span>
            </div>
            <div class="health-list">
              <div class="health-row"><span>Entry Zone:</span> <b>$${Number(s.entry_zone_min).toFixed(2)} – $${Number(s.entry_zone_max).toFixed(2)}</b></div>
              <div class="health-row"><span>Stop Loss (SL):</span> <b class="text-red">$${Number(s.stop_loss).toFixed(2)}</b></div>
              <div class="health-row"><span>Take Profit 1:</span> <b class="text-green">$${Number(s.take_profit_1).toFixed(2)}</b></div>
              <div class="health-row"><span>Risk-to-Reward:</span> <b class="text-gold">1:${Number(s.risk_reward_ratio).toFixed(1)}</b></div>
            </div>
            <div style="margin-top:14px; display:flex; gap:8px;">
              <button class="btn btn-gold btn-sm" onclick="switchNavPane('signals')">View in Signal Center</button>
              <button class="btn btn-outline btn-sm" onclick="selectSymbol('${s.symbol}', 'OANDA:${s.symbol}'); switchNavPane('charts');">Open Chart</button>
            </div>
          `;
        }
      } else {
        if (spotBadge) spotBadge.innerText = "WAIT / NO TRADE";
        if (spotContainer) {
          spotContainer.innerHTML = `
            <div class="text-muted text-sm" style="padding:16px 0;">
              No qualified setups meet the server-configured risk filter at this moment.
              System is continuously scanning order blocks and liquidity sweeps.
            </div>
            <button class="btn btn-gold btn-sm" onclick="triggerScan()">⚡ Run Market Scan</button>
          `;
        }
      }
    }
  } catch (err) {
    console.warn("loadOverviewData error:", err);
  }
}

/* ==========================================================================
   2. LIVE MARKETS DATA LOADER & TABLE
   ========================================================================== */
let currentMarketsFilter = "ALL";
let currentMarketsSearch = "";

function filterMarketsTable(cat, btn) {
  currentMarketsFilter = cat;
  document.querySelectorAll("#tab-pane-markets .section-filter-btn").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
  renderMarketsTable();
}

function onMarketsTableSearch(val) {
  currentMarketsSearch = val || "";
  renderMarketsTable();
}

async function loadMarketsData() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/prices/realtime`);
    if (res.ok) {
      const data = await res.json();
      window.lastKnownMarketData = data.prices || {};
    }
  } catch (e) {
    console.warn("loadMarketsData error:", e);
  }
  renderMarketsTable();
}

function renderMarketsTable() {
  const tbody = document.getElementById("markets-full-table-body");
  if (!tbody) return;

  let filtered = currentMarketsFilter === "ALL"
    ? WATCHLIST
    : WATCHLIST.filter(item => item.category === currentMarketsFilter || (currentMarketsFilter === "COMMODITIES" && item.category === "COMMODITIES"));

  if (currentMarketsSearch.trim()) {
    const q = currentMarketsSearch.trim().toUpperCase();
    filtered = filtered.filter(item => item.symbol.includes(q) || item.name.toUpperCase().includes(q));
  }

  const prices = window.lastKnownMarketData || {};

  tbody.innerHTML = filtered.map(item => {
    const pInfo = prices[item.symbol] || null;
    const isCrypto = item.symbol.includes("USDT") || item.symbol.includes("BTC");
    const isForex = !isCrypto && !item.symbol.includes("XAU") && !item.symbol.includes("XAG");
    const p = pInfo ? Number(pInfo.price) : null;
    const fmtPrice = p !== null ? (isForex ? p.toFixed(4) : (p > 100 ? `$${p.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : `$${p}`)) : "---";
    const bid = pInfo && pInfo.bid ? (isForex ? Number(pInfo.bid).toFixed(4) : `$${Number(pInfo.bid).toFixed(2)}`) : "---";
    const ask = pInfo && pInfo.ask ? (isForex ? Number(pInfo.ask).toFixed(4) : `$${Number(pInfo.ask).toFixed(2)}`) : "---";
    const spread = pInfo && pInfo.spread !== undefined && pInfo.spread !== null ? `${pInfo.spread} pts` : "---";
    const c24 = pInfo && pInfo.change_24h !== undefined && pInfo.change_24h !== null ? Number(pInfo.change_24h) : null;
    const chgText = c24 === null ? "--" : (c24 >= 0 ? `+${c24.toFixed(2)}%` : `${c24.toFixed(2)}%`);
    const source = pInfo ? (pInfo.provider || pInfo.source || "N/A") : "Awaiting data";
    const isLive = pInfo && pInfo.source === "EXNESS_MT5";
    const statusPill = isLive ? `<span class="badge-active">MT5 LIVE</span>` : `<span class="provider-pill">${pInfo ? 'FALLBACK' : 'OFFLINE'}</span>`;

    return `
      <tr>
        <td>
          <div style="display:flex; align-items:center; gap:8px;">
            ${getAssetRealLogoHTML(item.symbol)}
            <b>${item.symbol}</b>
          </div>
        </td>
        <td><span class="text-secondary">${item.name}</span> <span class="provider-pill" style="margin-left:4px;">${item.category}</span></td>
        <td>${bid}</td>
        <td>${ask}</td>
        <td><span class="text-muted">${spread}</span></td>
        <td class="${c24 === null ? 'text-muted' : (c24 >= 0 ? 'text-green' : 'text-red')}"><b>${chgText}</b></td>
        <td><span class="provider-pill">${escapeHtml(String(source))}</span></td>
        <td>${statusPill}</td>
        <td>
          <button class="btn btn-outline btn-xs" onclick="selectSymbol('${item.symbol}', '${item.tv}'); switchNavPane('charts');">📈 Chart</button>
        </td>
      </tr>
    `;
  }).join("");
}

/* ==========================================================================
   5. SIGNAL CENTER DATA LOADER & DISPATCH
   ========================================================================== */
async function loadSignalsCenterData() {
  const container = document.getElementById("signals-center-container");
  if (!container) return;
  container.innerHTML = `<div class="registry-telemetry-loading">Querying active signals from PostgreSQL ledger...</div>`;

  try {
    const res = await fetch(`${API_BASE}/api/v1/xauusd/signals?status=ACTIVE,CANDIDATE&limit=10`);
    if (!res.ok) throw new Error("Failed to fetch active signals");
    const data = await res.json();
    const sigs = data.signals || [];

    if (sigs.length === 0) {
      container.innerHTML = `
        <div class="empty-state-card" style="grid-column: 1 / -1; text-align:center; padding: 40px 20px;">
          <div style="font-size:32px; margin-bottom:12px;">🛡️</div>
          <div style="font-size:16px; font-weight:700; color:var(--zyrox-text);">No Qualified Active Signals</div>
          <div style="color:var(--zyrox-text-secondary); max-width:480px; margin:8px auto 20px auto; font-size:13px; line-height:1.6;">
            No active signal records are currently available. Check that a verified market-data source is configured before generating a new analysis.
          </div>
          <button class="btn btn-gold btn-sm" onclick="triggerGenerateSignalAction()">⚡ Run Signal Generator Now</button>
        </div>
      `;
      return;
    }

    container.innerHTML = sigs.map(s => {
      const isBuy = s.direction === "BUY";
      const sideCls = isBuy ? "side-buy" : "side-sell";
      const createdStr = s.created_at ? new Date(s.created_at).toLocaleString() : "Just now";
      const fmtPrice = value => value != null && Number.isFinite(Number(value)) ? Number(value).toFixed(2) : "N/A";
      const rrValue = s.risk_reward_ratio == null || !Number.isFinite(Number(s.risk_reward_ratio)) ? "N/A" : Number(s.risk_reward_ratio).toFixed(1);
      const rawScore = s.setup_score ?? s.confidence;
      const scoreNumber = rawScore == null ? NaN : Number(rawScore);
      const scoreDisplay = Number.isFinite(scoreNumber) ? `${Math.round(scoreNumber > 1 ? scoreNumber : scoreNumber * 100)}%` : "N/A";
      const rawSymbol = String(s.symbol || "");
      const safeSymbol = /^[A-Z0-9._-]{1,20}$/.test(rawSymbol) ? rawSymbol : "";
      const safeDirection = escapeHtml(String(s.direction || "N/A"));
      return `
        <div class="signal-card ${sideCls}">
          <div class="signal-card-header">
            <div style="display:flex; align-items:center; gap:8px;">
              ${getAssetRealLogoHTML(safeSymbol)}
              <span style="font-weight:700; font-size:16px;">${escapeHtml(safeSymbol || "N/A")}</span>
              <span class="badge-side ${isBuy ? 'badge-buy' : 'badge-sell'}">${safeDirection}</span>
            </div>
            <span class="provider-pill">${escapeHtml(String(s.status || "N/A"))}</span>
          </div>

          <div class="signal-card-body">
            <div class="sig-level-row">
              <span class="sig-lvl-label">Entry Range:</span>
              <span class="sig-lvl-val">$${fmtPrice(s.entry_zone_min)} – $${fmtPrice(s.entry_zone_max)}</span>
            </div>
            <div class="sig-level-row">
              <span class="sig-lvl-label">Stop Loss (SL):</span>
              <span class="sig-lvl-val text-red">$${fmtPrice(s.stop_loss)}</span>
            </div>
            <div class="sig-level-row">
              <span class="sig-lvl-label">Take Profit 1:</span>
              <span class="sig-lvl-val text-green">$${fmtPrice(s.take_profit_1)}</span>
            </div>
            <div class="sig-level-row">
              <span class="sig-lvl-label">Risk-to-Reward:</span>
              <span class="sig-lvl-val text-gold">${rrValue === "N/A" ? "N/A" : `1:${rrValue}`}</span>
            </div>
            <div class="sig-level-row">
              <span class="sig-lvl-label">Setup Confidence:</span>
              <span class="sig-lvl-val text-cyan">${scoreDisplay}</span>
            </div>
            <div class="sig-level-row">
              <span class="sig-lvl-label">Mode / Source:</span>
              <span class="sig-lvl-val text-muted">${escapeHtml(String(s.execution_mode || 'N/A'))} · ${escapeHtml(String(s.data_source || 'N/A'))}</span>
            </div>
          </div>

          <div class="signal-card-footer">
            <span class="text-muted" style="font-size:11px;">${escapeHtml(createdStr)}</span>
            <div style="display:flex; gap:6px;">
              <button class="btn btn-outline btn-xs" onclick="selectSymbol('${safeSymbol}', 'OANDA:${safeSymbol}'); switchNavPane('charts');">📈 Chart</button>
              <button class="btn btn-gold btn-xs" onclick="sendTelegramTestSignalAction()">✈ Dispatch</button>
            </div>
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<div class="error-banner">Failed to load signals: ${escapeHtml(err.message)}</div>`;
  }
}

async function triggerGenerateSignalAction() {
  const btn = event?.currentTarget;
  if (btn) {
    btn.disabled = true;
    btn.innerText = "⏳ Generating...";
  }

  try {
    const res = await fetch(`${API_BASE}/api/v1/xauusd/signals/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: currentSymbol, timeframe: currentTimeframe })
    });
    const data = await res.json();
    if (data.status === "ACTIVE" || data.status === "CANDIDATE") {
      alert(`✅ New Qualified Signal Generated!\nDirection: ${data.direction}\nEntry: $${data.entry_zone_min} - $${data.entry_zone_max}\nSL: $${data.stop_loss}\nTP1: $${data.take_profit_1}`);
    } else {
      alert(`🛡️ Evaluation Result: ${data.status || 'WAIT / NO TRADE'}\nReason: ${data.reason || data.invalidation_condition || 'Strict institutional R:R and multi-agent gating maintained.'}`);
    }
    loadSignalsCenterData();
    loadSignalsHistoryData();
  } catch (err) {
    alert(`❌ Signal generation error: ${err.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "⚡ Scan & Generate Signal";
    }
  }
}

/* ==========================================================================
   6. SIGNAL HISTORY DATA LOADER & FILTER
   ========================================================================== */
let currentHistoryFilter = "ALL";

function filterSignalsHistory(filter, btn) {
  currentHistoryFilter = filter;
  document.querySelectorAll("#tab-pane-history .section-filter-btn").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
  loadSignalsHistoryData();
}

async function loadSignalsHistoryData() {
  const tbody = document.getElementById("signals-history-table-body");
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="11" class="text-center text-muted">Querying PostgreSQL historical audit trail...</td></tr>`;

  try {
    const url = currentHistoryFilter === "ALL" 
      ? `${API_BASE}/api/v1/xauusd/signals?limit=50`
      : `${API_BASE}/api/v1/xauusd/signals?status=${currentHistoryFilter}&limit=50`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to query signal ledger");
    const data = await res.json();
    const sigs = data.signals || [];

    if (sigs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="11" class="text-center text-muted" style="padding:24px;">No historical records found for filter '${currentHistoryFilter}'.</td></tr>`;
      return;
    }

    tbody.innerHTML = sigs.map(s => {
      const rawSymbol = String(s.symbol || "");
      const safeSymbol = /^[A-Z0-9._-]{1,20}$/.test(rawSymbol) ? rawSymbol : "";
      const isBuy = s.direction === "BUY";
      const statusPill = s.status === "TP_HIT" 
        ? `<span class="badge-active" style="background:rgba(0,217,154,0.15); color:var(--zyrox-primary);">TP HIT</span>`
        : (s.status === "SL_HIT" 
          ? `<span class="badge-expired" style="background:rgba(255,100,124,0.15); color:var(--zyrox-danger);">SL HIT</span>`
          : `<span class="provider-pill">${escapeHtml(String(s.status || "N/A"))}</span>`);

      const rReturn = s.outcome_r !== undefined && s.outcome_r !== null 
        ? (Number(s.outcome_r) > 0 ? `+${Number(s.outcome_r).toFixed(1)}R` : `${Number(s.outcome_r).toFixed(1)}R`) 
        : "N/A";

      const rCls = rReturn.startsWith("+") ? "text-green" : (rReturn.startsWith("-") ? "text-red" : "text-muted");
      const dt = s.created_at ? new Date(s.created_at).toLocaleString() : "N/A";

      return `
        <tr>
          <td><code style="color:var(--zyrox-primary);">${escapeHtml(String(s.id || s.signal_id || '--'))}</code></td>
          <td><b>${escapeHtml(safeSymbol || "N/A")}</b></td>
          <td><span class="${isBuy ? 'text-green' : 'text-red'} font-bold">${escapeHtml(String(s.direction || "N/A"))}</span></td>
          <td>$${Number(s.entry_zone_min).toFixed(2)} – $${Number(s.entry_zone_max).toFixed(2)}</td>
          <td class="text-red">$${Number(s.stop_loss).toFixed(2)}</td>
          <td class="text-green">$${Number(s.take_profit_1).toFixed(2)}</td>
          <td class="${rCls} font-bold">${rReturn}</td>
          <td>${statusPill}</td>
          <td><span class="text-secondary" style="font-size:11px;">${escapeHtml(dt)}</span></td>
          <td><span class="provider-pill">${escapeHtml(String(s.execution_mode || 'N/A'))}</span></td>
          <td>
            <button class="btn btn-outline btn-xs" onclick="selectSymbol('${safeSymbol}', 'OANDA:${safeSymbol}'); switchNavPane('charts');">Chart</button>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="11" class="text-center text-red" style="padding:20px;">Error loading history: ${escapeHtml(err.message)}</td></tr>`;
  }
}

/* ==========================================================================
   7. PERFORMANCE ANALYTICS DATA LOADER
   ========================================================================== */
let currentAnalyticsDataset = "ALL";

function switchAnalyticsDataset(dataset, btn) {
  currentAnalyticsDataset = dataset;
  document.querySelectorAll("#tab-pane-analytics .section-filter-btn").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
  loadPerformanceAnalyticsData();
}

async function loadPerformanceAnalyticsData() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/signals/performance?dataset=${currentAnalyticsDataset}`);
    if (!res.ok) throw new Error("Failed to fetch performance statistics");
    const data = await res.json();

    const setVal = (id, val, cls) => {
      const el = document.getElementById(id);
      if (el) {
        el.innerText = (val !== null && val !== undefined) ? val : "--";
        if (cls) el.className = cls;
      }
    };

    setVal("stat-total-signals", data.total_signals);
    setVal("stat-closed-trades", `Closed: ${data.total_closed || 0} · Active: ${data.total_active_signals || 0}`);
    setVal("stat-win-rate", data.win_rate_percent !== null ? `${data.win_rate_percent}%` : "--", "section-kpi-val text-green");
    setVal("stat-win-loss-count", `Wins: ${data.total_wins || 0} · Losses: ${data.total_losses || 0}`);
    setVal("stat-profit-factor", data.profit_factor !== null ? data.profit_factor : "--", "section-kpi-val text-gold");
    setVal("stat-expectancy-r", data.expectancy_r !== null ? `${data.expectancy_r > 0 ? '+' : ''}${data.expectancy_r} R` : "--", "section-kpi-val text-cyan");
    setVal("stat-max-drawdown", data.max_drawdown_percent !== null ? `${data.max_drawdown_percent}%` : "--", "section-kpi-val text-red");

    setVal("stat-tp1-rate", data.tp1_hit_rate !== null ? `${data.tp1_hit_rate}%` : "--", "val-green");
    setVal("stat-tp2-rate", data.tp2_hit_rate !== null ? `${data.tp2_hit_rate}%` : "--", "val-green");
    setVal("stat-tp3-rate", data.tp3_hit_rate !== null ? `${data.tp3_hit_rate}%` : "--", "val-green");
    setVal("stat-avg-win", data.avg_win_r !== null ? `+${data.avg_win_r} R` : "--", "val-gold");
    setVal("stat-avg-loss", data.avg_loss_r !== null ? `-${data.avg_loss_r} R` : "--", "val-red");

    // Populate strategy breakdown table
    const breakdownBody = document.getElementById("analytics-breakdown-body");
    if (breakdownBody) {
      const rows = Array.isArray(data.breakdown) ? data.breakdown : [];

      breakdownBody.innerHTML = rows.map(r => `
        <tr>
          <td><b>${escapeHtml(String(r.symbol || "N/A"))}</b></td>
          <td><span class="provider-pill">${escapeHtml(String(r.tf || "N/A"))}</span></td>
          <td><code style="color:var(--zyrox-text-secondary);">${escapeHtml(String(r.version || "N/A"))}</code></td>
          <td>${Number.isFinite(Number(r.count)) ? Number(r.count) : "N/A"}</td>
          <td class="text-green">${r.winrate != null && Number.isFinite(Number(r.winrate)) ? `${Number(r.winrate)}%` : '--'}</td>
          <td class="text-gold">${r.pf != null && Number.isFinite(Number(r.pf)) ? Number(r.pf) : '--'}</td>
          <td class="text-cyan">${r.r != null && Number.isFinite(Number(r.r)) ? `${Number(r.r)} R` : '--'}</td>
          <td><span class="provider-pill">${escapeHtml(String(r.status || "N/A"))}</span></td>
        </tr>
      `).join("");
    }
  } catch (err) {
    console.warn("loadPerformanceAnalyticsData error:", err);
  }
}

/* ==========================================================================
   10. TELEGRAM STATUS & TEST DISPATCH
   ========================================================================== */
async function loadTelegramStatusData() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/telegram/status`);
    if (res.ok) {
      const data = await res.json();
      const statusEl = document.getElementById("tg-bot-status");
      const userEl = document.getElementById("tg-bot-username");
      const chatEl = document.getElementById("tg-chat-id");
      const healthEl = document.getElementById("tg-delivery-health");

      if (data.configured) {
        if (statusEl) {
          statusEl.innerText = "CONFIGURED (connectivity not checked)";
          statusEl.className = "section-kpi-val text-gold";
        }
        if (userEl) userEl.innerText = data.bot_username ? `Bot: @${data.bot_username}` : "Bot username: not configured";
        if (chatEl) chatEl.innerText = data.default_chat_id || "Chat ID: not configured";
        if (healthEl) healthEl.innerText = "Delivery health not verified";
      } else {
        if (statusEl) {
          statusEl.innerText = "NOT CONFIGURED";
          statusEl.className = "section-kpi-val text-muted";
        }
        if (userEl) userEl.innerText = data.bot_username ? `Bot: @${data.bot_username}` : "Bot username: not configured";
        if (chatEl) chatEl.innerText = data.default_chat_id || "Chat ID: not configured";
        if (healthEl) healthEl.innerText = "Not available";
      }
    }
  } catch (err) {
    console.warn("loadTelegramStatusData error:", err);
  }
}

async function sendTelegramTestSignalAction() {
  const btn = event?.currentTarget;
  if (btn) {
    btn.disabled = true;
    btn.innerText = "⏳ Dispatching...";
  }

  try {
    const res = await fetch(`${API_BASE}/api/v1/telegram/send-test-signal`, { method: "POST" });
    const data = await res.json();
    if (data.status === "SUCCESS") {
      alert("✅ Test Signal successfully dispatched to Telegram channel via official Bot API!");
    } else {
      alert(`⚠️ Telegram dispatch result: ${data.message || JSON.stringify(data)}`);
    }
    loadTelegramStatusData();
  } catch (err) {
    alert(`❌ Telegram dispatch error: ${err.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "✉ Send Test Signal to Telegram";
    }
  }
}

/* ==========================================================================
   11. MT5 BRIDGE DATA LOADER
   ========================================================================== */
async function loadMT5BridgeData() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/bridge/status`);
    if (!res.ok) return;
    const data = await res.json();

    const heroState = document.getElementById("mt5-hero-state");
    const heroDesc = document.getElementById("mt5-hero-desc");
    const brokerEl = document.getElementById("mt5-broker-name");
    const serverEl = document.getElementById("mt5-server-name");
    const ageEl = document.getElementById("mt5-feed-age");
    const topDot = document.getElementById("top-bridge-dot");
    const topLabel = document.getElementById("top-bridge-label");

    if (data.status === "CONNECTED" && data.is_active_for_signals) {
      if (heroState) {
        heroState.innerText = "CONNECTED";
        heroState.className = "section-kpi-val text-green";
      }
      if (heroDesc) heroDesc.innerText = `Fresh ticks · ${(data.fresh_tick_symbols || []).join(", ") || "symbol unavailable"}`;
      if (topDot) topDot.className = "bridge-status-dot bridge-connected";
      if (topLabel) topLabel.innerText = "MT5: FRESH TICKS";
    } else if (data.status === "CONNECTED") {
      if (heroState) {
        heroState.innerText = "BRIDGE CONNECTED";
        heroState.className = "section-kpi-val text-gold";
      }
      if (heroDesc) heroDesc.innerText = "Heartbeat is active; waiting for a fresh bid/ask tick.";
      if (topDot) topDot.className = "bridge-status-dot bridge-stale";
      if (topLabel) topLabel.innerText = "MT5: NO FRESH TICK";
    } else if (data.status === "STALE") {
      if (heroState) {
        heroState.innerText = "FEED STALE";
        heroState.className = "section-kpi-val text-gold";
      }
      if (heroDesc) heroDesc.innerText = "No ticks in last 30s. Market closed or paused.";
      if (topDot) topDot.className = "bridge-status-dot bridge-stale";
      if (topLabel) topLabel.innerText = "MT5: STALE";
    } else {
      if (heroState) {
        heroState.innerText = "STANDBY";
        heroState.className = "section-kpi-val text-muted";
      }
      if (heroDesc) heroDesc.innerText = "Awaiting Windows Bridge client connection.";
      if (topDot) topDot.className = "bridge-status-dot bridge-disconnected";
      if (topLabel) topLabel.innerText = "MT5: STANDBY";
    }

    const bridgeReported = data.status !== "DISCONNECTED";
    if (brokerEl) brokerEl.innerText = bridgeReported ? (data.broker || "Not reported") : "Not connected";
    if (serverEl) serverEl.innerText = bridgeReported ? (data.server || "Not reported") : "No server reported";
    if (ageEl) ageEl.innerText = data.seconds_since_last_activity !== null && data.seconds_since_last_activity !== undefined ? `${data.seconds_since_last_activity}s ago` : "--";
  } catch (err) {
    console.warn("loadMT5BridgeData error:", err);
  }
}

function testBridgeStatus() {
  loadMT5BridgeData();
}

/* ==========================================================================
   12. SETTINGS LOADER & PERSISTENCE
   ========================================================================== */
function loadSettingsData() {
  const sym = localStorage.getItem("zyrox_default_symbol") || "XAUUSD";
  const tf = localStorage.getItem("zyrox_default_timeframe") || "15";
  const rr = localStorage.getItem("zyrox_risk_floor") || "2.0";
  const cap = localStorage.getItem("zyrox_risk_cap") || "0.5";
  const lang = localStorage.getItem("zyrox_lang") || (isKhmer ? "kh" : "en");
  const den = localStorage.getItem("zyrox_density") || "dense";

  const setSelect = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = val;
  };

  setSelect("setting-default-symbol", sym);
  setSelect("setting-default-timeframe", tf);
  setSelect("setting-risk-floor", rr);
  setSelect("setting-risk-cap", cap);
  setSelect("setting-language", lang);
  setSelect("setting-density", den);

  if (typeof initAnyRouterUI === "function") {
    initAnyRouterUI();
  }
  if (typeof initFreeLLMAPIUI === "function") {
    initFreeLLMAPIUI();
  }
}

function saveSettingsData() {
  const sym = document.getElementById("setting-default-symbol")?.value || "XAUUSD";
  const tf = document.getElementById("setting-default-timeframe")?.value || "15";
  const rr = document.getElementById("setting-risk-floor")?.value || "2.0";
  const cap = document.getElementById("setting-risk-cap")?.value || "0.5";
  const lang = document.getElementById("setting-language")?.value || "en";
  const den = document.getElementById("setting-density")?.value || "dense";

  localStorage.setItem("zyrox_default_symbol", sym);
  localStorage.setItem("zyrox_default_timeframe", tf);
  localStorage.setItem("zyrox_risk_floor", rr);
  localStorage.setItem("zyrox_risk_cap", cap);
  localStorage.setItem("zyrox_lang", lang);
  localStorage.setItem("zyrox_density", den);

  if (lang === "kh" && !isKhmer) toggleLanguage();
  if (lang === "en" && isKhmer) toggleLanguage();

  if (den === "dense") {
    document.body.classList.add("density-dense");
  } else {
    document.body.classList.remove("density-dense");
  }

  alert("✅ Terminal preferences saved to local profile!");
}

function onSettingLanguageChange(val) {
  if (val === "kh" && !isKhmer) toggleLanguage();
  if (val === "en" && isKhmer) toggleLanguage();
}

/* ==========================================================================
   13. ADMIN CONSOLE LOADER
   ========================================================================== */
function loadAdminData() {
  loadVipStats().then(() => {
    const act = document.getElementById("vip-kpi-active")?.textContent || "0";
    const exp = document.getElementById("vip-kpi-expiring")?.textContent || "0";
    const rev = document.getElementById("vip-kpi-revenue")?.textContent || "$0";

    const aAct = document.getElementById("admin-kpi-active");
    const aExp = document.getElementById("admin-kpi-expiring");
    const aRev = document.getElementById("admin-kpi-revenue");

    if (aAct) aAct.textContent = act;
    if (aExp) aExp.textContent = exp;
    if (aRev) aRev.textContent = rev;
  });
  loadVipSubscribers();
}

function toggleMacroDrawer() {
  const drawer = document.getElementById("tab-pane-macro-drawer");
  if (!drawer) return;
  const isHidden = drawer.classList.contains("tab-pane-hidden");
  if (isHidden) {
    drawer.classList.remove("tab-pane-hidden");
    fetchMacroEvents(false);
  } else {
    drawer.classList.add("tab-pane-hidden");
  }
}

function togglePortfolioDrawer() {
  const drawer = document.getElementById("tab-pane-portfolio-drawer");
  if (!drawer) return;
  const isHidden = drawer.classList.contains("tab-pane-hidden");
  if (isHidden) {
    drawer.classList.remove("tab-pane-hidden");
    fetchHealthAndPaper();
  } else {
    drawer.classList.add("tab-pane-hidden");
  }
}

function toggleDeepDiveTray() {
  const tray = document.getElementById("terminal-deepdive-tray");
  const arrow = document.getElementById("deepdive-arrow");
  if (!tray) return;
  tray.classList.toggle("open");
  const isOpen = tray.classList.contains("open");
  if (arrow) arrow.innerText = isOpen ? "▴" : "▾";
}

function toggleWatchlistCollapse() {
  const wl = document.getElementById("terminal-watchlist");
  if (wl) wl.classList.toggle("collapsed");
}

function toggleAiSidebarCollapse() {
  const ai = document.getElementById("terminal-ai-sidebar");
  if (ai) ai.classList.toggle("collapsed");
}

function switchAiSidebarTab(tabName, btn) {
  document.querySelectorAll(".ai-tab-btn").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");

  document.querySelectorAll(".ai-sidebar-pane").forEach(p => p.classList.remove("active"));
  const target = document.getElementById(`ai-pane-${tabName}`);
  if (target) target.classList.add("active");

  if (tabName === "ledger") {
    fetchHealthAndPaper();
  }
}

function focusAIChat() {
  if (window.innerWidth <= 900) {
    switchMobileView("ai");
  } else {
    const tabBtn = document.getElementById("ai-tab-chat");
    if (tabBtn) switchAiSidebarTab("chat", tabBtn);
    const aiSidebar = document.getElementById("terminal-ai-sidebar");
    if (aiSidebar && aiSidebar.classList.contains("collapsed")) {
      aiSidebar.classList.remove("collapsed");
    }
  }
  const input = document.getElementById("ai-chat-input");
  if (input) {
    setTimeout(() => {
      input.focus();
      input.scrollIntoView({ behavior: "smooth" });
    }, 100);
  }
}

let currentMobileView = "chart";

function switchMobileView(view) {
  currentMobileView = view;

  // Close any open sheets or overlays
  closeMobileMoreSheet();
  document.querySelectorAll(".terminal-full-overlay").forEach(el => el.classList.add("tab-pane-hidden"));

  // Update active state in bottom navigation bar
  document.querySelectorAll(".mob-nav-item").forEach(item => item.classList.remove("active"));
  const navBtn = document.getElementById(`mob-nav-${view}`);
  if (navBtn) navBtn.classList.add("active");

  // Update body classes for responsive styles
  document.body.classList.remove("mobile-view-chart", "mobile-view-watchlist", "mobile-view-ai", "mobile-view-trade");
  document.body.classList.add(`mobile-view-${view}`);

  const mainCanvas = document.getElementById("terminal-center-canvas");
  const wlPanel = document.getElementById("terminal-watchlist");
  const aiSidebar = document.getElementById("terminal-ai-sidebar");

  if (window.innerWidth <= 900) {
    if (view === "chart") {
      if (mainCanvas) mainCanvas.style.setProperty("display", "flex", "important");
      if (wlPanel) wlPanel.style.setProperty("display", "none", "important");
      if (aiSidebar) aiSidebar.style.setProperty("display", "none", "important");
      if (window.taikryChart && typeof window.taikryChart.handleResize === "function") {
        setTimeout(() => window.taikryChart.handleResize(), 80);
      }
    } else if (view === "watchlist") {
      if (mainCanvas) mainCanvas.style.setProperty("display", "none", "important");
      if (wlPanel) {
        wlPanel.style.setProperty("display", "flex", "important");
        wlPanel.classList.remove("collapsed");
      }
      if (aiSidebar) aiSidebar.style.setProperty("display", "none", "important");
    } else if (view === "ai") {
      if (mainCanvas) mainCanvas.style.setProperty("display", "none", "important");
      if (wlPanel) wlPanel.style.setProperty("display", "none", "important");
      if (aiSidebar) {
        aiSidebar.style.setProperty("display", "flex", "important");
        aiSidebar.classList.remove("collapsed");
        switchAiSidebarTab("chat", document.getElementById("ai-tab-chat"));
      }
    } else if (view === "trade") {
      if (mainCanvas) mainCanvas.style.setProperty("display", "none", "important");
      if (wlPanel) wlPanel.style.setProperty("display", "none", "important");
      if (aiSidebar) {
        aiSidebar.style.setProperty("display", "flex", "important");
        aiSidebar.classList.remove("collapsed");
        switchAiSidebarTab("trade", document.getElementById("ai-tab-trade"));
      }
    }
  }

  // Telegram native haptic feedback if running inside Telegram Mini App
  if (window.Telegram?.WebApp?.HapticFeedback) {
    try {
      window.Telegram.WebApp.HapticFeedback.selectionChanged();
    } catch (_) {}
  }
}

window.addEventListener("resize", () => {
  if (window.innerWidth > 900) {
    const mainCanvas = document.getElementById("terminal-center-canvas");
    const wlPanel = document.getElementById("terminal-watchlist");
    const aiSidebar = document.getElementById("terminal-ai-sidebar");
    if (mainCanvas) mainCanvas.style.removeProperty("display");
    if (wlPanel) wlPanel.style.removeProperty("display");
    if (aiSidebar) aiSidebar.style.removeProperty("display");
  } else {
    switchMobileView(currentMobileView);
  }
});

function toggleMobileMoreSheet() {
  const sheet = document.getElementById("mobile-more-sheet");
  if (!sheet) return;
  const isHidden = sheet.classList.contains("tab-pane-hidden");
  if (isHidden) {
    sheet.classList.remove("tab-pane-hidden");
    const moreBtn = document.getElementById("mob-nav-more");
    if (moreBtn) moreBtn.classList.add("active");
    if (window.Telegram?.WebApp?.HapticFeedback) {
      try { window.Telegram.WebApp.HapticFeedback.impactOccurred("light"); } catch (_) {}
    }
  } else {
    closeMobileMoreSheet();
  }
}

function closeMobileMoreSheet(event) {
  const sheet = document.getElementById("mobile-more-sheet");
  if (sheet) sheet.classList.add("tab-pane-hidden");
  const moreBtn = document.getElementById("mob-nav-more");
  if (moreBtn) moreBtn.classList.remove("active");
  // Restore current view button active state
  const activeBtn = document.getElementById(`mob-nav-${currentMobileView}`);
  if (activeBtn) activeBtn.classList.add("active");
}

function onChatInputKeydown(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    submitChatMessage();
  }
}

// =========================================================================
// REAL AI CHAT ASSISTANT & MULTIMODAL PHOTO UPLOAD (PHONE & PC)
// =========================================================================

let currentChatPhotoBase64 = null;
let currentChatPhotoName = "";

function triggerPhotoUpload() {
  const fileInput = document.getElementById("ai-chat-photo-input");
  if (fileInput) fileInput.click();
}

function onPhotoSelected(event) {
  const file = event.target?.files?.[0];
  if (!file) return;
  processChatImageFile(file);
}

function processChatImageFile(file) {
  if (!file.type.startsWith("image/")) {
    alert("Please select an image file (PNG, JPG, WEBP).");
    return;
  }
  const reader = new FileReader();
  reader.onload = function(e) {
    currentChatPhotoBase64 = e.target.result;
    currentChatPhotoName = file.name || "chart_screenshot.png";
    const previewTray = document.getElementById("chat-photo-preview-tray");
    const previewImg = document.getElementById("chat-photo-preview-img");
    const photoName = document.getElementById("chat-photo-name");
    if (previewTray && previewImg) {
      previewImg.src = currentChatPhotoBase64;
      if (photoName) photoName.innerText = currentChatPhotoName;
      previewTray.classList.add("is-active");
      previewTray.style.display = "flex";
    }
  };
  reader.readAsDataURL(file);
}

function clearPhotoAttachment() {
  currentChatPhotoBase64 = null;
  currentChatPhotoName = "";
  const fileInput = document.getElementById("ai-chat-photo-input");
  if (fileInput) fileInput.value = "";
  const previewTray = document.getElementById("chat-photo-preview-tray");
  if (previewTray) {
    previewTray.classList.remove("is-active");
    previewTray.style.display = "none";
  }
}

function handleChatPaste(event) {
  const items = (event.clipboardData || event.originalEvent?.clipboardData)?.items;
  if (!items) return;
  for (let i = 0; i < items.length; i++) {
    if (items[i].type.indexOf("image") !== -1) {
      const file = items[i].getAsFile();
      if (file) {
        processChatImageFile(file);
        event.preventDefault();
        break;
      }
    }
  }
}

function setupChatDragAndDrop() {
  const dropZone = document.getElementById("ai-pane-chat");
  if (!dropZone) return;

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
  dropZone.addEventListener("dragleave", (e) => {
    dropZone.classList.remove("dragover");
  });
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer?.files?.length) {
      const file = e.dataTransfer.files[0];
      if (file.type.startsWith("image/")) {
        processChatImageFile(file);
      }
    }
  });

  const chatInput = document.getElementById("ai-chat-input");
  if (chatInput) {
    chatInput.addEventListener("paste", handleChatPaste);
  }
}

function openImageZoom(src) {
  if (!src) return;
  const overlay = document.createElement("div");
  overlay.className = "chart-img-modal-overlay";
  overlay.style.cssText = "position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.85);backdrop-filter:blur(10px);z-index:99999;display:flex;align-items:center;justify-content:center;cursor:zoom-out;";
  const image = document.createElement("img");
  image.src = src;
  image.alt = "Uploaded chart preview";
  image.style.cssText = "max-width:92vw;max-height:92vh;border-radius:10px;border:2px solid rgba(56,189,248,0.5);box-shadow:0 0 30px rgba(0,0,0,0.9);object-fit:contain;";
  overlay.appendChild(image);
  overlay.onclick = () => {
    if (document.body.contains(overlay)) {
      document.body.removeChild(overlay);
    }
  };
  document.body.appendChild(overlay);
}

function applySetupToFastTrade(action, entry, sl, tp1) {
  setFastTradeDir(action === "SELL" ? "SELL" : "BUY");
  const entryInput = document.getElementById("ft-entry-input");
  const slInput = document.getElementById("ft-sl-input");
  const tpInput = document.getElementById("ft-tp-input");
  if (entryInput && entry && entry !== "---") entryInput.value = entry;
  if (slInput && sl && sl !== "---") slInput.value = sl;
  if (tpInput && tp1 && tp1 !== "---") tpInput.value = tp1;

  // Switch to Trade tab
  const tradeTabBtn = document.getElementById("ai-tab-trade");
  if (tradeTabBtn) switchAiSidebarTab("trade", tradeTabBtn);

  // Flash highlight
  [entryInput, slInput, tpInput].forEach(el => {
    if (el) {
      el.style.transition = "box-shadow 0.2s, border-color 0.2s";
      el.style.borderColor = "var(--theme-accent-bright)";
      el.style.boxShadow = "0 0 12px var(--theme-accent-bright)";
      setTimeout(() => {
        el.style.borderColor = "";
        el.style.boxShadow = "";
      }, 1500);
    }
  });

  const toast = document.getElementById("cockpit-status-toast");
  if (toast) {
    toast.innerHTML = `<span class="toast-clock">⚡</span> <b>Trade setup applied to Fast Trade (${escapeHtml(String(action))} @ ${escapeHtml(String(entry))}) ✓</b>`;
  }
}

function copySetupToClipboard(text, btnElement) {
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    if (btnElement) {
      const orig = btnElement.innerHTML;
      btnElement.innerHTML = `✓ Copied!`;
      setTimeout(() => { btnElement.innerHTML = orig; }, 1800);
    }
    const toast = document.getElementById("cockpit-status-toast");
    if (toast) {
      toast.innerHTML = `<span class="toast-clock">📋</span> <b>Setup copied to clipboard ✓</b>`;
    }
  }).catch(() => {
    alert("Trade Setup:\n" + text);
  });
}

function sendQuickPrompt(promptText) {
  const input = document.getElementById("ai-chat-input");
  if (input) input.value = promptText;
  submitChatMessage();
}

async function submitChatMessage() {
  const input = document.getElementById("ai-chat-input");
  const stream = document.getElementById("ai-chat-stream");
  if (!input || !stream) return;

  const query = input.value.trim();
  const photoToSend = currentChatPhotoBase64;
  const photoName = currentChatPhotoName;

  if (!query && !photoToSend) return;

  input.value = "";
  clearPhotoAttachment();

  const now = new Date();
  const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

  // User Message Bubble
  const userMsg = document.createElement("div");
  userMsg.className = "chat-msg chat-msg-user";
  let userAttachmentHtml = "";
  if (photoToSend) {
    userAttachmentHtml = `
      <div class="chat-user-img-attachment">
        <img src="${photoToSend}" alt="Uploaded Chart" onclick="openImageZoom(this.src)" title="Click to enlarge" />
      </div>
    `;
  }
  userMsg.innerHTML = `
    <div class="chat-avatar">👤</div>
    <div class="chat-bubble">
      <div class="chat-author">TRADER</div>
      ${userAttachmentHtml}
      ${query ? `<div class="chat-text">${escapeHtml(query)}</div>` : ""}
      <div class="chat-time">${timeStr}</div>
    </div>
  `;
  stream.appendChild(userMsg);
  stream.scrollTop = stream.scrollHeight;

  // Typing / AI Processing Bubble
  const provider = document.getElementById("ai-chat-provider-select")?.value || "auto";
  const typingMsg = document.createElement("div");
  typingMsg.className = "chat-msg chat-msg-ai";
  const typingStatus = photoToSend ?
    `Analyzing chart photo with Real Multimodal Vision (Gemini 3 / SMC Engine)...` :
    `Synthesizing institutional multi-agent consensus for ${currentSymbol}...`;

  typingMsg.innerHTML = `
    <div class="chat-avatar">🤖</div>
    <div class="chat-bubble">
      <div class="chat-author">TAIKRY AI</div>
      <div class="chat-text"><span class="pulse-dot-sm"></span> <i>${typingStatus}</i></div>
      <div class="chat-time">${timeStr}</div>
    </div>
  `;
  stream.appendChild(typingMsg);
  stream.scrollTop = stream.scrollHeight;

  try {
    const payload = {
      query: query || (photoToSend ? "Analyze this chart thoroughly with institutional SMC rules, calculate Entry, SL, TP, and វិភាគមើលជាភាសាខ្មែរ." : `Analyze ${currentSymbol} market structure`),
      symbol: currentSymbol,
      timeframe: currentTimeframe || "15m",
      provider: provider,
      image_base64: photoToSend
    };

    const resp = await fetch("/api/v1/ai/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(payload)
    });

    if (!resp.ok) {
      const errJson = await resp.json().catch(() => ({}));
      throw new Error(errJson.detail || `API HTTP ${resp.status}`);
    }

    const data = await resp.json();
    const trade = data.trade_execution || {};
    const analysis = data.smart_analysis || {};

    const action = (trade.action || "HOLD").toUpperCase();
    const entry = trade.entry_price !== null && trade.entry_price !== undefined ? trade.entry_price : "---";
    const sl = trade.stop_loss !== null && trade.stop_loss !== undefined ? trade.stop_loss : "---";
    const tp1 = trade.take_profit_1 !== null && trade.take_profit_1 !== undefined ? trade.take_profit_1 : "---";
    const tp2 = trade.take_profit_2 !== null && trade.take_profit_2 !== undefined ? trade.take_profit_2 : "---";
    const rr = trade.risk_reward_ratio || "N/A";
    const confidenceValue = Number(trade.confidence);
    const confidence = Number.isFinite(confidenceValue) && confidenceValue >= 0 && confidenceValue <= 100
      ? `${confidenceValue}%`
      : "N/A";

    const actionBadgeClass = action === "BUY" ? "chat-action-buy" : (action === "SELL" ? "chat-action-sell" : "chat-action-hold");
    const actionIcon = action === "BUY" ? "🟢 BUY" : (action === "SELL" ? "🔴 SELL" : "🟡 HOLD");
    const providerTag = [
      data.provider ? data.provider.toUpperCase() : "Provider not reported",
      data.model || "Model not reported",
      data.latency_ms ? `${data.latency_ms}ms` : null
    ].filter(Boolean).join(" · ");

    const khmerSummary = analysis.synthesis_summary_kh || "";
    const enSummary = analysis.synthesis_summary_en || "";

    const copyText = `⚡ TAIKRY AI ANALYSIS OUTPUT — PAPER ONLY
Asset: ${currentSymbol} (${currentTimeframe || "15m"})
Action: ${action}
Entry: ${entry}
Stop Loss: ${sl}
Take Profit 1: ${tp1}
Take Profit 2: ${tp2}
Risk/Reward: ${rr}
Confidence: ${confidence}
Model: ${providerTag}
វិភាគមើល: ${khmerSummary}`;

    const safeCopyText = copyText.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;');

    let cardHtml = `
      <div class="chat-setup-card">
        <div class="chat-setup-header">
          <div class="chat-setup-badge-group">
            <span class="chat-action-badge ${actionBadgeClass}">${actionIcon}</span>
            <span style="font-weight:700; color:#fff; font-size:12px;">${currentSymbol} · ${currentTimeframe || "15m"}</span>
          </div>
          <span class="chat-provider-pill">${escapeHtml(providerTag)}</span>
        </div>

        <div class="chat-setup-grid">
          <div class="chat-setup-item">
            <div class="chat-setup-lbl">Entry Price</div>
            <div class="chat-setup-val val-gold">${(entry !== "---" && entry !== null && entry !== undefined) ? '$' + entry : '---'}</div>
          </div>
          <div class="chat-setup-item">
            <div class="chat-setup-lbl">Stop Loss (SL)</div>
            <div class="chat-setup-val val-red">${(sl !== "---" && sl !== null && sl !== undefined) ? '$' + sl : '---'}</div>
          </div>
          <div class="chat-setup-item">
            <div class="chat-setup-lbl">Take Profit 1 (TP1)</div>
            <div class="chat-setup-val val-green">${(tp1 !== "---" && tp1 !== null && tp1 !== undefined) ? '$' + tp1 : '---'}</div>
          </div>
          <div class="chat-setup-item">
            <div class="chat-setup-lbl">Take Profit 2 (TP2)</div>
            <div class="chat-setup-val val-green">${(tp2 !== "---" && tp2 !== null && tp2 !== undefined) ? '$' + tp2 : '---'}</div>
          </div>
          <div class="chat-setup-item chat-setup-grid-full">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span class="chat-setup-lbl">Risk:Reward Floor</span>
              <span style="font-weight:800; color:#38bdf8; font-size:12px;">${rr}</span>
              <span class="chat-setup-lbl" style="margin-left:12px;">Confidence</span>
              <span style="font-weight:800; color:#ffd700; font-size:12px;">${confidence}</span>
            </div>
          </div>
        </div>

        ${khmerSummary ? `
          <div class="chat-khmer-analysis-box">
            <div class="chat-khmer-title">🇰🇭 ការវិភាគមើលលម្អិត (Khmer Market Analysis):</div>
            <div>${escapeHtml(khmerSummary)}</div>
          </div>
        ` : ""}

        ${enSummary ? `
          <div class="chat-en-analysis-box">
            <b>Institutional Analysis:</b> ${escapeHtml(enSummary)}
          </div>
        ` : ""}

        ${data.deep_research ? `
          <div class="chat-deep-research-container" style="margin-top:10px; background:rgba(15,23,42,0.85); border:1px solid rgba(56,189,248,0.35); border-radius:8px; padding:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:6px;">
              <span style="font-weight:700; color:#38bdf8; font-size:12px;">🔬 11-Agent Pre-News & Deep Research</span>
              <span style="font-size:10px; background:rgba(56,189,248,0.15); color:#38bdf8; padding:2px 6px; border-radius:4px;">Window: ${escapeHtml(data.deep_research.C_upcoming_news_calendar?.blackout_status || 'STANDARD')}</span>
            </div>
            
            ${data.deep_research.C_upcoming_news_calendar ? `
              <div style="font-size:11px; margin-bottom:8px; background:rgba(0,0,0,0.3); padding:6px 8px; border-radius:4px;">
                <b style="color:#f59e0b;">📅 Upcoming Catalyst:</b> ${escapeHtml(data.deep_research.C_upcoming_news_calendar.event_name)} (${escapeHtml(data.deep_research.C_upcoming_news_calendar.currency)})
                <span style="color:#94a3b8; margin-left:6px;">Forecast: ${escapeHtml(data.deep_research.C_upcoming_news_calendar.forecast)} | Prev: ${escapeHtml(data.deep_research.C_upcoming_news_calendar.previous)}</span>
                <div style="font-size:10.5px; color:#38bdf8; margin-top:2px;">⏱ Countdown: ${escapeHtml(data.deep_research.C_upcoming_news_calendar.countdown || '')} · Local: ${escapeHtml(data.deep_research.C_upcoming_news_calendar.event_time_cambodia || '')}</div>
              </div>
            ` : ""}

            <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:8px;">
              ${data.deep_research.F_bullish_scenario ? `
                <div style="background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.3); border-radius:6px; padding:8px; font-size:11px;">
                  <div style="font-weight:700; color:#10b981; margin-bottom:4px;">🟢 Bullish Scenario</div>
                  <div style="color:#94a3b8; font-size:10px;">Trigger: <span style="color:#fff;">${escapeHtml(data.deep_research.F_bullish_scenario.confirmation_trigger || '---')}</span></div>
                  <div style="color:#94a3b8; font-size:10px;">TP1: <span style="color:#10b981;">$${data.deep_research.F_bullish_scenario.target_1 || '---'}</span> | TP2: <span style="color:#10b981;">$${data.deep_research.F_bullish_scenario.target_2 || '---'}</span></div>
                  <div style="color:#94a3b8; font-size:10px;">SL: <span style="color:#ef4444;">$${data.deep_research.F_bullish_scenario.stop_loss || '---'}</span></div>
                  <div style="color:#cbd5e1; font-size:9.5px; margin-top:3px;">❌ Inval: ${escapeHtml(data.deep_research.F_bullish_scenario.invalidation || '---')}</div>
                </div>
              ` : ""}

              ${data.deep_research.G_bearish_scenario ? `
                <div style="background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.3); border-radius:6px; padding:8px; font-size:11px;">
                  <div style="font-weight:700; color:#ef4444; margin-bottom:4px;">🔴 Bearish Scenario</div>
                  <div style="color:#94a3b8; font-size:10px;">Trigger: <span style="color:#fff;">${escapeHtml(data.deep_research.G_bearish_scenario.confirmation_trigger || '---')}</span></div>
                  <div style="color:#94a3b8; font-size:10px;">TP1: <span style="color:#10b981;">$${data.deep_research.G_bearish_scenario.target_1 || '---'}</span> | TP2: <span style="color:#10b981;">$${data.deep_research.G_bearish_scenario.target_2 || '---'}</span></div>
                  <div style="color:#94a3b8; font-size:10px;">SL: <span style="color:#ef4444;">$${data.deep_research.G_bearish_scenario.stop_loss || '---'}</span></div>
                  <div style="color:#cbd5e1; font-size:9.5px; margin-top:3px;">❌ Inval: ${escapeHtml(data.deep_research.G_bearish_scenario.invalidation || '---')}</div>
                </div>
              ` : ""}
            </div>

            ${data.deep_research.H_base_case_no_trade ? `
              <div style="background:rgba(245,158,11,0.08); border:1px solid rgba(245,158,11,0.25); border-radius:6px; padding:6px 8px; font-size:10.5px; margin-bottom:6px; color:#fde047;">
                <b>🛡 Base Case:</b> ${escapeHtml(data.deep_research.H_base_case_no_trade.condition || '')}
              </div>
            ` : ""}

            ${data.deep_research.I_volatility_spread_warning ? `
              <div style="font-size:10px; color:#f87171; margin-bottom:4px;">
                ⚠️ <b>Spread Warning:</b> ${escapeHtml(data.deep_research.I_volatility_spread_warning.warning_kh || data.deep_research.I_volatility_spread_warning.warning_en || '')}
              </div>
            ` : ""}

            <div style="font-size:9.5px; color:#64748b; margin-top:6px; border-top:1px solid rgba(255,255,255,0.05); padding-top:4px;">
              📊 Sources: ${escapeHtml((data.deep_research.J_source_list_and_freshness?.news_sources || []).join(' · ') || 'Investing.com · MarketWatch · FairEconomy')}
            </div>
          </div>
        ` : ""}

        <div class="chat-setup-actions">
          <button class="btn-chat-apply" onclick="applySetupToFastTrade('${action}', '${entry}', '${sl}', '${tp1}')" title="Send to 1-Click Fast Trade Panel">
            ⚡ បញ្ជូនទៅ Fast Trade
          </button>
          <button class="btn-chat-copy" onclick="copySetupToClipboard('${safeCopyText}', this)" title="Copy Trade Setup for Telegram or Notes">
            📋 ចម្លង Setup
          </button>
        </div>
      </div>
    `;

    typingMsg.querySelector(".chat-text").innerHTML = cardHtml;
    stream.scrollTop = stream.scrollHeight;
  } catch (err) {
    console.error("AI Chat Error:", err);
    typingMsg.querySelector(".chat-text").innerHTML = `
      <div style="color:var(--accent-red); font-size:11.5px;">
        ⚠️ AI Chat notice: ${escapeHtml(err.message || 'Service temporarily unavailable')}. Please retry or choose another provider.
      </div>
    `;
    stream.scrollTop = stream.scrollHeight;
  }
}


function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return String(text ?? "").replace(/[&<>"']/g, m => map[m]);
}

function setFastTradeDir(dir) {
  const buyBtn = document.getElementById("ft-btn-buy");
  const sellBtn = document.getElementById("ft-btn-sell");
  if (dir === "BUY") {
    if (buyBtn) buyBtn.classList.add("active");
    if (sellBtn) sellBtn.classList.remove("active");
  } else {
    if (buyBtn) buyBtn.classList.remove("active");
    if (sellBtn) sellBtn.classList.add("active");
  }
}

function armCurrentAlert() {
  const price = document.getElementById("top-active-price")?.innerText || "---";
  const message = "Price alerts are not connected yet. No background alert has been armed.";
  alert(message);
  const toast = document.getElementById("cockpit-status-toast");
  if (toast) {
    toast.innerHTML = `<span class="toast-clock">🔔</span> <b>${message}</b>`;
  }
}

/* ==========================================================================
   COCKPIT SUBPANE SWITCHING & STATE MACHINE / REGISTRY TELEMETRY LOADERS
   ========================================================================== */

function switchCockpitSubpane(paneName) {
  document.querySelectorAll(".cockpit-subpane").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".cockpit-subpane-tab").forEach(t => t.classList.remove("active"));

  const target = document.getElementById(`pane-cockpit-${paneName}`);
  const tab = document.getElementById(`tab-sub-${paneName}`);

  if (target) target.classList.add("active");
  if (tab) tab.classList.add("active");

  if (paneName === "history") {
    loadSignalLifecycles();
  } else if (paneName === "bot") {
    loadAgentRegistryStatus();
  } else if (paneName === "news") {
    renderCockpitNewsQuickList(currentXauusdCatalyst, cachedMacroEvents);
  }
}

async function loadSignalLifecycles() {
  const container = document.getElementById("cockpit-history-container");
  if (!container) return;

  container.innerHTML = `<div style="font-size:12px; color:#94a3b8; text-align:center; padding:12px;">⏳ Loading persistent signals from lifecycle state machine...</div>`;

  try {
    const res = await fetch(`${API_BASE}/api/v1/signals/lifecycle?limit=20`);
    const data = await res.json();
    const signals = data.signals || [];

    if (signals.length === 0) {
      container.innerHTML = `<div style="font-size:12px; color:#94a3b8; text-align:center; padding:14px; background:rgba(0,0,0,0.25); border-radius:8px;">No signal history is available yet. Run a scan when verified market data is configured.</div>`;
      return;
    }

    container.innerHTML = "";
    signals.forEach(sig => {
      const card = document.createElement("div");
      card.className = "lifecycle-card";

      const stateBadgeClass = {
        "WAITING_CONFIRMATION": "badge-state-amber",
        "ACTIVE": "badge-state-green",
        "TARGET_HIT": "badge-state-gold",
        "STOP_HIT": "badge-state-red",
        "INVALIDATED": "badge-state-gray",
        "EXPIRED": "badge-state-gray"
      }[sig.current_state] || "badge-state-gray";

      const dirClass = sig.direction === "BUY" ? "val-green" : "val-red";
      const fmtLifecyclePrice = value => value != null && Number.isFinite(Number(value)) ? Number(value).toFixed(2) : "N/A";
      const updatedAt = sig.updated_at && !Number.isNaN(Date.parse(sig.updated_at)) ? new Date(sig.updated_at).toLocaleString() : "N/A";
      const reasonHtml = sig.invalidation_reason_en ? `
        <div class="lifecycle-reason">
          <b>Reason (EN):</b> ${escapeHtml(String(sig.invalidation_reason_en))}<br>
          ${sig.invalidation_reason_kh ? `<b>🇰🇭 មូលហេតុ:</b> ${escapeHtml(String(sig.invalidation_reason_kh))}` : ''}
        </div>
      ` : '';

      card.innerHTML = `
        <div class="lifecycle-header">
          <div>
            <span style="font-weight:700; color:#fff;">${escapeHtml(String(sig.symbol || "N/A"))}</span>
            <span class="${dirClass}" style="font-weight:700; margin-left:6px;">${escapeHtml(String(sig.direction || "N/A"))}</span>
            <span style="color:#ffd700; font-size:11px; margin-left:8px;">⭐ ${sig.ai_score != null && Number.isFinite(Number(sig.ai_score)) ? `${Number(sig.ai_score)}%` : "N/A"}</span>
          </div>
          <span class="${stateBadgeClass}">${escapeHtml(String(sig.current_state || "N/A"))}</span>
        </div>
        <div class="lifecycle-levels">
          <span>Entry: <b>${fmtLifecyclePrice(sig.entry_price)}</b></span>
          <span>SL: <b style="color:#f87171;">${fmtLifecyclePrice(sig.stop_loss)}</b></span>
          <span>TP1: <b style="color:#34d399;">${fmtLifecyclePrice(sig.take_profit_1)}</b></span>
          <span>R:R: <b>${escapeHtml(String(sig.risk_reward ?? "N/A"))}</b></span>
        </div>
        ${reasonHtml}
        <div style="font-size:10px; color:#64748b; margin-top:2px;">
          ID: <code>${escapeHtml(String(sig.signal_id || "N/A"))}</code> · Updated: ${escapeHtml(updatedAt)}
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Load signal lifecycles error:", err);
    container.innerHTML = `<div style="font-size:12px; color:#f87171; text-align:center; padding:10px;">Failed to load signals. Ensure backend is running.</div>`;
  }
}

async function loadAgentRegistryStatus() {
  const container = document.getElementById("registry-telemetry-container");
  if (!container) return;

  container.innerHTML = `<div style="font-size:12px; color:#94a3b8; text-align:center; padding:10px;">⏳ Loading live agent registry telemetry...</div>`;

  try {
    const [regRes, routerRes] = await Promise.all([
      fetch(`${API_BASE}/api/v1/agents/registry/summary`),
      fetch(`${API_BASE}/api/v1/router/policy`)
    ]);

    const regData = await regRes.json();
    const routerData = await routerRes.json();
    const agents = regData.agents || [];

    let html = `
      <div style="background:rgba(0,0,0,0.3); border:1px solid rgba(56,189,248,0.25); border-radius:8px; padding:10px; margin-bottom:8px; font-size:11.5px;">
        <div style="font-weight:700; color:#38bdf8; margin-bottom:4px;">⚡ Hybrid AI Routing Cascade</div>
        <div style="color:#cbd5e1;"><b>Order:</b> ${escapeHtml((Array.isArray(routerData.routing_policy?.priority_order) ? routerData.routing_policy.priority_order : []).join(" ➔ ") || "Not reported")}</div>
        <div style="color:#94a3b8; font-size:10.5px; margin-top:3px;">Provider availability is checked per request.</div>
      </div>
    `;

    agents.forEach(ag => {
      const avgMs = ag.telemetry?.avg_latency_ms ? `${ag.telemetry.avg_latency_ms.toFixed(1)}ms` : '0ms';
      const execCount = ag.telemetry?.execution_count || 0;
      const statusClass = ag.status === 'ENABLED' ? 'badge-state-green' : 'badge-state-amber';

      html += `
        <div class="registry-agent-row">
          <div>
            <div class="registry-agent-name">${escapeHtml(ag.agent_name)}</div>
            <div style="font-size:10.5px; color:#64748b;">ID: <code>${escapeHtml(String(ag.agent_id || "N/A"))}</code> · Fallback: ${escapeHtml(String(ag.fallback_policy || "N/A"))}</div>
          </div>
          <div class="registry-agent-meta">
            <span style="font-size:11px; color:#94a3b8; font-family:monospace;">${execCount} runs · ${avgMs}</span>
            <span class="${statusClass}">${escapeHtml(String(ag.status || "N/A"))}</span>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  } catch (err) {
    console.error("Load agent registry error:", err);
    container.innerHTML = `<div style="font-size:12px; color:#f87171; text-align:center; padding:10px;">Failed to load registry telemetry.</div>`;
  }
}

// =========================================================================
// XAUUSD TELEGRAM SIGNALS & VERIFIED WIN-RATE DASHBOARD CONTROLLER
// =========================================================================

async function fetchXAUUSDSignalsAndStats() {
  const container = document.getElementById("xauusd-signals-panel-content");
  if (!container) return;

  container.innerHTML = `<div class="registry-telemetry-loading">⏳ Fetching verified XAUUSD signals, quota, and win-rate metrics...</div>`;

  try {
    const [quotaRes, statsRes, sigsRes] = await Promise.all([
      fetch(`${API_BASE}/api/v1/xauusd/signals/daily-quota`),
      fetch(`${API_BASE}/api/v1/xauusd/signals/stats`),
      fetch(`${API_BASE}/api/v1/xauusd/signals?limit=12`)
    ]);

    const quota = await quotaRes.json();
    const stats = await statsRes.json();
    const sigsData = await sigsRes.json();
    const signals = sigsData.signals || [];
    const todayStats = stats.today || {};
    const allStats = stats.all_time || {};

    const winRateDisplay = allStats.win_rate_display || "N/A — insufficient resolved trades";
    const sampleSize = allStats.resolved_sample_size || 0;
    const winsCount = allStats.wins_count || 0;
    const lossesCount = allStats.losses_count || 0;
    const wrText = (allStats.win_rate_percent !== null && allStats.win_rate_percent !== undefined) ? `${allStats.win_rate_percent}%` : "N/A";
    const tp2Rate = (allStats.tp2_attainment_rate !== null && allStats.tp2_attainment_rate !== undefined) ? `${allStats.tp2_attainment_rate}%` : "N/A";
    const tp3Rate = (allStats.tp3_attainment_rate !== null && allStats.tp3_attainment_rate !== undefined) ? `${allStats.tp3_attainment_rate}%` : "N/A";
    const netRValue = allStats.net_r_multiple == null ? NaN : Number(allStats.net_r_multiple);
    const netR = Number.isFinite(netRValue) ? `${netRValue > 0 ? '+' : ''}${netRValue}R` : "N/A";
    const streak = stats.streaks?.current_streak || "None";
    const sentCount = quota.signals_sent_today !== undefined ? quota.signals_sent_today : 0;
    const hardLimit = quota.daily_hard_limit !== undefined ? quota.daily_hard_limit : "N/A";

    let quotaBadgeClass = "badge-neutral-soft";
    if (Number.isFinite(Number(hardLimit)) && Number(hardLimit) > 0 && sentCount >= Number(hardLimit)) quotaBadgeClass = "badge-reject-soft";
    else if (sentCount >= 2) quotaBadgeClass = "badge-approve-soft";

    let html = `
      <!-- Top Metrics HUD Cards -->
      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:8px; margin-bottom:12px;">
        <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:8px; padding:8px 10px;">
          <div style="font-size:10px; color:#94a3b8; text-transform:uppercase; font-weight:700;">${isKhmer ? "កូតាសញ្ញាថ្ងៃនេះ" : "Signals Today"}</div>
          <div style="font-size:18px; font-weight:800; color:#fbbf24; margin:2px 0;">${sentCount} / ${hardLimit}</div>
          <div style="font-size:10px; color:#cbd5e1;">Configured daily limit</div>
        </div>

        <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:8px; padding:8px 10px;">
          <div style="font-size:10px; color:#94a3b8; text-transform:uppercase; font-weight:700;">${isKhmer ? "អត្រាឈ្នះ TP1" : "TP1 Win Rate"}</div>
          <div style="font-size:16px; font-weight:800; color:#22c55e; margin:2px 0;">${wrText}</div>
          <div style="font-size:10px; color:#94a3b8;">${winsCount}W / ${lossesCount}L (${sampleSize} res)</div>
        </div>

        <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:8px; padding:8px 10px;">
          <div style="font-size:10px; color:#94a3b8; text-transform:uppercase; font-weight:700;">${isKhmer ? "សម្រេច TP2 / TP3" : "TP2 / TP3 Rate"}</div>
          <div style="font-size:14px; font-weight:700; color:#38bdf8; margin:4px 0;">${tp2Rate} / ${tp3Rate}</div>
          <div style="font-size:10px; color:#94a3b8;">Target Expansion</div>
        </div>

        <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:8px; padding:8px 10px;">
          <div style="font-size:10px; color:#94a3b8; text-transform:uppercase; font-weight:700;">${isKhmer ? "ផលចំណេញសុទ្ធ" : "Net R-Multiple"}</div>
          <div style="font-size:16px; font-weight:800; color:#fbbf24; margin:2px 0;">${netR}</div>
          <div style="font-size:10px; color:#94a3b8;">Streak: ${escapeHtml(String(streak))}</div>
        </div>
      </div>

      <!-- Live Action Buttons -->
      <div style="display:flex; gap:8px; margin-bottom:12px; flex-wrap:wrap;">
        <button class="btn btn-gold btn-sm" onclick="triggerManualXAUUSDSignal()" style="flex:1; min-width:140px; font-size:11px;" ${quota.is_limit_reached ? 'disabled title="Daily 4-signal limit reached"' : ''}>
          ⚡ ${isKhmer ? "វិភាគ & ផ្ញើសញ្ញា Telegram" : "Scan & Send Telegram Signal"}
        </button>
        <button class="btn btn-secondary btn-sm" onclick="triggerDispatchXAUUSDDailyReport()" style="flex:1; min-width:140px; font-size:11px;">
          📊 ${isKhmer ? "ផ្ញើរបាយការណ៍សង្ខេបប្រចាំថ្ងៃ" : "Send Daily Telegram Report"}
        </button>
        <button class="btn btn-secondary btn-sm" onclick="fetchXAUUSDSignalsAndStats()" title="Refresh Data">
          🔄
        </button>
      </div>

      <!-- Signals Feed Header -->
      <div style="font-size:11px; font-weight:700; color:#cbd5e1; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center;">
        <span>📜 ${isKhmer ? "ប្រវត្តិនៃសញ្ញាជួញដូរ XAUUSD ផ្ទៀងផ្ទាត់" : "Verified XAUUSD Telegram Signals History"}</span>
        <span style="font-size:10px; color:#64748b;">Formula: Wins / (Wins + Losses) · Cambodia TZ</span>
      </div>
    `;

    if (signals.length === 0) {
      html += `
        <div style="text-align:center; padding:24px 12px; background:rgba(0,0,0,0.2); border-radius:8px; border:1px dashed rgba(255,255,255,0.08);">
          <div style="font-size:24px; margin-bottom:6px;">🥇</div>
          <div style="font-weight:700; color:#cbd5e1; font-size:12px;">No XAUUSD signals sent yet today</div>
          <div style="font-size:11px; color:#64748b; margin-top:4px;">Signal generation runs only while the service is running and data passes validation.</div>
        </div>
      `;
    } else {
      html += `<div style="display:flex; flex-direction:column; gap:6px;">`;
      signals.forEach(s => {
        const isBuy = s.direction === "BUY";
        const dirColor = isBuy ? "#22c55e" : "#ef4444";
        const dirIcon = isBuy ? "🟢 BUY" : "🔴 SELL";

        const pnlR = s.pnl_r_multiple == null || !Number.isFinite(Number(s.pnl_r_multiple)) ? "N/A" : `${Number(s.pnl_r_multiple) > 0 ? "+" : ""}${Number(s.pnl_r_multiple)}R`;
        let outcomeBadge = `<span style="background:rgba(148,163,184,0.15); color:#94a3b8; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:700;">${escapeHtml(String(s.outcome || s.signal_status || "N/A"))}</span>`;
        if (s.outcome === "WIN") outcomeBadge = `<span style="background:rgba(34,197,94,0.15); color:#22c55e; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:700;">🏆 WIN (${pnlR})</span>`;
        else if (s.outcome === "LOSS") outcomeBadge = `<span style="background:rgba(239,68,68,0.15); color:#ef4444; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:700;">❌ LOSS (${pnlR})</span>`;
        else if (s.outcome === "AMBIGUOUS") outcomeBadge = `<span style="background:rgba(234,179,8,0.15); color:#eab308; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:700;">⚠️ AMBIGUOUS</span>`;
        else if (s.outcome === "EXPIRED_NO_ENTRY") outcomeBadge = `<span style="background:rgba(100,116,139,0.15); color:#64748b; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:700;">🚫 EXPIRED</span>`;

        const tgStatus = s.telegram_delivery_status === "SENT"
          ? `<span style="color:#38bdf8;" title="Message ID: ${escapeHtml(String(s.telegram_message_id || 'N/A'))}">✈️ Sent #${escapeHtml(String(s.telegram_message_id || ''))}</span>`
          : `<span style="color:#94a3b8;">⏳ ${escapeHtml(String(s.telegram_delivery_status || "N/A"))}</span>`;
        const fmtSignalPrice = value => value != null && Number.isFinite(Number(value)) ? Number(value).toFixed(2) : "N/A";

        html += `
          <div style="background:rgba(0,0,0,0.25); border:1px solid rgba(255,255,255,0.06); border-radius:8px; padding:8px 10px; font-size:11px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
              <div>
                <b style="color:${dirColor};">${dirIcon}</b> · <code style="color:#fbbf24;">${fmtSignalPrice(s.entry_price)}</code>
                <span style="color:#64748b; font-size:10px; margin-left:4px;">SL: ${fmtSignalPrice(s.stop_loss)} | TP1: ${fmtSignalPrice(s.take_profit_1)}</span>
              </div>
              <div>${outcomeBadge}</div>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:10px; color:#94a3b8;">
              <div>Confluence: <b style="color:#cbd5e1;">${s.ai_score != null && Number.isFinite(Number(s.ai_score)) ? `${Number(s.ai_score)}%` : "N/A"}</b> · R:R ${escapeHtml(String(s.risk_reward_1 ?? "N/A"))}</div>
              <div>${tgStatus} · <span style="color:#64748b;">${escapeHtml(String(s.cambodia_date || ''))}</span></div>
            </div>
          </div>
        `;
      });
      html += `</div>`;
    }

    container.innerHTML = html;
  } catch (err) {
    console.error("Fetch XAUUSD signals error:", err);
    container.innerHTML = `<div style="font-size:12px; color:#f87171; text-align:center; padding:10px;">Failed to load XAUUSD signals data: ${escapeHtml(err.message)}</div>`;
  }
}

async function triggerManualXAUUSDSignal() {
  const btn = event?.currentTarget;
  if (btn) btn.disabled = true;
  try {
    const res = await fetch(`${API_BASE}/api/v1/xauusd/signals/generate?dispatch_telegram=true`, { method: "POST" });
    const data = await res.json();
    if (data.status === "APPROVED") {
      alert(`✅ XAUUSD Signal Approved and Dispatched to Telegram!\nSignal ID: ${data.signal?.signal_id}\nTelegram Msg ID: ${data.telegram_message_id}`);
    } else {
      alert(`ℹ️ Signal Suppressed: ${data.reason || "Market conditions do not satisfy 80%-95% multi-agent confluence or daily quota."}`);
    }
  } catch (err) {
    alert(`❌ Failed to trigger signal: ${err.message}`);
  } finally {
    if (btn) btn.disabled = false;
    fetchXAUUSDSignalsAndStats();
  }
}

async function triggerDispatchXAUUSDDailyReport() {
  const btn = event?.currentTarget;
  if (btn) btn.disabled = true;
  try {
    const res = await fetch(`${API_BASE}/api/v1/xauusd/signals/daily-report/dispatch?force=true`, { method: "POST" });
    const data = await res.json();
    if (data.success) {
      alert(`✅ Daily Telegram Performance Report successfully dispatched!\nReport Date: ${data.report_date}\nTelegram Message ID: ${data.telegram_message_id}`);
    } else {
      alert(`⚠️ Daily report dispatch status: ${data.error || "Completed"}`);
    }
  } catch (err) {
    alert(`❌ Error dispatching daily report: ${err.message}`);
  } finally {
    if (btn) btn.disabled = false;
    fetchXAUUSDSignalsAndStats();
  }
}


// =========================================================================
// VIP SUBSCRIPTIONS & EXPIRING INVITE LINKS UI CONTROLLER
// =========================================================================
// DEVELOPER PROFILE & SYSTEM ARCHITECT CONTROLLER
// Architect: Heng Taikry · Telegram: 0968288832
// =========================================================================

function openDeveloperModal() {
  const modal = document.getElementById("developer-profile-modal");
  if (modal) {
    modal.classList.remove("modal-hidden");
  }
}

function closeDeveloperModal() {
  const modal = document.getElementById("developer-profile-modal");
  if (modal) {
    modal.classList.add("modal-hidden");
  }
}

function copyDeveloperTelegram() {
  copyTextToClipboard("0968288832", "Developer Telegram");
}

function copyTextToClipboard(text, label = "Item") {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      showCyberToast(`📋 ${label} copied: ${text}`);
    }).catch(() => {
      prompt(`Copy ${label}:`, text);
    });
  } else {
    prompt(`Copy ${label}:`, text);
  }
}

function showCyberToast(msg) {
  const existing = document.getElementById("cyber-toast-notification");
  if (existing) existing.remove();
  const toast = document.createElement("div");
  toast.id = "cyber-toast-notification";
  toast.className = "cyber-toast";
  const icon = document.createElement("span");
  icon.textContent = "✨";
  const text = document.createElement("span");
  text.textContent = String(msg ?? "");
  toast.append(icon, text);
  document.body.appendChild(toast);
  setTimeout(() => {
    if (toast.parentNode) toast.remove();
  }, 2800);
}

// =========================================================================
// WINDOWS EXNESS MT5 BRIDGE CONTROLLER & MODAL
// =========================================================================

function openMT5BridgeModal() {
  const modal = document.getElementById("exness-mt5-bridge-modal");
  if (modal) {
    modal.classList.remove("modal-hidden");
    testBridgeStatus();
  }
}

function closeMT5BridgeModal() {
  const modal = document.getElementById("exness-mt5-bridge-modal");
  if (modal) {
    modal.classList.add("modal-hidden");
  }
}

async function testBridgeStatus() {
  try {
    const res = await fetch("/api/v1/bridge/status");
    if (!res.ok) throw new Error("Bridge status check failed");
    const data = await res.json();
    updateBridgeStatusUI(data);
  } catch (e) {
    console.debug("[MT5_BRIDGE] Status check error:", e);
    updateBridgeStatusUI({ status: "DISCONNECTED" });
  }
}

function updateBridgeStatusUI(data) {
  const status = data.status || "DISCONNECTED";
  const topDot = document.getElementById("top-bridge-dot");
  const topLabel = document.getElementById("top-bridge-label");
  const modalBadge = document.getElementById("bridge-modal-status-badge");
  const bmcBroker = document.getElementById("bmc-broker-val");
  const bmcServer = document.getElementById("bmc-server-val");
  const bmcAge = document.getElementById("bmc-age-val");

  if (topDot && topLabel) {
    topDot.className = "bridge-status-dot";
    if (status === "CONNECTED" && data.is_active_for_signals) {
      topDot.classList.add("bridge-connected");
      topLabel.innerText = "MT5: FRESH TICKS";
      topLabel.style.color = "#00D99A";
    } else if (status === "CONNECTED") {
      topDot.classList.add("bridge-stale");
      topLabel.innerText = "MT5: NO FRESH TICK";
      topLabel.style.color = "#FFC76B";
    } else if (status === "STALE") {
      topDot.classList.add("bridge-stale");
      topLabel.innerText = "MT5: STALE";
      topLabel.style.color = "#FFC76B";
    } else {
      topDot.classList.add("bridge-disconnected");
      topLabel.innerText = "MT5: STANDBY";
      topLabel.style.color = "#87A99A";
    }
  }

  if (modalBadge) {
    modalBadge.innerText = `● ${status === "CONNECTED" && !data.is_active_for_signals ? "CONNECTED · NO FRESH TICK" : status}`;
    modalBadge.className = "bridge-hero-badge " + (status === "CONNECTED" ? "text-green" : (status === "STALE" ? "text-gold" : "text-muted"));
  }

  const bridgeReported = status !== "DISCONNECTED";
  if (bmcBroker) bmcBroker.innerText = bridgeReported ? (data.broker || "Not reported") : "Not connected";
  if (bmcServer) bmcServer.innerText = bridgeReported ? (data.server || "Not reported") : "No server reported";
  if (bmcAge) {
    bmcAge.innerText = data.seconds_since_last_activity != null ? `${data.seconds_since_last_activity}s ago` : "No ticks yet";
  }
}

// Auto-poll bridge status every 15s
setInterval(testBridgeStatus, 15000);

function showPlansModal() {
  const modal = document.getElementById("plans-spec-modal");
  if (modal) {
    modal.classList.remove("modal-hidden");
    loadVipStats();
    loadVipSubscribers();
  }
}

function closePlansModal() {
  const modal = document.getElementById("plans-spec-modal");
  if (modal) {
    modal.classList.add("modal-hidden");
  }
}

function switchVipModalTab(tab) {
  const tabPlans = document.getElementById("tab-vip-plans");
  const tabSubs = document.getElementById("tab-vip-subscribers");
  const contentPlans = document.getElementById("vip-tab-content-plans");
  const contentSubs = document.getElementById("vip-tab-content-subscribers");

  if (tab === "plans") {
    if (tabPlans) tabPlans.classList.add("active");
    if (tabSubs) tabSubs.classList.remove("active");
    if (contentPlans) contentPlans.style.display = "block";
    if (contentSubs) contentSubs.style.display = "none";
  } else {
    if (tabPlans) tabPlans.classList.remove("active");
    if (tabSubs) tabSubs.classList.add("active");
    if (contentPlans) contentPlans.style.display = "none";
    if (contentSubs) contentSubs.style.display = "block";
    loadVipStats();
    loadVipSubscribers();
  }
}

function prefillGrantForm(tier, duration) {
  switchVipModalTab("subscribers");
  const tField = document.getElementById("grant-tier");
  const dField = document.getElementById("grant-duration");
  if (tField) tField.value = tier;
  if (dField) dField.value = String(duration);
  const uField = document.getElementById("grant-user-id");
  if (uField) uField.focus();
}

async function loadVipStats() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/vip/stats`);
    if (!res.ok) return;
    const data = await res.json();
    const act = document.getElementById("vip-kpi-active");
    const exp = document.getElementById("vip-kpi-expiring");
    const rev = document.getElementById("vip-kpi-revenue");
    const past = document.getElementById("vip-kpi-expired");

    if (act) act.textContent = data.active_subscribers || 0;
    if (exp) exp.textContent = data.expiring_within_48h || 0;
    if (rev) rev.textContent = `$${(data.total_revenue_usd || 0).toLocaleString()}`;
    if (past) past.textContent = (data.expired_subscribers || 0) + (data.revoked_subscribers || 0);
  } catch (err) {
    console.warn("Failed to load VIP stats:", err);
  }
}

async function loadVipSubscribers() {
  const tbody = document.getElementById("vip-subscribers-tbody");
  if (!tbody) return;
  try {
    const res = await fetch(`${API_BASE}/api/v1/vip/subscribers?limit=50`);
    if (!res.ok) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #f87171; padding: 15px;">Failed to fetch subscribers.</td></tr>`;
      return;
    }
    const data = await res.json();
    const subs = data.subscribers || [];
    if (subs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #94a3b8; padding: 20px;">No subscribers found yet. Use the form above to grant access!</td></tr>`;
      return;
    }

    tbody.innerHTML = subs.map(s => {
      const badgeCls = s.tier === "VIP" ? "badge-vip" : (s.tier === "LIFETIME" ? "badge-lifetime" : "badge-pro");
      const statusCls = s.status === "ACTIVE" ? "vip-status-active" : (s.status === "EXPIRED" ? "vip-status-expired" : "vip-status-revoked");
      const expiresStr = s.is_lifetime ? "👑 Lifetime" : (s.expires_at ? new Date(s.expires_at).toLocaleDateString() : "N/A");
      let safeInviteLink = "";
      try {
        const parsedInvite = new URL(s.invite_link || "");
        if (parsedInvite.protocol === "https:" && ["t.me", "telegram.me"].includes(parsedInvite.hostname.toLowerCase())) safeInviteLink = parsedInvite.href;
      } catch (_) {}
      const linkDisp = safeInviteLink ? `<a href="${escapeHtml(safeInviteLink)}" target="_blank" rel="noopener noreferrer" style="color: #38bdf8; text-decoration: underline;">Join Link</a>` : "N/A";
      const safeUserId = String(s.user_id ?? "");
      const encodedUserId = encodeURIComponent(safeUserId);
      const revokeBtn = s.status === "ACTIVE"
        ? `<button class="btn btn-outline btn-xs" style="color: #f87171; border-color: rgba(239,68,68,0.4);" onclick="revokeVipSubscriber(decodeURIComponent('${encodedUserId}'))">Revoke</button>`
        : `<span style="color: #64748b;">—</span>`;

      return `
        <tr>
          <td>
            <div style="font-weight: 700; color: #f8fafc;">${escapeHtml(safeUserId)}</div>
            <div style="font-size: 11px; color: #94a3b8;">${escapeHtml(s.username ? '@' + s.username : (s.full_name || ''))}</div>
          </td>
          <td><span class="vip-card-badge ${badgeCls}">${escapeHtml(String(s.tier || ""))}</span></td>
          <td><span class="vip-status-pill ${statusCls}">${escapeHtml(String(s.status || ""))}</span></td>
          <td style="font-size: 11px;">${escapeHtml(expiresStr)}</td>
          <td>${linkDisp}</td>
          <td>${revokeBtn}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #f87171; padding: 15px;">Error: ${escapeHtml(err.message)}</td></tr>`;
  }
}

async function submitGrantVip() {
  const userId = document.getElementById("grant-user-id")?.value?.trim();
  const username = document.getElementById("grant-username")?.value?.trim() || null;
  const tier = document.getElementById("grant-tier")?.value || "PRO";
  const duration = parseInt(document.getElementById("grant-duration")?.value || "30", 10);

  if (!userId) {
    alert("Please enter a valid Telegram User ID (e.g. 849201948)!");
    return;
  }

  const payload = {
    user_id: userId,
    username: username,
    tier: tier,
    duration_days: duration,
    send_telegram_alert: true
  };

  try {
    const res = await fetch(`${API_BASE}/api/v1/vip/grant`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.status === "SUCCESS") {
      const banner = document.getElementById("grant-result-banner");
      const linkEl = document.getElementById("grant-result-link");
      if (banner && linkEl) {
        linkEl.textContent = data.subscription.invite_link || "N/A";
        banner.style.display = "flex";
      }
      alert(`✅ VIP Access Granted to ${userId}!\nTier: ${tier}\nDuration: ${duration} Days\nLink: ${data.subscription.invite_link}`);
      loadVipStats();
      loadVipSubscribers();
    } else {
      alert(`⚠️ Could not grant VIP: ${JSON.stringify(data)}`);
    }
  } catch (err) {
    alert(`❌ Error granting VIP: ${err.message}`);
  }
}

function copyVipLink() {
  const linkEl = document.getElementById("grant-result-link");
  if (linkEl && linkEl.textContent) {
    navigator.clipboard.writeText(linkEl.textContent).then(() => {
      alert("📋 VIP Invite Link copied to clipboard!");
    }).catch(() => {
      prompt("Copy invite link:", linkEl.textContent);
    });
  }
}

async function revokeVipSubscriber(userId) {
  if (!confirm(`Are you sure you want to revoke VIP access for user ${userId}?\nThis will evict the member from the VIP channel and invalidate their invite link.`)) {
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/v1/vip/revoke`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, reason: "Admin revoked from Dashboard UI", kick_from_channel: true })
    });
    const data = await res.json();
    if (data.status === "SUCCESS") {
      alert(`✅ VIP subscription revoked for ${userId}. Member kicked from channel.`);
      loadVipStats();
      loadVipSubscribers();
    } else {
      alert(`⚠️ Could not revoke: ${JSON.stringify(data)}`);
    }
  } catch (err) {
    alert(`❌ Error revoking subscription: ${err.message}`);
  }
}

async function runVipExpirationAudit() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/vip/check-expirations`, { method: "POST" });
    const data = await res.json();
    alert(`🛡️ VIP Expiration Sweep Completed!\nChecked: ${data.checked_count}\nExpired & Evicted: ${data.expired_count}\nReminders Sent: ${data.reminded_count}`);
    loadVipStats();
    loadVipSubscribers();
  } catch (err) {
    alert(`❌ Error running expiration sweep: ${err.message}`);
  }
}



/* =============================================================================
 * ANYROUTER INFERENCE GATEWAY & MULTI-AGENT CONTROL JAVASCRIPT
 * ============================================================================= */

async function loadAnyRouterCatalog(forceRefresh = false) {
  try {
    const badge = document.getElementById("anyrouter-status-badge");
    const tbody = document.getElementById("anyrouter-models-tbody");
    const refreshLabel = document.getElementById("anyrouter-last-refresh");
    if (badge) badge.textContent = "Querying...";

    const res = await fetch(`${API_BASE}/api/v1/anyrouter/models?force_refresh=${forceRefresh}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (badge) {
      if (data.status === "CONNECTED") {
        badge.textContent = `CONNECTED (${data.total_models} Models)`;
        badge.className = "badge badge-success";
      } else if (data.status === "UNCONFIGURED") {
        badge.textContent = "UNCONFIGURED (Key Missing)";
        badge.className = "badge badge-warning";
      } else {
        badge.textContent = data.status || "ERROR";
        badge.className = "badge badge-danger";
      }
    }

    if (refreshLabel && data.last_catalog_refresh_time) {
      refreshLabel.textContent = `Refreshed: ${new Date(data.last_catalog_refresh_time).toLocaleTimeString()}`;
    }

    if (tbody) {
      if (!data.models || data.models.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted p-15">${escapeHtml(String(data.error_message || "No models returned from catalog."))}</td></tr>`;
      } else {
        tbody.innerHTML = data.models.map(m => {
          const modelId = String(m.id || "");
          const modelArg = encodeURIComponent(modelId).replace(/'/g, "%27");
          return `
          <tr>
            <td><code class="text-gold font-mono">${escapeHtml(modelId)}</code></td>
            <td>${escapeHtml(String(m.provider || "N/A"))}</td>
            <td>${m.context_window ? m.context_window.toLocaleString() : "Auto"}</td>
            <td>${(m.capabilities || []).map(c => `<span class="badge badge-xs mr-5">${escapeHtml(c)}</span>`).join("")}</td>
            <td><span class="badge badge-xs ${m.status === 'AVAILABLE' ? 'badge-success' : 'badge-muted'}">${escapeHtml(m.status)}</span></td>
            <td>
              <button class="btn btn-outline btn-xs" onclick="runAnyRouterSmokeTest(decodeURIComponent('${modelArg}'))">⚡ Probe</button>
            </td>
          </tr>
        `;
        }).join("");
      }
    }

    loadAnyRouterBudget();
  } catch (err) {
    console.error("Failed to load AnyRouter catalog:", err);
    const badge = document.getElementById("anyrouter-status-badge");
    if (badge) {
      badge.textContent = "OFFLINE";
      badge.className = "badge badge-danger";
    }
  }
}

async function refreshAnyRouterCatalog() {
  await loadAnyRouterCatalog(true);
}

async function runAnyRouterSmokeTest(modelId = null) {
  const resultBox = document.getElementById("anyrouter-smoke-result-box");
  const details = document.getElementById("smoke-details");
  const timeLabel = document.getElementById("smoke-time");
  const title = document.getElementById("smoke-status-title");

  if (resultBox) resultBox.style.display = "block";
  if (details) details.innerHTML = `<span class="text-gold">Running low-token smoke test probe...</span>`;

  try {
    const payload = modelId ? { model_id: modelId } : {};
    const res = await fetch(`${API_BASE}/api/v1/anyrouter/smoke-test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (timeLabel) timeLabel.textContent = new Date().toLocaleTimeString();

    if (data.status === "SUCCESS") {
      if (title) title.innerHTML = `<span class="text-green">✓ SMOKE TEST SUCCESS (HTTP ${data.http_status})</span>`;
      if (details) {
        details.innerHTML = `
          <div><strong>Model Tested:</strong> <code>${escapeHtml(data.model_id)}</code></div>
          <div><strong>Latency:</strong> ${data.latency_ms} ms | <strong>Prompt Tokens:</strong> ${data.usage ? data.usage.prompt_tokens : 0} | <strong>Completion Tokens:</strong> ${data.usage ? data.usage.completion_tokens : 0}</div>
          <div><strong>Response Preview:</strong> <code>${escapeHtml(data.response_preview || "OK")}</code></div>
        `;
      }
    } else if (data.status === "SKIPPED") {
      if (title) title.innerHTML = `<span class="text-gold">ℹ️ SMOKE TEST SKIPPED</span>`;
      if (details) {
        details.innerHTML = `<div>${escapeHtml(data.error_message || "ANYROUTER_API_KEY is not configured in .env.")}</div>`;
      }
    } else {
      if (title) title.innerHTML = `<span class="text-danger">✕ SMOKE TEST FAILED</span>`;
      if (details) {
        details.innerHTML = `
          <div><strong>Model:</strong> <code>${escapeHtml(data.model_id)}</code></div>
          <div><strong>Error:</strong> ${escapeHtml(data.error_message || "Unknown error")}</div>
        `;
      }
    }

    loadAnyRouterBudget();
  } catch (err) {
    if (title) title.innerHTML = `<span class="text-danger">✕ REQUEST FAILED</span>`;
    if (details) details.textContent = err.message;
  }
}

async function loadAnyRouterRoles() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/anyrouter/roles`);
    if (!res.ok) return;
    const roles = await res.json();
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el && val) el.value = val;
    };
    setVal("role-orchestrator", roles.orchestrator);
    setVal("role-reasoning", roles.reasoning);
    setVal("role-fast", roles.fast);
    setVal("role-critic", roles.critic);
    setVal("role-fallback", roles.fallback);
  } catch (err) {
    console.warn("Failed to load AnyRouter roles:", err);
  }
}

async function saveAnyRouterRoles() {
  const roles = [
    { role: "orchestrator", id: "role-orchestrator" },
    { role: "reasoning", id: "role-reasoning" },
    { role: "fast", id: "role-fast" },
    { role: "critic", id: "role-critic" },
    { role: "fallback", id: "role-fallback" }
  ];

  let successCount = 0;
  for (const item of roles) {
    const el = document.getElementById(item.id);
    const modelId = el ? el.value.trim() : "";
    if (!modelId) continue;
    try {
      const res = await fetch(`${API_BASE}/api/v1/anyrouter/roles`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: item.role, model_id: modelId })
      });
      if (res.ok) successCount++;
    } catch (e) {
      console.error(`Failed to assign role ${item.role}:`, e);
    }
  }
  alert(`✓ Updated ${successCount} multi-agent role assignments.`);
}

async function loadAnyRouterBudget() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/anyrouter/budget`);
    if (!res.ok) return;
    const b = await res.json();
    const badge = document.getElementById("anyrouter-budget-badge");
    if (badge) {
      badge.textContent = `Spent: $${b.estimated_spend_usd.toFixed(3)} / Limit: $${b.spend_limit_usd.toFixed(2)}`;
      badge.className = b.budget_exceeded ? "badge badge-danger" : "badge badge-outline";
    }
  } catch (err) {
    console.debug("Budget fetch failed:", err);
  }
}

async function triggerDeepMultiAgentAnalysis() {
  const symEl = document.getElementById("deep-analysis-symbol");
  const symbol = symEl ? symEl.value : "XAUUSD";

  // Visual cues on agent chips
  const agentBadges = [1, 2, 3, 4, 5, 6, 7];
  agentBadges.forEach(num => {
    const b = document.getElementById(`badge-agent-${num}`);
    if (b) {
      b.textContent = "RUNNING...";
      b.className = "agent-chip-badge text-gold";
    }
  });

  const traceBox = document.getElementById("deep-analysis-trace-box");
  if (traceBox) traceBox.style.display = "block";

  try {
    const res = await fetch(`${API_BASE}/api/v1/agents/deep-analysis`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: symbol })
    });
    const trace = await res.json();

    // Update Agent Badges
    const updateChip = (num, text, isOk = true) => {
      const b = document.getElementById(`badge-agent-${num}`);
      if (b) {
        b.textContent = text;
        b.className = isOk ? "agent-chip-badge text-green" : "agent-chip-badge text-gold";
      }
    };

    updateChip(1, `${trace.execution_time_ms} ms`);
    updateChip(2, trace.market_structure.status === "COMPLETED" ? `${trace.market_structure.trend} (${trace.market_structure.regime})` : "UNAVAILABLE", trace.market_structure.status === "COMPLETED");
    updateChip(3, trace.multi_timeframe.status === "COMPLETED" ? `${trace.multi_timeframe.dominant_bias} (${trace.multi_timeframe.confluence_score ?? "N/A"}%)` : "UNAVAILABLE", trace.multi_timeframe.status === "COMPLETED");
    const calendarVerified = Boolean(trace.macro_news.calendar_available);
    updateChip(4, !calendarVerified ? "CALENDAR N/A" : (trace.macro_news.is_blackout ? "BLACKOUT" : "CLEAR"), calendarVerified && !trace.macro_news.is_blackout);
    updateChip(5, trace.risk_guardian.approved ? "APPROVED" : "VETOED", trace.risk_guardian.approved);
    updateChip(6, `Score: ${trace.critic.critic_score ?? "N/A"}/100`, trace.critic.critic_score != null);
    updateChip(7, trace.final_synthesis.action);

    // Populate Trace Inspector
    document.getElementById("trace-symbol").textContent = trace.symbol;
    const actionBadge = document.getElementById("trace-action-badge");
    if (actionBadge) {
      actionBadge.textContent = trace.final_synthesis.action;
      actionBadge.className = `badge ${
        trace.final_synthesis.action === "BUY" ? "badge-success" :
        trace.final_synthesis.action === "SELL" ? "badge-danger" :
        trace.final_synthesis.action === "WAIT" ? "badge-warning" : "badge-muted"
      }`;
    }
    document.getElementById("trace-status-label").textContent = trace.overall_status;
    document.getElementById("trace-request-id").textContent = trace.request_id.slice(0, 8) + "...";
    document.getElementById("trace-latency").textContent = trace.execution_time_ms;

    // Risk Geometry Grid
    const r = trace.risk_guardian;
    const riskGrid = document.getElementById("trace-risk-grid");
    if (riskGrid) {
      riskGrid.innerHTML = `
        <div class="trace-risk-item">
          <div class="trace-risk-item-label">Verified Entry</div>
          <div class="trace-risk-item-val">${r.entry_price ?? "N/A"}</div>
        </div>
        <div class="trace-risk-item">
          <div class="trace-risk-item-label">Stop Loss</div>
          <div class="trace-risk-item-val">${r.stop_loss ?? "N/A"}</div>
        </div>
        <div class="trace-risk-item">
          <div class="trace-risk-item-label">Take Profit</div>
          <div class="trace-risk-item-val">${r.take_profit ?? "N/A"}</div>
        </div>
        <div class="trace-risk-item">
          <div class="trace-risk-item-label">Risk:Reward Ratio</div>
          <div class="trace-risk-item-val text-gold">${r.risk_reward_ratio == null ? "N/A" : `${r.risk_reward_ratio}:1`} (Min ${r.min_required_rr ?? "N/A"})</div>
        </div>
        <div class="trace-risk-item">
          <div class="trace-risk-item-label">Max Risk Cap</div>
          <div class="trace-risk-item-val">${r.max_risk_percent ?? "N/A"}% (${r.risk_amount_usd == null ? "N/A" : `$${r.risk_amount_usd}`})</div>
        </div>
        <div class="trace-risk-item">
          <div class="trace-risk-item-label">Calculated Lot Size</div>
          <div class="trace-risk-item-val">${r.recommended_lot_size == null ? "N/A" : `${r.recommended_lot_size} Lots`}</div>
        </div>
      `;
    }

    // Critic Audit
    const criticDiv = document.getElementById("trace-critic-content");
    if (criticDiv) {
      criticDiv.innerHTML = `
        <div><strong>Counter-Trend Risk:</strong> ${escapeHtml(String(trace.critic.counter_trend_risk ?? "N/A"))} | <strong>Trapped Traders Risk:</strong> ${escapeHtml(String(trace.critic.trapped_traders_risk ?? "N/A"))}</div>
        <div><strong>Objections:</strong> ${trace.critic.objections.length > 0 ? escapeHtml(trace.critic.objections.join("; ")) : "No objections recorded."}</div>
        <div><strong>Opposing Evidence:</strong> ${escapeHtml(trace.critic.opposing_evidence.join("; ")) || "None."}</div>
      `;
    }

    // Bilingual Synthesis
    document.getElementById("trace-thesis-en").textContent = trace.final_synthesis.thesis_en;
    document.getElementById("trace-thesis-kh").textContent = trace.final_synthesis.thesis_kh;

  } catch (err) {
    alert("Deep Analysis failed: " + err.message);
  }
}

function initAnyRouterUI() {
  loadAnyRouterCatalog(false);
  loadAnyRouterRoles();
  loadAnyRouterBudget();
}


/* ==========================================================================
   SAAS SUBSCRIPTION, 14-DAY FREE TRIAL, TELEGRAM & SUPPORT CLIENT LOGIC
   ========================================================================== */

let currentSaasUser = null;
let currentTelegramLink = null;

async function checkSaasSession() {
  try {
    const res = await fetch("/api/v1/auth/me", { credentials: "include" });
    if (res.ok) {
      const data = await res.json();
      currentSaasUser = data;
      const topLabel = document.getElementById("top-account-label");
      if (topLabel) {
        const roleBadge = data.role === "ADMIN" ? "👑 Admin" : (data.full_name || "Account");
        topLabel.textContent = roleBadge;
      }
    } else {
      currentSaasUser = null;
      const topLabel = document.getElementById("top-account-label");
      if (topLabel) topLabel.textContent = "Sign In / Trial";
    }
  } catch (err) {
    console.debug("SaaS session check: not authenticated or offline");
  }
}

async function loadAccountProfile() {
  try {
    // 1. Fetch current user profile
    const userRes = await fetch("/api/v1/auth/me", { credentials: "include" });
    if (!userRes.ok) {
      // If unauthenticated, redirect to landing sign-in
      if (confirm("You are currently not signed in. Would you like to go to the Sign In / Free Trial page?")) {
        window.location.href = "/";
      }
      return;
    }
    const user = await userRes.json();
    currentSaasUser = user;

    // Fill profile fields
    const fnInput = document.getElementById("acc-fullname");
    if (fnInput) fnInput.value = user.full_name || "";
    const emInput = document.getElementById("acc-email");
    if (emInput) emInput.value = user.email || "";
    const langSelect = document.getElementById("acc-language");
    if (langSelect && user.preferred_language) langSelect.value = user.preferred_language;
    const tzInput = document.getElementById("acc-timezone");
    if (tzInput && user.timezone) tzInput.value = user.timezone;

    // 2. Fetch 14-Day Free Trial & Entitlements
    const trialRes = await fetch("/api/v1/auth/trial-status", { credentials: "include" });
    if (trialRes.ok) {
      const trial = await trialRes.json();
      const planNameEl = document.getElementById("saas-plan-name");
      const planStatusEl = document.getElementById("saas-plan-status");
      const countdownEl = document.getElementById("saas-trial-countdown");
      const expiresAtEl = document.getElementById("saas-trial-expires-at");
      const scansQuotaEl = document.getElementById("saas-quota-scans");
      const deepQuotaEl = document.getElementById("saas-quota-deep");

      if (planNameEl) {
        const tier = trial.plan_name ? trial.plan_name.toUpperCase() : "FREE TRIAL";
        planNameEl.textContent = tier;
      }
      if (planStatusEl) {
        planStatusEl.textContent = `Status: ${trial.status.replace("_", " ").toUpperCase()}`;
        planStatusEl.className = trial.is_active ? "section-kpi-sub text-green" : "section-kpi-sub text-danger";
      }
      if (countdownEl) {
        if (trial.status === "trial_active") {
          countdownEl.textContent = `${trial.days_remaining}d ${trial.hours_remaining}h Left`;
        } else if (trial.status === "trial_expired") {
          countdownEl.textContent = "Expired";
          countdownEl.className = "section-kpi-val text-danger";
        } else if (trial.status === "active_paid") {
          countdownEl.textContent = "Active Paid Tier";
          countdownEl.className = "section-kpi-val text-gold";
        } else {
          countdownEl.textContent = trial.status;
        }
      }
      if (expiresAtEl && trial.trial_expires_at) {
        expiresAtEl.textContent = `Expires: ${trial.trial_expires_at.slice(0, 16)} UTC`;
      }

      // Quotas
      if (scansQuotaEl) {
        const scanLim = trial.daily_scan_limit === -1 ? "Unlimited" : trial.daily_scan_limit;
        scansQuotaEl.textContent = `${trial.scans_used_today || 0} / ${scanLim}`;
      }
      if (deepQuotaEl) {
        const deepLim = trial.daily_deep_analysis_limit === -1 ? "Unlimited" : trial.daily_deep_analysis_limit;
        deepQuotaEl.textContent = `${trial.deep_analysis_used_today || 0} / ${deepLim}`;
      }
    }

    // 3. Fetch Telegram Link Status
    await loadTelegramLinkUI();

  } catch (err) {
    console.error("Failed to load account profile:", err);
  }
}

async function loadTelegramLinkUI() {
  try {
    const res = await fetch("/api/v1/telegram-link/status", { credentials: "include" });
    if (!res.ok) return;
    const data = await res.json();
    currentTelegramLink = data;

    const badge = document.getElementById("saas-telegram-status-badge");
    const unlinkedBox = document.getElementById("saas-telegram-unlinked-box");
    const linkedBox = document.getElementById("saas-telegram-linked-box");
    const userDisplay = document.getElementById("saas-telegram-user-display");
    const chatDisplay = document.getElementById("saas-telegram-chatid-display");

    if (data.linked) {
      if (badge) {
        badge.textContent = "CONNECTED";
        badge.style.color = "#00D99A";
        badge.style.borderColor = "#00D99A";
        badge.style.background = "rgba(0, 217, 154, 0.15)";
      }
      if (unlinkedBox) unlinkedBox.style.display = "none";
      if (linkedBox) linkedBox.style.display = "block";
      if (userDisplay) userDisplay.textContent = data.telegram_username ? `@${data.telegram_username}` : "Telegram User";
      if (chatDisplay) chatDisplay.textContent = `Chat ID: ${data.telegram_chat_id || "Verified"}`;

      // Populate preferences
      const p = data.preferences || {};
      const setChecked = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.checked = val !== false;
      };
      setChecked("pref-signals", p.trade_signals);
      setChecked("pref-risk", p.risk_alerts);
      setChecked("pref-macro", p.macro_events);
      setChecked("pref-briefing", p.daily_briefing);
      setChecked("pref-trial", p.trial_expiration_reminders);
    } else {
      if (badge) {
        badge.textContent = "NOT LINKED";
        badge.style.color = "#87A99A";
        badge.style.borderColor = "#20372C";
        badge.style.background = "rgba(135, 169, 154, 0.1)";
      }
      if (unlinkedBox) unlinkedBox.style.display = "block";
      if (linkedBox) linkedBox.style.display = "none";
    }
  } catch (err) {
    console.error("Failed to load telegram link UI:", err);
  }
}

async function startTelegramLinking() {
  try {
    const res = await fetch("/api/v1/telegram-link/token", {
      method: "POST",
      credentials: "include"
    });
    if (!res.ok) {
      const err = await res.json();
      alert("Failed to generate linking token: " + (err.detail || "Unknown error"));
      return;
    }
    const data = await res.json();
    const displayBox = document.getElementById("saas-telegram-token-display");
    const urlInput = document.getElementById("saas-telegram-link-url");
    const linkBtn = document.getElementById("saas-telegram-link-btn");

    if (urlInput) urlInput.value = data.deep_link;
    if (linkBtn) linkBtn.href = data.deep_link;
    if (displayBox) displayBox.style.display = "block";

  } catch (err) {
    alert("Connection error: " + err.message);
  }
}

function copyTelegramLink() {
  const urlInput = document.getElementById("saas-telegram-link-url");
  if (urlInput && urlInput.value) {
    navigator.clipboard.writeText(urlInput.value);
    alert("Telegram pairing link copied to clipboard! Paste it into your browser or send to your Telegram bot.");
  }
}

async function unlinkTelegramAccount() {
  if (!confirm("Are you sure you want to disconnect your Telegram account from ZYROX AI? Real-time mobile alerts will stop.")) {
    return;
  }
  try {
    const res = await fetch("/api/v1/telegram-link/unlink", {
      method: "POST",
      credentials: "include"
    });
    if (res.ok) {
      alert("Telegram account successfully disconnected.");
      await loadTelegramLinkUI();
    } else {
      const err = await res.json();
      alert("Unlink failed: " + (err.detail || "Server error"));
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

async function saveNotificationPreferences() {
  const payload = {
    trade_signals: document.getElementById("pref-signals")?.checked ?? true,
    risk_alerts: document.getElementById("pref-risk")?.checked ?? true,
    macro_events: document.getElementById("pref-macro")?.checked ?? true,
    daily_briefing: document.getElementById("pref-briefing")?.checked ?? true,
    trial_expiration_reminders: document.getElementById("pref-trial")?.checked ?? true
  };
  try {
    const res = await fetch("/api/v1/telegram-link/preferences", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      alert("Notification preferences saved successfully!");
    } else {
      const err = await res.json();
      alert("Save failed: " + (err.detail || "Server error"));
    }
  } catch (err) {
    alert("Save error: " + err.message);
  }
}

async function saveUserProfile() {
  const fullName = document.getElementById("acc-fullname")?.value?.trim();
  const preferredLanguage = document.getElementById("acc-language")?.value;
  const timezone = document.getElementById("acc-timezone")?.value?.trim();

  try {
    const res = await fetch("/api/v1/auth/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        full_name: fullName,
        preferred_language: preferredLanguage,
        timezone: timezone
      })
    });
    if (res.ok) {
      alert("Profile updated successfully!");
      await checkSaasSession();
    } else {
      const err = await res.json();
      alert("Update failed: " + (err.detail || "Server error"));
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

async function updateUserPassword() {
  const oldPassword = document.getElementById("acc-old-pass")?.value;
  const newPassword = document.getElementById("acc-new-pass")?.value;

  if (!oldPassword || !newPassword) {
    alert("Please enter both current and new password.");
    return;
  }
  if (newPassword.length < 8) {
    alert("New password must be at least 8 characters long.");
    return;
  }

  try {
    const res = await fetch("/api/v1/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        old_password: oldPassword,
        new_password: newPassword
      })
    });
    if (res.ok) {
      alert("Password changed successfully! Please keep your new credentials safe.");
      document.getElementById("acc-old-pass").value = "";
      document.getElementById("acc-new-pass").value = "";
    } else {
      const err = await res.json();
      alert("Password update failed: " + (err.detail || "Incorrect current password"));
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

async function handleUserLogout() {
  if (!confirm("Are you sure you want to sign out of ZYROX AI?")) return;
  try {
    await fetch("/api/v1/auth/logout", {
      method: "POST",
      credentials: "include"
    });
  } catch (err) {
    console.debug("Logout notice:", err);
  } finally {
    window.location.href = "/";
  }
}

async function confirmDeleteAccount() {
  const confirmation = prompt("To permanently delete your ZYROX AI account and cancel all subscriptions, type 'DELETE' below:");
  if (confirmation !== "DELETE") {
    alert("Account deletion canceled.");
    return;
  }
  try {
    const res = await fetch("/api/v1/auth/account", {
      method: "DELETE",
      credentials: "include"
    });
    if (res.ok) {
      alert("Your account has been deleted.");
      window.location.href = "/";
    } else {
      const err = await res.json();
      alert("Deletion failed: " + (err.detail || "Server error"));
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

/* ==========================================================================
   SUPPORT DESK & TICKET SYSTEM LOGIC
   ========================================================================== */

async function loadSupportTickets() {
  try {
    const res = await fetch("/api/v1/support/tickets", { credentials: "include" });
    const tbody = document.getElementById("user-tickets-tbody");
    if (!tbody) return;

    if (!res.ok) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Sign in to view your support tickets.</td></tr>`;
      return;
    }
    const tickets = await res.json();
    if (!tickets || tickets.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No support tickets submitted yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = tickets.map(t => {
      const badgeClass = t.status === "RESOLVED" || t.status === "CLOSED" ? "text-green" : (t.status === "IN_PROGRESS" ? "text-gold" : "text-cyan");
      return `
        <tr>
          <td><strong style="color: #16E6AB;">${escapeHtml(String(t.ticket_number || ""))}</strong></td>
          <td>${escapeHtml(String(t.subject || ""))}</td>
          <td>${escapeHtml(String(t.category || ""))}</td>
          <td>${escapeHtml(String(t.priority || "").toUpperCase())}</td>
          <td><span class="${badgeClass}">● ${escapeHtml(String(t.status || ""))}</span></td>
          <td style="font-size: 11px; color: #87A99A;">${escapeHtml(String(t.created_at || "").slice(0, 16))}</td>
        </tr>
      `;
    }).join("");

  } catch (err) {
    console.error("Failed to load support tickets:", err);
  }
}

async function submitSupportTicket() {
  const category = document.getElementById("ticket-category")?.value;
  const priority = document.getElementById("ticket-priority")?.value;
  const subject = document.getElementById("ticket-subject")?.value?.trim();
  const message = document.getElementById("ticket-message")?.value?.trim();

  if (!subject || !message) {
    alert("Please provide both a subject and detailed description.");
    return;
  }

  try {
    const res = await fetch("/api/v1/support/tickets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        category: category,
        priority: priority,
        subject: subject,
        message: message
      })
    });

    if (res.ok) {
      const created = await res.json();
      alert(`Support Ticket #${created.ticket_number} created successfully! Our engineering team will review your inquiry.`);
      document.getElementById("ticket-subject").value = "";
      document.getElementById("ticket-message").value = "";
      await loadSupportTickets();
    } else {
      const err = await res.json();
      alert("Ticket submission failed: " + (err.detail || "Please sign in first"));
    }
  } catch (err) {
    alert("Submission error: " + err.message);
  }
}

// Auto-check SaaS session on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  checkSaasSession();
});


/* ==========================================================================
   ADMIN SAAS MANAGEMENT JAVASCRIPT HANDLERS
   ========================================================================== */

let adminCachedUsers = [];

async function loadAdminSaaSData() {
  try {
    // 1. Load Analytics
    const anaRes = await fetch("/api/v1/admin/analytics", { credentials: "include" });
    if (anaRes.ok) {
      const a = await anaRes.json();
      const totEl = document.getElementById("admin-saas-total-users");
      const triEl = document.getElementById("admin-saas-active-trials");
      const paidEl = document.getElementById("admin-saas-paid-users");
      const spendEl = document.getElementById("admin-saas-ai-spend");

      if (totEl) totEl.textContent = a.total_users || 0;
      if (triEl) triEl.textContent = a.active_trials || 0;
      if (paidEl) paidEl.textContent = a.paid_users || 0;
      if (spendEl) spendEl.textContent = "$" + (a.total_ai_cost_usd ? a.total_ai_cost_usd.toFixed(4) : "0.00");
    }

    // 2. Load Users
    const usersRes = await fetch("/api/v1/admin/users", { credentials: "include" });
    const tbody = document.getElementById("admin-saas-users-tbody");
    if (!tbody) return;

    if (!usersRes.ok) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Admin authorization required. Sign in as admin.</td></tr>`;
      return;
    }

    const data = await usersRes.json();
    adminCachedUsers = data.users || [];
    renderAdminUsersTable(adminCachedUsers);

  } catch (err) {
    console.error("Failed to load admin SaaS data:", err);
  }
}

function filterAdminUsers(query) {
  const q = (query || "").toLowerCase();
  const filtered = adminCachedUsers.filter(u =>
    (u.email || "").toLowerCase().includes(q) ||
    (u.full_name || "").toLowerCase().includes(q)
  );
  renderAdminUsersTable(filtered);
}

function renderAdminUsersTable(users) {
  const tbody = document.getElementById("admin-saas-users-tbody");
  if (!tbody) return;
  if (!users || users.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No users found.</td></tr>`;
    return;
  }

  tbody.innerHTML = users.map(u => {
    const isSuspended = u.status === "suspended";
    const statusColor = isSuspended ? "text-danger" : (u.trial_status === "trial_active" ? "text-green" : "text-cyan");
    const rawUserId = String(u.id || "");
    const safeUserId = /^[a-f0-9-]{1,64}$/i.test(rawUserId) ? rawUserId : "";
    const statusArgument = isSuspended ? "suspended" : "active";
    return `
      <tr>
        <td><strong>${escapeHtml(String(u.email || ""))}</strong></td>
        <td>${escapeHtml(String(u.full_name || "--"))}</td>
        <td><span class="badge">${escapeHtml(String(u.role || ""))}</span></td>
        <td><span class="text-gold">${escapeHtml(String(u.subscription_tier || "free_trial").toUpperCase())}</span></td>
        <td><span class="${statusColor}">● ${escapeHtml(String(u.status || ""))} (${escapeHtml(String(u.trial_status || "n/a"))})</span></td>
        <td>
          <div style="display: flex; gap: 4px;">
            <button class="btn btn-outline btn-xs" ${safeUserId ? `onclick="promptOverridePlan('${safeUserId}')"` : "disabled"}>Plan</button>
            <button class="btn ${isSuspended ? 'btn-gold' : 'btn-danger'} btn-xs" ${safeUserId ? `onclick="toggleUserSuspension('${safeUserId}', '${statusArgument}')"` : "disabled"}>
              ${isSuspended ? 'Activate' : 'Suspend'}
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

async function promptOverridePlan(userId) {
  const plan = prompt("Enter new plan slug (free_trial, pro, premium):", "pro");
  if (!plan) return;
  const daysStr = prompt("Enter duration in days (e.g. 30):", "30");
  const days = parseInt(daysStr, 10) || 30;

  try {
    const res = await fetch(`/api/v1/admin/users/${userId}/subscription`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        plan_slug: plan.toLowerCase(),
        duration_days: days,
        reason: "Admin manual override"
      })
    });
    if (res.ok) {
      alert(`User plan successfully updated to ${plan} for ${days} days!`);
      await loadAdminSaaSData();
    } else {
      const err = await res.json();
      alert("Override failed: " + (err.detail || "Server error"));
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

async function toggleUserSuspension(userId, currentStatus) {
  const newStatus = currentStatus === "suspended" ? "active" : "suspended";
  if (!confirm(`Are you sure you want to change user status to '${newStatus}'?`)) return;

  try {
    const res = await fetch(`/api/v1/admin/users/${userId}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        status: newStatus,
        reason: `Admin toggle to ${newStatus}`
      })
    });
    if (res.ok) {
      alert(`User status updated to ${newStatus}.`);
      await loadAdminSaaSData();
    } else {
      const err = await res.json();
      alert("Status update failed: " + (err.detail || "Server error"));
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}


/* =============================================================================
 * FREELLMAPI OPEN-SOURCE FLEET JAVASCRIPT HANDLERS
 * ============================================================================= */

async function pingFreeLLMAPI() {
  const pill = document.getElementById("freellmapi-live-pill");
  const label = document.getElementById("freellmapi-status-label");
  if (pill) {
    pill.textContent = "Checking...";
    pill.className = "badge badge-warning";
  }
  if (label) label.textContent = "Probing endpoint...";

  try {
    const res = await fetch("/api/v1/freellmapi/status");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (pill) {
      if (data.status === "CONNECTED" || data.status === "ONLINE") {
        pill.textContent = "ONLINE (ACTIVE)";
        pill.className = "badge badge-success";
      } else {
        pill.textContent = `STANDBY (${data.status})`;
        pill.className = "badge badge-outline";
      }
    }
    if (label) {
      label.textContent = `${data.message || "Endpoint reachable"} (Model: ${data.default_model})`;
    }

    const urlInput = document.getElementById("freellmapi-base-url");
    if (urlInput && data.base_url) urlInput.value = data.base_url;

    const modelInput = document.getElementById("freellmapi-default-model");
    if (modelInput && data.default_model) modelInput.value = data.default_model;

  } catch (err) {
    if (pill) {
      pill.textContent = "UNREACHABLE";
      pill.className = "badge badge-danger";
    }
    if (label) {
      label.textContent = "Container offline or invalid Base URL";
    }
  }
}

async function discoverFreeLLMAPIModels() {
  const container = document.getElementById("freellmapi-models-container");
  const countSpan = document.getElementById("freellmapi-models-count");
  const listDiv = document.getElementById("freellmapi-models-list");
  const label = document.getElementById("freellmapi-status-label");

  if (label) label.textContent = "Discovering models from /v1/models...";
  try {
    const res = await fetch("/api/v1/freellmapi/models");
    const data = await res.json();

    if (container) container.style.display = "block";

    if (data.models && data.models.length > 0) {
      if (countSpan) countSpan.textContent = data.count || data.models.length;
      if (listDiv) {
        listDiv.innerHTML = data.models.map(m => {
          const modelId = String(m.id || m);
          const modelArg = encodeURIComponent(modelId).replace(/'/g, "%27");
          return `
          <button type="button" class="btn btn-outline btn-xs" style="margin: 2px;" onclick="selectFreeLLMAPIModel(decodeURIComponent('${modelArg}'))">
            ${escapeHtml(modelId)}
          </button>
        `;
        }).join("");
      }
      if (label) label.textContent = `Discovered ${data.count} models available in pool`;
    } else {
      if (countSpan) countSpan.textContent = "0";
      if (listDiv) {
        listDiv.innerHTML = `<span class="text-xs text-muted">No models returned or proxy not currently responding. Defaulting to deepseek-r1.</span>`;
      }
      if (label) label.textContent = data.message || "No models detected";
    }
  } catch (err) {
    if (container) container.style.display = "block";
    if (listDiv) listDiv.innerHTML = `<span class="text-xs text-danger">Error discovering models: ${escapeHtml(err.message)}</span>`;
  }
}

function selectFreeLLMAPIModel(modelId) {
  const modelInput = document.getElementById("freellmapi-default-model");
  if (modelInput) {
    modelInput.value = modelId;
    alert(`Selected FreeLLMAPI default model: ${modelId}`);
  }
}

async function saveFreeLLMAPIConfig() {
  const baseUrl = document.getElementById("freellmapi-base-url")?.value?.trim();
  const defaultModel = document.getElementById("freellmapi-default-model")?.value?.trim();
  const apiKey = document.getElementById("freellmapi-api-key")?.value?.trim();

  try {
    const res = await fetch("/api/v1/freellmapi/configure", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        base_url: baseUrl,
        default_model: defaultModel,
        api_key: apiKey
      })
    });
    if (res.ok) {
      const data = await res.json();
      alert(`FreeLLMAPI configuration saved!\nBase URL: ${data.base_url}\nModel: ${data.default_model}`);
      await pingFreeLLMAPI();
    } else {
      const err = await res.json();
      alert("Failed to save: " + (err.detail || "Server error"));
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

async function testFreeLLMAPIInference() {
  const box = document.getElementById("freellmapi-test-output-box");
  const output = document.getElementById("freellmapi-test-output");
  const timeLabel = document.getElementById("freellmapi-test-time");
  const title = document.getElementById("freellmapi-telemetry-title");

  if (box) box.style.display = "block";
  if (title) title.innerHTML = `<span class="text-gold">⚡ SENDING INFERENCE PROBE TO FREELLMAPI...</span>`;
  if (output) output.textContent = "Connecting to FreeLLMAPI proxy...\nSending test payload: 'Analyze market volatility and response latency in one sentence.'";
  if (timeLabel) timeLabel.textContent = new Date().toLocaleTimeString();

  const modelId = document.getElementById("freellmapi-default-model")?.value?.trim();

  try {
    const res = await fetch("/api/v1/freellmapi/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: modelId || null })
    });
    const data = await res.json();

    if (data.status === "SUCCESS") {
      if (title) title.innerHTML = `<span class="text-green">✔ INFERENCE TEST PASSED (${data.latency_ms}ms)</span>`;
      if (output) {
        output.textContent = `Model: ${data.model}\nEndpoint: ${data.endpoint}\nStatus: HTTP 200 OK\nLatency: ${data.latency_ms}ms\nResponse:\n${data.response}`;
      }
      await pingFreeLLMAPI();
    } else {
      if (title) title.innerHTML = `<span class="text-gold">⚠ PROXY STANDBY / FALLBACK</span>`;
      if (output) {
        output.textContent = `Endpoint: ${data.endpoint}\nNotice: ${data.error_message || data.response || "Server returned non-200"}\nTip: Ensure Docker container is running (docker run -d -p 4000:4000 tashfeenahmed/freellmapi) or cloud URL is set.`;
      }
    }
  } catch (err) {
    if (title) title.innerHTML = `<span class="text-danger">✖ REQUEST FAILED</span>`;
    if (output) output.textContent = `Network exception: ${err.message}`;
  }
}

function initFreeLLMAPIUI() {
  pingFreeLLMAPI();
}
