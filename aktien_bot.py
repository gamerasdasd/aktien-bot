"""
Täglicher Aktien-Morgenbericht per Telegram.

Quellen: Finanz-News (RSS), Reddit, StockTwits-Trending
Analyse: Claude (Anthropic API)
Versand: Telegram-Bot

Installation:  pip install feedparser requests anthropic
Start:         python aktien_bot.py
"""

import os
import re
import requests
import feedparser
import anthropic

# ============ EINSTELLUNGEN (als Umgebungsvariablen setzen) ============
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]      # von @BotFather
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]  # deine Chat-ID
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")

HEADERS = {"User-Agent": "Mozilla/5.0 (aktien-bot)"}

NEWS_FEEDS = {
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "CNBC Markets": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
}

SOCIAL_FEEDS = {
    "Reddit r/wallstreetbets": "https://www.reddit.com/r/wallstreetbets/hot/.rss",
    "Reddit r/stocks": "https://www.reddit.com/r/stocks/hot/.rss",
    "Reddit r/Aktien": "https://www.reddit.com/r/Aktien/hot/.rss",
}


def clean(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").replace("\n", " ").strip()


def read_feed(name: str, url: str, limit: int = 12) -> list[str]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        feed = feedparser.parse(r.content)
        return [f"[{name}] {clean(e.get('title', ''))}" for e in feed.entries[:limit]]
    except Exception as e:
        print(f"Fehler bei {name}: {e}")
        return []


def stocktwits_trending() -> list[str]:
    try:
        r = requests.get(
            "https://api.stocktwits.com/api/2/trending/symbols.json",
            headers=HEADERS, timeout=15,
        )
        symbols = r.json().get("symbols", [])[:15]
        return [f"[StockTwits Trending] {s['symbol']} – {s.get('title', '')}" for s in symbols]
    except Exception as e:
        print(f"Fehler bei StockTwits: {e}")
        return []


def collect_data() -> str:
    lines = []
    for name, url in {**NEWS_FEEDS, **SOCIAL_FEEDS}.items():
        lines += read_feed(name, url)
    lines += stocktwits_trending()
    return "\n".join(lines)


def analyze(data: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = f"""Du bist ein Aktien-Analyst. Unten stehen die aktuellen Schlagzeilen aus
Finanznachrichten und Social Media (Reddit, StockTwits). Erstelle daraus einen kurzen
Morgenbericht auf Deutsch für einen Privatanleger, der über Trade Republic handelt.

Format:
1. Marktstimmung heute (2-3 Sätze)
2. KURZFRISTIG (Tage bis Wochen): 3 Aktien – Name, Ticker, Begründung (1-2 Sätze), Risiko
3. LANGFRISTIG (Jahre): 3 Aktien oder ETFs – Name, Ticker, Begründung (1-2 Sätze), Risiko
4. Vorsicht: Aktien, die gerade überhypt wirken (Meme-Hype, Pump-Verdacht)

Regeln:
- Nur Titel, die bei Trade Republic handelbar sind (große, bekannte Werte/ETFs).
- Stütze dich auf die gelieferten Daten, erfinde keine Kurse oder Zahlen.
- Max. 2500 Zeichen, kein Markdown, nur Text und Emojis.
- Am Ende ein Satz: Keine Anlageberatung, eigene Recherche nötig.

DATEN:
{data}"""
    msg = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def send_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for i in range(0, len(text), 4000):  # Telegram-Limit: 4096 Zeichen
        r = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text[i:i + 4000]},
            timeout=15,
        )
        r.raise_for_status()


def main():
    data = collect_data()
    if not data:
        send_telegram("⚠️ Heute konnten keine News geladen werden.")
        return
    report = analyze(data)
    send_telegram("📈 Aktien-Morgenbericht\n\n" + report)


if __name__ == "__main__":
    main()
