"""Bumerang: Facebook səhifəsindəki köhnə Reels-i gizlət (silmədən).
fb-hide/request.json: {"keep": ["<video_id>", ...]}  -> qalan bütün Reels gizlədilir.
Nəticə: fb-hide/result.json
"""
import json, os, urllib.parse, urllib.request, urllib.error

GV = os.environ.get("GRAPH_VERSION") or "v25.0"
G = f"https://graph.facebook.com/{GV}"
TOKEN = os.environ["META_TOKEN"]
PAGE = os.environ["FB_PAGE_ID"]


def call(method, path, token, **params):
    params["access_token"] = token
    data = None
    url = f"{G}/{path}"
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method), timeout=60) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return {"_error": json.loads(e.read().decode()).get("error", {}).get("message", "")}
        except Exception:
            return {"_error": str(e)}


def main():
    keep = set(json.load(open("fb-hide/request.json", encoding="utf-8")).get("keep", []))
    pt = call("GET", PAGE, TOKEN, fields="access_token").get("access_token") or TOKEN
    reels = call("GET", f"{PAGE}/video_reels", pt, fields="id,description,post_id,created_time", limit=50)
    out = {"listed_error": reels.get("_error"), "items": []}
    for v in reels.get("data", []):
        vid = v["id"]
        it = {"video_id": vid, "title": (v.get("description") or "").split("\n")[0][:60], "created": v.get("created_time")}
        if vid in keep:
            it["action"] = "saxlanıldı"
        else:
            pid = v.get("post_id")
            if not pid:
                pid = call("GET", vid, pt, fields="post_id").get("post_id")
            it["post_id"] = pid
            if pid:
                full = pid if "_" in str(pid) else f"{PAGE}_{pid}"
                r = call("POST", full, pt, is_hidden="true")
                it["action"] = "gizlədildi" if r.get("success") else f"xəta: {r.get('_error') or r}"
            else:
                it["action"] = "xəta: post_id tapılmadı"
        out["items"].append(it)
    json.dump(out, open("fb-hide/result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
