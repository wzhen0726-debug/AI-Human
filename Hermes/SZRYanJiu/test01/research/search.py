import urllib.request, urllib.parse, re, sys, json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")

def bing_search(q, n=10):
    url = "https://cn.bing.com/search?q=" + urllib.parse.quote(q)
    html = fetch(url)
    # extract result links & titles
    items = []
    for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", html, re.S):
        blk = m.group(1)
        href = re.search(r'href="([^"]+)"', blk)
        txt = re.sub(r"<[^>]+>", "", blk).strip()
        if href:
            items.append((href.group(1), txt))
    out = []
    for href, title in items[:n]:
        out.append({"url": href, "title": title})
    return out

def duck_search(q, n=10):
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q)
    html = fetch(url)
    out = []
    for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        href, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        ud = re.search(r"uddg=([^&]+)", href)
        if ud:
            href = urllib.parse.unquote(ud.group(1))
        out.append({"url": href, "title": title})
    return out[:n]

if __name__ == "__main__":
    q = sys.argv[1]
    engine = sys.argv[2] if len(sys.argv) > 2 else "ddg"
    try:
        res = duck_search(q) if engine == "ddg" else bing_search(q)
        for r in res:
            print(r["title"], "|", r["url"])
    except Exception as e:
        print("ERR", e)
