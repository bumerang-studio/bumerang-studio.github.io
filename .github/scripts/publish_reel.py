"""Bumerang: Instagram + Facebook Reels avtomatik paylaşım.

reels/<slug>/video.mp4 + reels/<slug>/post.json push edildikdə işləyir.
post.json: {"caption": "...", "thumb_offset_ms": 10200, "instagram": true, "facebook": true}
Nəticə reels/<slug>/result.json faylına yazılır.
"""
import json, os, sys, time, urllib.parse, urllib.request, urllib.error

GV = os.environ.get("GRAPH_VERSION") or "v25.0"
G = f"https://graph.facebook.com/{GV}"
TOKEN = os.environ["META_TOKEN"]
IG_USER = os.environ["IG_USER_ID"]
PAGE = os.environ["FB_PAGE_ID"]
SITE = "https://bumerang-studio.github.io"


def call(method, url, params=None, headers=None, data=None):
    params = dict(params or {})
    body = None
    if method == "GET":
        url = url + "?" + urllib.parse.urlencode(params)
    else:
        body = data if data is not None else urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        txt = e.read().decode(errors="replace")
        raise RuntimeError(f"{method} {url.split('?')[0]} -> {e.code}: {txt}")


def wait_public(url, size):
    for _ in range(60):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status == 200 and int(r.headers.get("Content-Length", "0")) == size:
                    return
        except Exception:
            pass
        time.sleep(10)
    raise RuntimeError(f"Video saytda görünmədi: {url}")


def instagram(video_url, caption, thumb):
    p = {"media_type": "REELS", "video_url": video_url, "caption": caption,
         "share_to_feed": "true", "access_token": TOKEN}
    if thumb is not None:
        p["thumb_offset"] = str(thumb)
    cid = call("POST", f"{G}/{IG_USER}/media", p)["id"]
    for _ in range(60):
        st = call("GET", f"{G}/{cid}", {"fields": "status_code,status", "access_token": TOKEN})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram video emal xətası: {st}")
        time.sleep(10)
    mid = call("POST", f"{G}/{IG_USER}/media_publish", {"creation_id": cid, "access_token": TOKEN})["id"]
    info = call("GET", f"{G}/{mid}", {"fields": "permalink", "access_token": TOKEN})
    return {"id": mid, "permalink": info.get("permalink")}


def page_token():
    r = call("GET", f"{G}/{PAGE}", {"fields": "access_token", "access_token": TOKEN})
    return r.get("access_token") or TOKEN


def facebook(video_url, caption):
    pt = page_token()
    s = call("POST", f"{G}/{PAGE}/video_reels", {"upload_phase": "start", "access_token": pt})
    vid = s["video_id"]
    call("POST", s.get("upload_url") or f"https://rupload.facebook.com/video-upload/{GV}/{vid}",
         headers={"Authorization": f"OAuth {pt}", "file_url": video_url}, data=b"")
    call("POST", f"{G}/{PAGE}/video_reels", {"upload_phase": "finish", "video_id": vid,
         "video_state": "PUBLISHED", "description": caption, "access_token": pt})
    return {"video_id": vid, "link": f"https://www.facebook.com/reel/{vid}"}


def main(slug):
    folder = os.path.join("reels", slug)
    post = json.load(open(os.path.join(folder, "post.json"), encoding="utf-8"))
    video = os.path.join(folder, "video.mp4")
    url = f"{SITE}/reels/{urllib.parse.quote(slug)}/video.mp4"
    wait_public(url, os.path.getsize(video))
    res = {"slug": slug, "time_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())}
    ok = True
    if post.get("instagram", True):
        try:
            res["instagram"] = instagram(url, post["caption"], post.get("thumb_offset_ms"))
        except Exception as e:
            ok = False; res["instagram_error"] = str(e)
    if post.get("facebook", True):
        try:
            res["facebook"] = facebook(url, post["caption"])
        except Exception as e:
            ok = False; res["facebook_error"] = str(e)
    res["ok"] = ok
    json.dump(res, open(os.path.join(folder, "result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return ok


if __name__ == "__main__":
    good = all([main(s) for s in sys.argv[1:] if s.strip()])
    sys.exit(0 if good else 1)
