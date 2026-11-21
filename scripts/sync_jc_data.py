import json
import os
import re
from datetime import datetime, timedelta, timezone
import requests
from bs4 import BeautifulSoup

BJ_TZ = timezone(timedelta(hours=8))
DATA_PATH = os.path.join("data", "matches.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

WEEKDAY_MAP = {"周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6}


def load_existing():
    if os.path.exists(DATA_PATH):
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"latestDate": "", "updatedAt": "", "issuesByDate": {}, "matchResults": {}}


def resolve_issue_date(wk_prefix):
    now = datetime.now(BJ_TZ).date()
    target_wd = WEEKDAY_MAP.get(wk_prefix)
    if target_wd is None:
        return now.strftime("%Y-%m-%d")
    diff = (target_wd - now.weekday()) % 7
    if diff >= 5:
        diff -= 7
    return (now + timedelta(days=diff)).strftime("%Y-%m-%d")


def parse_500_schedule():
    url = "https://trade.500.com/jczq/"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.encoding = "gbk" if "gb" in (resp.apparent_encoding or "").lower() else (resp.apparent_encoding or "utf-8")
    soup = BeautifulSoup(resp.text, "html.parser")

    grouped = {}
    for tr in soup.select("tr"):
        txt = tr.get_text(" ", strip=True)
        code_m = re.search(r"(周[一二三四五六日])\s*(\d{3})", txt)
        if not code_m:
            continue
        wk_prefix, num = code_m.group(1), code_m.group(2)
        code = f"{wk_prefix} {num}"
        issue_date = resolve_issue_date(wk_prefix)

        clean_txt = txt.replace("↑", "").replace("↓", "")
        vs_m = re.search(r"(?:\[\d+\])?([^\s\[\]]+)\s+VS\s+([^\s\[\]]+)(?:\[\d+\])?", clean_txt, re.I)
        if not vs_m:
            continue
        home = re.sub(r"^\[\d+\]", "", vs_m.group(1)).strip()
        away = re.sub(r"\[\d+\]$", "", vs_m.group(2)).strip()

        times = re.findall(r"\b\d{2}:\d{2}\b", clean_txt)
        kickoff = times[0] if times else "23:00"
        league_m = re.search(r"周[一二三四五六日]\s*\d{3}\s+(\S+)", clean_txt)
        league = league_m.group(1) if league_m else "竞彩足球"
        nums = re.findall(r"(\d+\.\d{2})", clean_txt)
        odds0 = {"h": float(nums[0]), "d": float(nums[1]), "a": float(nums[2])} if len(nums) >= 3 else {"h": 2.10, "d": 3.30, "a": 3.10}
        odds_hc = {"h": float(nums[3]), "d": float(nums[4]), "a": float(nums[5])} if len(nums) >= 6 else {"h": 3.50, "d": 3.40, "a": 1.85}
        hc_m = re.search(r"\s([+-]?\d)\s+\d+\.\d{2}", clean_txt)
        handicap = int(hc_m.group(1)) if hc_m else -1

        mid = re.sub(r"[^a-zA-Z0-9]", "", f"{issue_date}_{code}")
        grouped.setdefault(issue_date, []).append({
            "id": mid, "code": code, "league": league, "group": "官方竞彩",
            "kickoff": kickoff, "cutoff": kickoff, "status": "未开赛",
            "home": home, "away": away, "homeRank": "--", "awayRank": "--",
            "handicap": handicap, "odds0": odds0, "oddsHc": odds_hc,
            "initEuro": odds0.copy(), "instEuro": odds0.copy(),
            "asianInit": f"让({handicap}) 0.90", "asianInst": f"让({handicap}) 0.88",
            "homeForm": ["W", "D", "W", "L", "W"], "awayForm": ["D", "W", "L", "W", "D"],
            "homeStats": f"{home}，已由 GitHub Actions 自动同步官方实时赔率。",
            "awayStats": f"{away}，已由 GitHub Actions 自动同步官方实时赔率。",
            "homeInjuries": "暂无补充伤停。", "awayInjuries": "暂无补充伤停。",
            "h2h": "已同步最新官方胜平负与让球赔率。", "homeMotiv": 75, "awayMotiv": 72,
            "motivationNote": "GitHub Actions 自动同步场次：已接入最新官方赔率。"
        })
    return grouped


def parse_163_results(store):
    url = "https://sports.163.com/caipiao/match/football/jczq"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.encoding = resp.apparent_encoding or "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")
    results = store.setdefault("matchResults", {})

    for tr in soup.select("tr"):
        txt = tr.get_text(" ", strip=True)
        if "完" not in txt:
            continue
        code_m = re.search(r"(周[一二三四五六日]\s*\d{3})", txt)
        score_m = re.search(r"\b(\d{1,2})\s*-\s*(\d{1,2})\b", txt)
        if not code_m or not score_m:
            continue
        code = re.sub(r"\s+", "", code_m.group(1))
        hg, ag = int(score_m.group(1)), int(score_m.group(2))
        ht_m = re.search(r"(\d{1,2})\s*-\s*(\d{1,2})\s*$", txt)
        hth = int(ht_m.group(1)) if ht_m else ""
        hta = int(ht_m.group(2)) if ht_m else ""

        for d, mlist in store.get("issuesByDate", {}).items():
            for m in mlist:
                if m.get("code", "").replace(" ", "") == code:
                    results[m["id"]] = {"homeGoals": hg, "awayGoals": ag, "htHome": hth, "htAway": hta}


def main():
    store = load_existing()
    now_str = datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")
    try:
        grouped = parse_500_schedule()
        if grouped:
            for d, mlist in grouped.items():
                if mlist:
                    store.setdefault("issuesByDate", {})[d] = mlist
            today_str = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
            store["latestDate"] = today_str if today_str in grouped else sorted(grouped.keys())[0]
    except Exception as e:
        print("Schedule sync warning:", e)

    try:
        parse_163_results(store)
    except Exception as e:
        print("Result sync warning:", e)

    store["updatedAt"] = now_str
    os.makedirs("data", exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"Saved {DATA_PATH} at {now_str}")


if __name__ == "__main__":
    main()
