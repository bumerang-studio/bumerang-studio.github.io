"""Bumerang: Instagram + Facebook statistikası -> stats/latest.json, stats/history.csv"""
import csv, json, os, time, urllib.parse, urllib.request, urllib.error

GV = os.environ.get("GRAPH_VERSION") or "v25.0"
G = f"https://graph.facebook.com/{GV}"
TOKEN = os.environ["META_TOKEN"]
IG = os.environ["IG_USER_ID"]
PAGE = os.environ["FB_PAGE_ID"]


def get(path, token=None, **params):
    params["access_token"] = token or TOKEN
    url = f"{G}/{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get("error", {}).get("message", "")
        except Exception:
            msg = str(e)
        return {"_error": msg}


def ig_stats():
    acc = get(IG, fields="username,followers_count,media_count")
    media = get(f"{IG}/media", fields="id,caption,permalink,timestamp,like_count,comments_count,media_product_type", limit=30)
    items = []
    for mm in media.get("data", []):
        it = {k: mm.get(k) for k in ("permalink", "timestamp", "like_count", "comments_count")}
        it["title"] = (mm.get("caption") or "").split("\n")[0][:70]
        for met in ("views", "reach", "saved", "shares"):
            ins = get(f"{mm['id']}/insights", metric=met)
            if "_error" in ins:
                it["insights_error"] = ins["_error"][:160]
            for row in ins.get("data", []):
                it[row["name"]] = (row.get("values") or [{}])[0].get("value", row.get("total_value", {}).get("value"))
        items.append(it)
    return {"account": acc, "media": items, "media_error": media.get("_error")}


def fb_stats():
    page = get(PAGE, fields="name,followers_count,fan_count,access_token")
    pt = page.pop("access_token", None)
    reels = get(f"{PAGE}/video_reels", token=pt, fields="id,description,created_time,permalink_url", limit=20)
    items = []
    for r in reels.get("data", []):
        it = {"link": "https://www.facebook.com" + r.get("permalink_url", "") if r.get("permalink_url", "").startswith("/") else r.get("permalink_url"),
              "created": r.get("created_time"), "title": (r.get("description") or "").split("\n")[0][:70]}
        for met in ("blue_reels_play_count", "fb_reels_total_plays", "post_video_reach"):
            ins = get(f"{r['id']}/video_insights", token=pt, metric=met)
            if "_error" in ins:
                it.setdefault("insights_error", {})[met] = ins["_error"][:120]
            for row in ins.get("data", []):
                it[row["name"]] = (row.get("values") or [{}])[0].get("value")
        items.append(it)
    return {"page": page, "reels": items, "reels_error": reels.get("_error")}


def main():
    os.makedirs("stats", exist_ok=True)
    now = time.strftime("%Y-%m-%d %H:%M", time.gmtime(time.time() + 4 * 3600))
    data = {"time_baku": now, "instagram": ig_stats(), "facebook": fb_stats()}
    json.dump(data, open("stats/latest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    new = not os.path.exists("stats/history.csv")
    with open("stats/history.csv", "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time_baku", "platform", "title", "link", "views", "reach", "likes", "comments", "saved", "shares", "followers"])
        acc = data["instagram"]["account"]
        for it in data["instagram"]["media"]:
            w.writerow([now, "instagram", it.get("title"), it.get("permalink"), it.get("views"), it.get("reach"),
                        it.get("like_count"), it.get("comments_count"), it.get("saved"), it.get("shares"), acc.get("followers_count")])
        pg = data["facebook"]["page"]
        for it in data["facebook"]["reels"]:
            w.writerow([now, "facebook", it.get("title"), it.get("link"), it.get("blue_reels_play_count") or it.get("fb_reels_total_plays"),
                        it.get("post_video_reach"), "", "", "", "", pg.get("followers_count")])
    print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])


if __name__ == "__main__":
    main()
