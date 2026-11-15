import os, json, re, requests
from playwright.sync_api import sync_playwright

TOKEN = os.environ["TELEGRAM_TOKEN"].strip()
CHAT = os.environ["TELEGRAM_CHAT_ID"].strip()
BASE = "https://deals.3rrood.com/store/amazon_resale?gcat={}&stock=in"
CATS = {"mobiles": "موبايلات", "laptops": "لابتوبات", "tablets": "تابلت", "tvs": "تلفزيونات"}
SEEN = "seen.json"


def send(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT, "text": text},
        timeout=30,
    )
    print("TELEGRAM:", r.status_code, r.text[:200])
    return r


def scrape(page, cat):
    page.goto(BASE.format(cat), wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    raw = page.evaluate(
        """() => [...document.querySelectorAll('a[href]')]
        .filter(a => a.innerText.includes('ج.م'))
        .map(a => ({href: a.href, text: a.innerText}))"""
    )
    items = {}
    for r in raw:
        lines = [l.strip() for l in r["text"].split("\n") if l.strip()]
        if not lines:
            continue
        title = max(lines, key=len)
        price = next((l for l in lines if re.fullmatch(r"[\d,\.]+", l)), "?")
        items[r["href"]] = {"title": title[:120], "price": price}
    print(cat, "found", len(items), "products")
    return items


def main():
    send("✅ تجربة: السكريبت اشتغل")
    seen = json.load(open(SEEN)) if os.path.exists(SEEN) else {}
    report = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale="ar-EG")
        for cat, name in CATS.items():
            try:
                items = scrape(page, cat)
            except Exception as e:
                print(cat, "ERROR", str(e)[:200])
                report.append(f"{name}: فشل ({str(e)[:60]})")
                continue
            if cat not in seen:
                seen[cat] = list(items.keys())
                report.append(f"{name}: اتسجل {len(items)} منتج")
                continue
            old = set(seen[cat])
            for href, it in items.items():
                if href not in old:
                    send(f"🆕 {name}\n{it['title']}\nالسعر: {it['price']} ج.م\n{href}")
                    seen[cat].append(href)
        browser.close()
    if report:
        send("تقرير أول تشغيل:\n" + "\n".join(report))
    json.dump(seen, open(SEEN, "w"), ensure_ascii=False)


main()
