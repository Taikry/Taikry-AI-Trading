"""
Economic Calendar & Real-Time Macro News Provider for TAIKRY AI MARKET INTELLIGENCE PRO
Fetches verified high-impact economic calendar events (FOMC, PPI, CPI, NFP, GDP, Central Bank Rates)
and breaking financial news with real-time countdowns, blackout alerts, and Khmer translations.
"""
import datetime
import logging
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional

import requests

logger = logging.getLogger("taikry.data.economic_calendar")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, application/xml, text/xml, */*"
}

# Khmer Translation & Macro Mapping Matrix for High-Impact Events
MACRO_KHMER_CATALOG = {
    "FEDERAL FUNDS": {
        "title_kh": "ការសម្រេចអត្រាការប្រាក់ Fed (Federal Funds Rate & FOMC)",
        "gold_impact_en": "Fed policy rate decision directly dictates USD yields and Gold valuation.",
        "gold_impact_kh": "គោលនយោបាយអត្រាការប្រាក់ Fed កំណត់ទិន្នផលដុល្លារ និងទិសដៅឡើងចុះនៃតម្លៃមាស។",
        "forex_impact_en": "Extreme volatility expected across all USD currency pairs.",
        "forex_impact_kh": "បង្កការប្រែប្រួលតម្លៃខ្លាំងលើគូរូបិយប័ណ្ណដុល្លារទាំងអស់។"
    },
    "FOMC": {
        "title_kh": "ការសម្រេចអត្រាការប្រាក់ និងសេចក្តីប្រកាសរបស់ធនាគារកណ្តាលអាមេរិក (FOMC)",
        "gold_impact_en": "Fed policy trajectory directly dictates USD yield curve and Gold safe-haven valuation.",
        "gold_impact_kh": "គោលនយោបាយអត្រាការប្រាក់ Fed កំណត់ទិន្នផលដុល្លារ និងទិសដៅឡើងចុះនៃតម្លៃមាស។",
        "forex_impact_en": "Extreme volatility expected across all USD currency pairs.",
        "forex_impact_kh": "បង្កការប្រែប្រួលតម្លៃខ្លាំងលើគូរូបិយប័ណ្ណដុល្លារទាំងអស់។"
    },
    "PPI": {
        "title_kh": "សន្ទស្សន៍ថ្លៃផលិតករ (PPI - Producer Price Index)",
        "gold_impact_en": "Wholesale inflation gauge precedes CPI; higher PPI signals persistent rate pressures, headwind for Gold.",
        "gold_impact_kh": "រង្វាស់អតិផរណាថ្លៃដើមផលិតកម្ម បង្ហាញពីសម្ពាធអត្រាការប្រាក់ និងជះឥទ្ធិពលលើតម្លៃមាស។",
        "forex_impact_en": "Drives immediate USD yield reactions and cross-currency rebalancing.",
        "forex_impact_kh": "ជំរុញឱ្យប្រាក់ដុល្លារប្រែប្រួលភ្លាមៗតាមទិន្នផលមូលបត្របំណុល។"
    },
    "CPI": {
        "title_kh": "សន្ទស្សន៍ថ្លៃទំនិញប្រើប្រាស់ (CPI - អតិផរណាសំខាន់បំផុត)",
        "gold_impact_en": "Primary benchmark for Fed rate expectations. Higher CPI strengthens USD, pressuring Gold.",
        "gold_impact_kh": "រង្វាស់អតិផរណាប្រើប្រាស់ស្នូល។ CPI ខ្ពស់ជំរុញដុល្លារ និងទាញទម្លាក់តម្លៃមាស។",
        "forex_impact_en": "Generates wide market spreads and explosive moves across EURUSD, GBPUSD, USDJPY.",
        "forex_impact_kh": "បង្កើតការប្រែប្រួលយ៉ាងគំហុកលើ EURUSD, GBPUSD, និង USDJPY។"
    },
    "NFP": {
        "title_kh": "របាយការណ៍ការងារមិនមែនកសិកម្ម (NFP - Non-Farm Payrolls)",
        "gold_impact_en": "US labor market health dictates economic strength. High NFP boosts USD, lowering Gold demand.",
        "gold_impact_kh": "របាយការណ៍ទីផ្សារការងារអាមេរិក។ NFP ខ្ពស់ជួយឱ្យដុល្លារឡើងថ្លៃ និងដាក់សម្ពាធលើមាស។",
        "forex_impact_en": "Highest single-day volatility catalyst in global Forex trading.",
        "forex_impact_kh": "ព្រឹត្តិការណ៍បង្កការកម្រើកតម្លៃខ្លាំងបំផុតក្នុងទីផ្សារប្តូរប្រាក់ Forex។"
    },
    "GDP": {
        "title_kh": "អត្រាកំណើនសេដ្ឋកិច្ចជាតិ (GDP - Gross Domestic Product)",
        "gold_impact_en": "Broad economic expansion indicator; strong GDP supports USD and dampens bullion safe-haven appeal.",
        "gold_impact_kh": "រង្វាស់កំណើនសេដ្ឋកិច្ចទូទៅ។ GDP រឹងមាំជួយដុល្លារ និងបន្ថយកម្លាំងទិញមាស។",
        "forex_impact_en": "Shifts sovereign yield curves and institutional currency positioning.",
        "forex_impact_kh": "ផ្លាស់ប្តូរទិន្នផលសញ្ញាប័ណ្ណរដ្ឋ និងលំហូរទុនស្ថាប័ន។"
    },
    "INTEREST RATE": {
        "title_kh": "ការសម្រេចអត្រាការប្រាក់របស់ធនាគារកណ្តាល (Central Bank Rate)",
        "gold_impact_en": "Direct monetary policy adjustment dictating opportunity cost of holding non-yielding Gold.",
        "gold_impact_kh": "ការកែសម្រួលអត្រាការប្រាក់ផ្ទាល់ ប៉ះពាល់ដល់ការកាន់កាប់ទ្រព្យសកម្មមាស។",
        "forex_impact_en": "Immediate re-pricing of interest rate differentials.",
        "forex_impact_kh": "ការគណនាតម្លៃគម្លាតអត្រាការប្រាក់រូបិយប័ណ្ណជាថ្មីភ្លាមៗ។"
    },
    "RETAIL SALES": {
        "title_kh": "ទិន្នន័យការលក់រាយរបស់សហរដ្ឋអាមេរិក (Retail Sales)",
        "gold_impact_en": "Consumer spending health drives Fed inflation calculations and bullion demand.",
        "gold_impact_kh": "កម្លាំងចំណាយរបស់អ្នកប្រើប្រាស់ឆ្លុះបញ្ចាំងពីអតិផរណា និងតម្រូវការមាស។",
        "forex_impact_en": "Moderate-to-high volatility impact on USD momentum.",
        "forex_impact_kh": "ជះឥទ្ធិពលមធ្យមទៅខ្លាំងលើសន្ទុះប្រាក់ដុល្លារអាមេរិក។"
    }
}

class EconomicCalendarProvider:
    """
    Fetches real-time economic calendar, high-impact event countdowns,
    breaking macro news feeds, and US Dollar Index (DXY) momentum.
    """
    def __init__(self):
        self.dxy_ticker = "DX-Y.NYB"
        self._cached_events: List[Dict[str, Any]] = []
        self._last_event_fetch_ts: float = 0.0
        self._calendar_available = False
        self._event_cache_ttl_seconds: int = 1800  # 30 minutes cache to avoid rate limits
        self._cached_news: List[Dict[str, Any]] = []
        self._last_news_fetch_ts: float = 0.0
        self._news_cache_ttl_seconds: int = 120    # 2 minutes cache for live headlines

    def _match_khmer_meta(self, title: str) -> Dict[str, str]:
        """Matches event title against the macro catalog for natural Khmer translation and impact context."""
        t_upper = title.upper()
        for key, meta in MACRO_KHMER_CATALOG.items():
            if key in t_upper:
                return meta
        return {
            "title_kh": f"ព្រឹត្តិការណ៍សេដ្ឋកិច្ចសំខាន់៖ {title}",
            "gold_impact_en": "High impact catalyst creates volatility in Gold spreads and price action.",
            "gold_impact_kh": "ព្រឹត្តិការណ៍បង្កើនការប្រែប្រួលតម្លៃ និងគម្លាត Spread លើទីផ្សារមាស។",
            "forex_impact_en": "Generates rapid institutional rebalancing across currency pairs.",
            "forex_impact_kh": "បង្កការរៀបចំលំហូរទុនឡើងវិញលើគូរូបិយប័ណ្ណសំខាន់ៗ។"
        }

    def _extract_event_category(self, title: str) -> str:
        """Extracts concise macro acronym or keyword for UI badges."""
        t = title.upper()
        if "FOMC" in t or "FEDERAL RESERVE" in t or "FEDERAL FUNDS RATE" in t or "FED RATE" in t:
            return "FOMC"
        if "CPI" in t or "CONSUMER PRICE" in t or "INFLATION" in t:
            return "CPI"
        if "PPI" in t or "PRODUCER PRICE" in t:
            return "PPI"
        if "NON-FARM" in t or "NONFARM" in t or "NFP" in t:
            return "NFP"
        if "GDP" in t or "GROSS DOMESTIC" in t:
            return "GDP"
        if "PCE" in t:
            return "Core PCE"
        if "RETAIL SALES" in t:
            return "Retail Sales"
        if "POWELL" in t:
            return "Fed Powell"
        if "RATE" in t or "INTEREST" in t:
            return "Rate Decision"
        if "UNEMPLOYMENT" in t or "JOBLESS" in t:
            return "Jobless Claims"
        clean = title.split(" - ")[0].split(":")[0].strip()
        return clean[:14]

    def get_upcoming_high_impact_events(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieves upcoming high-impact economic events with live countdown and blackout status.
        Uses a public calendar feed. Missing feed data remains unavailable.
        """
        now_ts = time.time()
        now_dt = datetime.datetime.now(datetime.timezone.utc)

        # Return cached if still within TTL
        if not force_refresh and (now_ts - self._last_event_fetch_ts < self._event_cache_ttl_seconds):
            # Recalculate countdowns dynamically
            return self._enrich_countdowns(self._cached_events, now_dt)

        fetched_events: List[Dict[str, Any]] = []
        self._calendar_available = False

        # 1. Attempt Forex Factory / FairEconomy public feed
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        try:
            r = requests.get(url, headers=HEADERS, timeout=4)
            if r.status_code == 200:
                raw = r.json()
                self._calendar_available = isinstance(raw, list)
                for item in raw:
                    impact = str(item.get("impact", "")).lower()
                    country = str(item.get("country", "")).upper()
                    if impact == "high" and country in ["USD", "EUR", "GBP", "JPY"]:
                        title = item.get("title", "")
                        meta = self._match_khmer_meta(title)
                        date_str = item.get("date", "")
                        fetched_events.append({
                            "id": f"ff_{abs(hash(title + date_str)) % 100000}",
                            "title": title,
                            "title_kh": meta["title_kh"],
                            "country": country,
                            "impact": "HIGH",
                            "scheduled_utc": date_str,
                            "scheduled_display": date_str,
                            "forecast": item.get("forecast") or "N/A",
                            "previous": item.get("previous") or "N/A",
                            "actual": item.get("actual") or "PENDING",
                            "volatility_risk": "EXTREME",
                            "gold_impact_en": meta["gold_impact_en"],
                            "gold_impact_kh": meta["gold_impact_kh"],
                            "forex_impact_en": meta["forex_impact_en"],
                            "forex_impact_kh": meta["forex_impact_kh"],
                            "category": self._extract_event_category(title)
                        })
        except Exception as e:
            logger.debug(f"FairEconomy feed skipped: {e}")

        # Do not fabricate a schedule when the public calendar is unavailable.
        if not fetched_events:
            logger.warning("Economic calendar feed returned no events; calendar status is unavailable.")

        self._cached_events = fetched_events
        self._last_event_fetch_ts = now_ts

        return self._enrich_countdowns(self._cached_events, now_dt)

    def _enrich_countdowns(self, events: List[Dict[str, Any]], now_dt: datetime.datetime) -> List[Dict[str, Any]]:
        """Calculates real-time countdown, minutes remaining, and news blackout status."""
        enriched = []
        for ev in events:
            ev_copy = dict(ev)
            sched_str = ev.get("scheduled_utc", "")
            try:
                # Parse ISO or standard string
                cleaned_str = sched_str.replace("Z", "+00:00")
                if "T" in cleaned_str:
                    sched_dt = datetime.datetime.fromisoformat(cleaned_str)
                else:
                    sched_dt = datetime.datetime.strptime(cleaned_str[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
            except Exception:
                logger.warning("Skipping economic calendar event with invalid timestamp: %r", sched_str)
                continue

            diff_sec = int((sched_dt - now_dt).total_seconds())
            diff_min = int(diff_sec / 60)
            diff_hrs = round(diff_min / 60, 1)

            ev_copy["countdown_seconds"] = diff_sec
            ev_copy["minutes_remaining"] = diff_min

            if -1800 <= diff_sec <= 0:
                ev_copy["time_until"] = "🔴 ACTIVE NOW (Releasing)"
                ev_copy["status_badge"] = "RELEASE_IN_PROGRESS"
                ev_copy["blackout_active"] = True
            elif 0 < diff_sec <= 1800:
                ev_copy["time_until"] = f"⚡ IN {diff_min} MINS"
                ev_copy["status_badge"] = "IMMINENT_BLACKOUT"
                ev_copy["blackout_active"] = True
            elif 1800 < diff_sec <= 7200:
                ev_copy["time_until"] = f"⏳ In {diff_min} mins"
                ev_copy["status_badge"] = "UPCOMING_SOON"
                ev_copy["blackout_active"] = False
            elif diff_sec > 7200:
                ev_copy["time_until"] = f"📅 In {diff_hrs} hrs"
                ev_copy["status_badge"] = "SCHEDULED"
                ev_copy["blackout_active"] = False
            else:
                passed_hrs = abs(round(diff_min / 60, 1))
                ev_copy["time_until"] = f"✅ Completed {passed_hrs}h ago"
                ev_copy["status_badge"] = "COMPLETED"
                ev_copy["blackout_active"] = False

            enriched.append(ev_copy)

        # Sort by urgency (imminent first)
        enriched.sort(key=lambda x: (x.get("countdown_seconds", 999999) < -1800, abs(x.get("countdown_seconds", 999999))))
        return enriched

    def check_news_blackout(self, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """
        Audits whether a High-Impact news release (FOMC, PPI, CPI, NFP) is inside
        the mandatory 30-minute pre-news blackout window.
        """
        events = self.get_upcoming_high_impact_events()
        for ev in events:
            if ev.get("blackout_active"):
                title = ev.get("title", "High-Impact Catalyst")
                title_kh = ev.get("title_kh", "")
                mins = ev.get("minutes_remaining", 0)
                return {
                    "is_blackout": True,
                    "status": "BLACKOUT",
                    "event_title": title,
                    "event_title_kh": title_kh,
                    "minutes_remaining": mins,
                    "advisory_en": f"PRE-NEWS LOCKOUT: {title} scheduled within {mins} mins. Extreme spread widening and slippage risk active.",
                    "advisory_kh": f"បំរាមជួញដូរពេលចេញព័ត៌មាន (News Lockout)៖ {title_kh} នឹងចេញផ្សាយក្នុងរយៈពេល {mins} នាទីទៀត។ ហាមបើកការជួញដូរថ្មីដើម្បីចៀសវាង Slippage និង Spread ឡើងខ្ពស់។"
                }

        return {
            "is_blackout": False,
            "status": "UNAVAILABLE" if not self._calendar_available else "CLEAR",
            "event_title": None,
            "event_title_kh": None,
            "minutes_remaining": None,
            "advisory_en": "Calendar feed is unavailable; upcoming event risk could not be verified.",
            "advisory_kh": "មិនអាចភ្ជាប់ប្រតិទិនព័ត៌មានបានទេ ដូច្នេះមិនអាចផ្ទៀងផ្ទាត់ហានិភ័យព្រឹត្តិការណ៍ខាងមុខបានឡើយ។"
        } if not self._calendar_available else {
            "is_blackout": False,
            "status": "CLEAR",
            "event_title": None,
            "event_title_kh": None,
            "minutes_remaining": None,
            "advisory_en": "No immediate high-impact blackout was found in the returned calendar events.",
            "advisory_kh": "ក្នុងព្រឹត្តិការណ៍ដែលប្រតិទិនបានផ្តល់ មិនឃើញមានព្រឹត្តិការណ៍ឥទ្ធិពលខ្ពស់ក្នុងពេលបច្ចុប្បន្នទេ។"
        }

    def get_next_xauusd_catalyst(self) -> Optional[Dict[str, Any]]:
        """
        Returns the single most urgent upcoming High-Impact macro release affecting Gold (XAUUSD).
        Prioritizes high-impact USD events (FOMC, CPI, PPI, NFP, PCE, etc.).
        Calculates exact countdown badge text in English and Khmer.
        """
        events = self.get_upcoming_high_impact_events()
        now_dt = datetime.datetime.now(datetime.timezone.utc)

        # Filter events affecting XAUUSD (USD high impact or gold catalysts)
        xau_events = []
        for ev in events:
            country = str(ev.get("country", "")).upper()
            impact = str(ev.get("impact", "")).upper()
            cat = str(ev.get("category", "")).upper()
            title = str(ev.get("title", "")).upper()

            is_gold_relevant = (
                (country == "USD" and impact == "HIGH") or
                any(k in cat or k in title for k in ["FOMC", "FED", "CPI", "PPI", "NFP", "PCE", "GDP", "GOLD", "RATE", "RETAIL"])
            )
            if is_gold_relevant:
                xau_events.append(ev)

        if not xau_events:
            return None

        # Filter events that are either active now or upcoming (not completed > 30m ago)
        active_or_upcoming = [
            e for e in xau_events
            if e.get("countdown_seconds", 0) > -1800
        ]
        if not active_or_upcoming:
            return None

        # Sort by closest time to now
        active_or_upcoming.sort(key=lambda x: (x.get("countdown_seconds", 999999) < 0, abs(x.get("countdown_seconds", 999999))))
        target = active_or_upcoming[0]

        diff_sec = target.get("countdown_seconds", 0)
        mins = target.get("minutes_remaining", 0)
        cat = target.get("category", "FOMC")
        is_blackout = target.get("blackout_active", False) or (0 <= diff_sec <= 1800)

        # Build clean countdown string
        if diff_sec < -1800:
            passed_hrs = abs(round(mins / 60, 1))
            badge_en = f"✅ {cat} Completed {passed_hrs}h ago"
            badge_kh = f"✅ {cat} បានបញ្ចប់ {passed_hrs}ម៉ោងមុន"
            time_display = f"{passed_hrs}h ago"
            time_display_kh = f"{passed_hrs}ម៉ោងមុន"
        elif -1800 <= diff_sec <= 0:
            badge_en = f"🔥 {cat} RELEASING NOW · Extreme Volatility"
            badge_kh = f"🔥 {cat} កំពុងចេញផ្សាយ · ប្រែប្រួលខ្លាំង"
            time_display = "NOW"
            time_display_kh = "ឥឡូវនេះ"
        elif 0 < diff_sec <= 1800:
            badge_en = f"⚡ {cat} in {mins}m · Blackout Active"
            badge_kh = f"⚡ {cat} ក្នុង {mins}នាទី · បំរាមជួញដូរ"
            time_display = f"{mins}m"
            time_display_kh = f"{mins}នាទី"
        elif 1800 < diff_sec < 86400:
            hrs = diff_sec // 3600
            rem_m = (diff_sec % 3600) // 60
            if hrs > 0 and rem_m > 0:
                time_display = f"{hrs}h {rem_m}m"
                time_display_kh = f"{hrs}ម៉ោង {rem_m}នាទី"
            elif hrs > 0:
                time_display = f"{hrs}h"
                time_display_kh = f"{hrs}ម៉ោង"
            else:
                time_display = f"{rem_m}m"
                time_display_kh = f"{rem_m}នាទី"
            badge_en = f"⚡ {cat} in {time_display} · High Impact"
            badge_kh = f"⚡ {cat} ក្នុង {time_display_kh} · ឥទ្ធិពលខ្លាំងលើមាស"
        else:
            days = diff_sec // 86400
            rem_hrs = (diff_sec % 86400) // 3600
            if rem_hrs > 0:
                time_display = f"{days}d {rem_hrs}h"
                time_display_kh = f"{days}ថ្ងៃ {rem_hrs}ម៉ោង"
            else:
                time_display = f"{days}d"
                time_display_kh = f"{days}ថ្ងៃ"
            badge_en = f"⚡ {cat} in {time_display} · High Impact"
            badge_kh = f"⚡ {cat} ក្នុង {time_display_kh} · ឥទ្ធិពលខ្លាំងលើមាស"

        return {
            "id": target.get("id"),
            "title": target.get("title"),
            "title_kh": target.get("title_kh"),
            "category": cat,
            "country": target.get("country", "USD"),
            "scheduled_utc": target.get("scheduled_utc"),
            "scheduled_display": target.get("scheduled_display"),
            "forecast": target.get("forecast"),
            "previous": target.get("previous"),
            "countdown_seconds": diff_sec,
            "minutes_remaining": mins,
            "time_display": time_display,
            "time_display_kh": time_display_kh,
            "badge_en": badge_en,
            "badge_kh": badge_kh,
            "is_blackout": is_blackout,
            "volatility_risk": target.get("volatility_risk", "EXTREME"),
            "gold_impact_en": target.get("gold_impact_en"),
            "gold_impact_kh": target.get("gold_impact_kh")
        }

    def get_live_macro_news(self, limit: int = 8) -> List[Dict[str, Any]]:
        """
        Fetches breaking financial and macroeconomic news headlines from verified live RSS feeds:
        - Investing.com Breaking News RSS
        - MarketWatch Top Stories RSS
        """
        now_ts = time.time()
        if now_ts - self._last_news_fetch_ts < self._news_cache_ttl_seconds:
            return self._cached_news[:limit]

        rss_feeds = [
            ("Investing.com", "https://www.investing.com/rss/news_25.rss"),
            ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories")
        ]

        news_items: List[Dict[str, Any]] = []

        for source_name, url in rss_feeds:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=4) as response:
                    raw_xml = response.read()
                    root = ET.fromstring(raw_xml)
                    items = root.findall("./channel/item")
                    for it in items[:6]:
                        title_el = it.find("title")
                        link_el = it.find("link")
                        pub_el = it.find("pubDate")
                        desc_el = it.find("description")

                        if title_el is not None and title_el.text:
                            title = title_el.text.strip()
                            pub_date = pub_el.text.strip() if pub_el is not None and pub_el.text else "Recent"
                            link = link_el.text.strip() if link_el is not None and link_el.text else "#"
                            desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

                            # Filter for macro, currencies, metals, and central banks
                            is_gold = any(w in title.lower() for w in ["gold", "xau", "bullion", "metal", "precious"])
                            is_fed = any(w in title.lower() for w in ["fed", "fomc", "powell", "rate", "inflation", "cpi", "ppi"])
                            is_fx = any(w in title.lower() for w in ["dollar", "dxy", "euro", "yen", "forex", "currency", "yield"])

                            relevance = "HIGH" if (is_gold or is_fed) else ("MEDIUM" if is_fx else "GENERAL")

                            news_items.append({
                                "title": title,
                                "source": source_name,
                                "published_at": pub_date,
                                "link": link,
                                "relevance": relevance,
                                "is_gold_related": is_gold,
                                "is_macro_related": is_fed,
                                "snippet": desc[:180] + "..." if len(desc) > 180 else desc
                            })
            except Exception as e:
                logger.debug(f"RSS fetch for {source_name} failed: {e}")

        self._cached_news = news_items
        self._last_news_fetch_ts = now_ts
        return news_items[:limit]

    def get_usd_strength_context(self) -> Dict[str, Any]:
        """
        Calculates US Dollar Index (DXY) momentum to gauge inverse correlation for Gold and Forex.
        """
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{self.dxy_ticker}?range=5d&interval=1d"
        try:
            r = requests.get(url, headers=HEADERS, timeout=5)
            if r.status_code == 200:
                data = r.json()["chart"]["result"][0]
                quotes = data["indicators"]["quote"][0]["close"]
                valid_quotes = [q for q in quotes if q is not None]
                if len(valid_quotes) >= 2:
                    curr_dxy = round(float(valid_quotes[-1]), 2)
                    prev_dxy = round(float(valid_quotes[-2]), 2)
                    dxy_change = round(curr_dxy - prev_dxy, 2)
                    bias = "BULLISH_USD" if dxy_change > 0 else ("BEARISH_USD" if dxy_change < 0 else "NEUTRAL_USD")
                    return {
                        "dxy_price": curr_dxy,
                        "dxy_change_pts": dxy_change,
                        "usd_bias": bias,
                        "status": "AVAILABLE",
                        "impact_on_gold": "BEARISH_PRESSURE" if bias == "BULLISH_USD" else "BULLISH_TAILWIND"
                    }
        except Exception:
            pass

        return {
            "dxy_price": None,
            "dxy_change_pts": None,
            "usd_bias": "UNAVAILABLE",
            "impact_on_gold": "UNAVAILABLE",
            "status": "UNAVAILABLE"
        }

economic_calendar_provider = EconomicCalendarProvider()
