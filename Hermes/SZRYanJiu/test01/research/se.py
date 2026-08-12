import urllib.request, urllib.parse, json, re, html as htmllib, sys

UA = "Mozilla/5.0"

def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")

def se_question(site, qid):
    u = (f"https://api.stackexchange.com/2.3/questions/{qid}?site={site}"
         "&filter=withbody")
    j = json.loads(fetch(u))
    return j["items"][0] if j.get("items") else None

def se_answers(site, qid):
    u = (f"https://api.stackexchange.com/2.3/questions/{qid}/answers?site={site}"
         "&filter=withbody&sort=votes")
    j = json.loads(fetch(u))
    return j.get("items", [])

def strip(h):
    h = re.sub(r"<pre><code[^>]*>(.*?)</code></pre>", lambda m: "\n```\n" + m.group(1) + "\n```\n", h, flags=re.S)
    h = re.sub(r"<code[^>]*>(.*?)</code>", lambda m: "`" + m.group(1) + "`", h, flags=re.S)
    h = re.sub(r"<li[^>]*>", "\n- ", h)
    h = re.sub(r"<p[^>]*>", "\n\n", h)
    h = re.sub(r"<br\s*/?>", "\n", h)
    h = re.sub(r"<img[^>]+src=\"([^\"]+)\"[^>]*>", r"[img:\1]", h)
    h = re.sub(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"\2 (\1)", h, flags=re.S)
    h = re.sub(r"<[^>]+>", "", h)
    return htmllib.unescape(h)

if __name__ == "__main__":
    site, qid = sys.argv[1], sys.argv[2]
    q = se_question(site, qid)
    print("# ", q["title"])
    print(q["link"])
    print(strip(q["body"])[:3000])
    print("\n\n===== ANSWERS =====")
    for a in se_answers(site, qid):
        print(f"\n--- answer score={a['score']} accepted={a.get('is_accepted')}")
        print(strip(a["body"])[:4000])
