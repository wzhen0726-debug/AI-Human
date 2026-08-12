import urllib.request, urllib.parse, json, sys

SEARX = "https://search.mectov.my.id"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"

def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")

def search(q, n=10):
    url = SEARX + "/search?q=" + urllib.parse.quote(q) + "&format=json"
    j = json.loads(fetch(url))
    return [(r["title"], r["url"], r.get("content","")[:200]) for r in j.get("results", [])[:n]]

if __name__ == "__main__":
    q = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    try:
        for t, u, c in search(q, n):
            print(t[:100])
            print("  ", u[:150])
            if c: print("  ", c.replace("\n"," ")[:180])
    except Exception as e:
        print("ERR", e)
