import os, json, re, requests
from playwright.sync_api import sync_playwright

TOKEN = os.environ["TELEGRAM_TOKEN"].strip()
CHAT = os.environ["TELEGRAM_CHAT_ID"].strip()
BASE = "https://deals.3rrood.com/store/amazon_resale?gcat={}&stock=in"
CATS = {"mobiles": "موبايلات", "laptops": "لابتوبات", "tablets": "تابلت", "tvs": "تلفزيونات"}
SEEN = "seen.json"
UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36")


def send(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT, "text": text[:4000]},
        timeout=30,
    )
    print("telegram status:", r.status_code)


FIND_JS = """() => {
  const out = new Map();
  document.querySelectorAll('a[href]').forEach(a => {
    let el = a;
    for (let i = 0; i < 4 && el; i++) {
      if (el.innerText && el.innerText.includes('ج.م')) {
        out.set(a.href, el.innerText);
        break;
      }
      el = el.parentElement;
    }
  });
  return [...out].map(([href, text]) => ({href, text}));
}"""

DIAG_JS = """() => ({
  title: document.title,
  anchors: document.querySelectorAll('a[href]').length,
  text: document.body ? document.body.innerText.slice(0, 400) : ''
})"""


def scrape(page, cat):
    page.goto(BASE.format(cat), wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector("text=ج.م", timeout=20000)
    except Exception:
        pass
    page.wait_for_timeout(2000)
    raw = page.evaluate(FIND_JS)
    items = {}
    for r in raw:
        lines = [l.strip() for l in r["text"].split("\n") if l.strip()]
        if not lines:
            continue
        title = max(lines, key=len)
        price = next((l for l in lines if re.fullmatch(r"[\d,\.]+", l)), "?")
        items[r["href"]] = {"title": title[:120], "price": price}
    diag = page.evaluate(DIAG_JS) if not items else None
    print(cat, "found", len(items), "products")
    return items, diag


def main():
    seen = json.load(open(SEEN)) if os.path.exists(SEEN) else {}
    report = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, locale="ar-EG", viewport={"width": 412, "height": 915})
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()
        for cat, name in CATS.items():
            try:
                items, diag = scrape(page, cat)
            except Exception as e:
                print(cat, "ERROR", str(e)[:150])
                report.append(f"{name}: فشل ({str(e)[:80]})")
                continue
            if not items:
                report.append(f"{name}: 0 منتج | عنوان الصفحة: {diag['title']} | روابط: {diag['anchors']}\n{diag['text']}")
                continue
            if not seen.get(cat):
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
        send("تقرير:\n\n" + "\n\n".join(report))
    json.dump(seen, open(SEEN, "w"), ensure_ascii=False)


main()
