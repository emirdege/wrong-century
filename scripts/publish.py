#!/usr/bin/env python3
"""Wrong Century — günlük yayın + oy sayımı.

Her çalıştırmada:
1. Son yayınlanan bölümün yorumlarını Make "WC Comments" webhook'undan çeker,
   A/B oylarını sayar ve kazananı seçer.
2. Kazanan dalın bölümü (örn. E2a / E2b) media/ klasöründe hazırsa
   Make "WC Publish" webhook'u ile YouTube + Instagram + Facebook'a yükler.
3. Sonucu state.json'a yazar (workflow commit eder).

Webhook adresleri GitHub Actions secret'larından gelir; kodda yer almaz.
"""
import json, os, re, sys, time, datetime as dt, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "state.json")
EPISODES = os.path.join(ROOT, "episodes.json")
PAGES_BASE = os.environ.get("PAGES_BASE", "").rstrip("/")
PUBLISH_HOOK = os.environ.get("MAKE_PUBLISH_HOOK", "")
COMMENTS_HOOK = os.environ.get("MAKE_COMMENTS_HOOK", "")
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
MIN_HOURS_BETWEEN = float(os.environ.get("MIN_HOURS_BETWEEN", "20"))

START_RE = re.compile(r"^\W*([ab])(?:\W|$)", re.I)          # "A", "b!!", "A for sure", "🅰️ A"
PHRASE_RE = re.compile(r"\b(?:option|vote|voting|choose|choice|team|going with)\s*([ab])\b", re.I)


def load(p, default):
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return default


def save(p, data):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def post(url, payload, timeout=900):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def count_votes(text):
    """Her yorumda tek oy: satır A/B ile başlıyorsa ya da 'vote B', 'option A' gibi ifade varsa."""
    votes = {"A": 0, "B": 0}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("===") or len(line) > 200:
            continue
        m = START_RE.match(line) or PHRASE_RE.search(line)
        if m:
            votes[m.group(1).upper()] += 1
    return votes


def main():
    state = load(STATE, {"published": []})
    episodes = load(EPISODES, {})
    now = dt.datetime.now(dt.timezone.utc)

    last = state["published"][-1] if state["published"] else None
    if last:
        age_h = (now - dt.datetime.fromisoformat(last["at"])).total_seconds() / 3600
        if age_h < MIN_HOURS_BETWEEN:
            print(f"Son yayın {age_h:.1f} saat önce; bekleniyor.")
            return
        # Üretim görevi oyları önceden saydıysa onun kararını kullan (aynı videoyu üretti)
        if state.get("next"):
            nxt = state.pop("next")
            print(f"Önceden karar verilmiş: {last['id']} → {nxt}")
            return publish(state, episodes, nxt, now)
        # oy sayımı
        votes = {"A": 0, "B": 0}
        if COMMENTS_HOOK and not DRY_RUN:
            txt = post(COMMENTS_HOOK, {"ig_media_id": last.get("instagram_id", ""),
                                       "fb_post_id": last.get("facebook_id", ""),
                                       "yt_video_id": last.get("youtube_id", "")}, timeout=300)
            votes = count_votes(txt)
        winner = "B" if votes["B"] > votes["A"] else "A"   # eşitlikte A
        last["votes"] = votes
        last["winner"] = winner
        nxt = episodes.get(last["id"], {}).get("next", {}).get(winner)
        print(f"{last['id']} oyları: {votes} → {winner} → {nxt}")
    else:
        nxt = episodes.get("_start")

    return publish(state, episodes, nxt, now)


def publish(state, episodes, nxt, now):
    if not nxt:
        print("Sıradaki bölüm tanımlı değil (sezon sonu ya da episodes.json eksik).")
        save(STATE, state)
        return
    ep = episodes.get(nxt)
    if not ep or not os.path.exists(os.path.join(ROOT, ep["file"])):
        msg = f"⚠️ {nxt} henüz hazır değil ({ep['file'] if ep else 'tanımsız'})."
        print(msg)
        state["waiting_for"] = nxt
        save(STATE, state)
        sys.exit(2)   # workflow kırmızı olur → e-posta bildirimi

    payload = {
        "video_url": f"{PAGES_BASE}/{ep['file']}",
        "yt_title": ep["yt_title"],
        "yt_description": ep["yt_description"],
        "caption": ep["caption"],
        "fb_description": ep.get("fb_description", ep["caption"]),
    }
    print("Yayınlanıyor:", nxt, payload["video_url"])
    if DRY_RUN:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    raw = post(PUBLISH_HOOK, payload)
    try:
        resp = json.loads(raw)
    except ValueError:
        # Make 180 sn içinde cevap veremezse "Accepted" döner; yayın büyük ihtimalle sürüyor.
        resp = {"raw_response": raw[:200]}
    state["published"].append({"id": nxt, "at": now.isoformat(timespec="seconds"), **resp})
    state.pop("waiting_for", None)
    save(STATE, state)
    print("Tamam:", resp)


if __name__ == "__main__":
    main()
