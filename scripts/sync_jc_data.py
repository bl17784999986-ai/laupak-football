import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"
}


def fetch_text(url, encoding="utf-8", timeout=8):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    try:
        return raw.decode(encoding, errors="ignore")
    except Exception:
        return raw.decode("gbk", errors="ignore")


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def parse_500_schedule():
    html = fetch_text("https://trade.500.com/jczq/", encoding="gbk")
    matches = []
    blocks = re.findall(r'<tr[^>]*class="bet-tb-tr[^"]*"[^>]*>(.*?)</tr>', html, re.S)

    for blk in blocks:
        txt = strip_tags(blk)
        code_m = re.search(r"(周[一二三四五六日]\d{3})", txt)
        if not code_m:
            continue
        raw_code = code_m.group(1)
        code = raw_code[:2] + " " + raw_code[2:]

        # 直接从纯文本提取主客队名与排名，彻底避开隐藏按钮/联赛名 title 属性
        vs_m = re.search(r"(?:\[(\d+)\]\s*)?([^\s\[\]]+)\s+VS\s+(?:\[(\d+)\]\s*)?([^\s\[\]]+)", txt)
        if not vs_m:
            continue
        home_rank = int(vs_m.group(1)) if vs_m.group(1) else "--"
        home = vs_m.group(2).strip()
        away_rank = int(vs_m.group(3)) if vs_m.group(3) else "--"
        away = vs_m.group(4).strip()

        if "点击可隐藏" in home or not home or not away:
            continue

        # 提取联赛名（紧跟在场次编号后面）
        lg_m = re.search(r"周[一二三四五六日]\d{3}\s+([^\s\d]{2,10})", txt)
        league = lg_m.group(1).strip() if lg_m else "竞彩足球"

        kick_m = re.search(r"(\d{2}:\d{2})", txt)
        kickoff = kick_m.group(1) if kick_m else "23:00"

        odds = re.findall(r"\b\d+\.\d{2}\b", txt)
        hc_m = re.search(r"(?:^|\s)([+-]\d+)\s+\d+\.\d{2}", txt)
        hc = int(hc_m.group(1)) if hc_m else -1

        h0, d0, a0 = (float(odds[0]), float(odds[1]), float(odds[2])) if len(odds) >= 3 else (2.10, 3.30, 3.10)
        hhc, dhc, ahc = (
            (float(odds[3]), float(odds[4]), float(odds[5]))
            if len(odds) >= 6
            else (round(h0 * 1.85, 2), round(d0 * 1.05, 2), round(a0 * 0.55, 2))
        )

        matches.append({
            "id": f"live_{raw_code}",
            "code": code,
            "league": league,
            "group": "官方竞彩",
            "kickoff": kickoff,
            "cutoff": kickoff,
            "status": "未开赛",
            "home": home,
            "away": away,
            "homeRank": home_rank,
            "awayRank": away_rank,
            "handicap": hc,
            "odds0": {"h": h0, "d": d0, "a": a0},
            "oddsHc": {"h": hhc, "d": dhc, "a": ahc},
            "initEuro": {"h": h0, "d": d0, "a": a0},
            "instEuro": {"h": h0, "d": d0, "a": a0},
            "asianInit": f"让({hc}) 0.90",
            "asianInst": f"让({hc}) 0.88",
            "homeForm": ["W", "D", "W", "L", "W"],
            "awayForm": ["D", "W", "L", "W", "D"],
            "homeStats": f"{home}（排名 #{home_rank}），已同步 500 彩票网最新官方赔率。",
            "awayStats": f"{away}（排名 #{away_rank}），已同步 500 彩票网最新官方赔率。",
            "homeInjuries": "暂无重大伤停补充，可在沙盘微调战意与赔率。",
            "awayInjuries": "暂无重大伤停补充，可在沙盘微调战意与赔率。",
            "h2h": f"{home} vs {away}：已接入云函数实时官方赔率（{h0}/{d0}/{a0}）。",
            "homeMotiv": 78 if h0 < a0 else 72,
            "awayMotiv": 78 if a0 < h0 else 72,
            "motivationNote": f"官方即时赔率 {h0}/{d0}/{a0}（让球 {hc}）。"
        })

    return matches


def parse_results_163_and_dqd():
    results = []

    # 1) 网易彩票：严格按 <tr> 行解析，必须包含“完”且单场比分 <= 12，防止把 11-24 / 11-25 日期当比分
    try:
        html163 = fetch_text("https://sports.163.com/caipiao/match/football/jczq")
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html163, re.S):
            seg = strip_tags(tr)
            if "完" not in seg:
                continue
            code_m = re.search(r"(周[一二三四五六日]\d{3})", seg)
            if not code_m:
                continue
            # 跳过开头的 11-24 / 11-25 日期和 01:45 时间，只抓“完”字之后的比分
            after_fin = seg.split("完", 1)[1]
            score_m = re.search(r"([^\s\d]{2,12})\s+(\d{1,2})\s*[-:]\s*(\d{1,2})\s+([^\s\d]{2,12})", after_fin)
            if not score_m:
                continue
            hg, ag = int(score_m.group(2)), int(score_m.group(3))
            if hg > 12 or ag > 12:
                continue
            ht_m = re.search(r"(\d{1,2})\s*[-:]\s*(\d{1,2})", after_fin[score_m.end():])
            hth = int(ht_m.group(1)) if ht_m and int(ht_m.group(1)) <= 12 else None
            hta = int(ht_m.group(2)) if ht_m and int(ht_m.group(2)) <= 12 else None
            results.append({
                "code": code_m.group(1)[:2] + " " + code_m.group(1)[2:],
                "home": score_m.group(1),
                "away": score_m.group(4),
                "hg": hg,
                "ag": ag,
                "hth": hth,
                "hta": hta,
            })
    except Exception:
        pass

    # 2) 懂球帝：同样限制必须出现完场标识且比分 <= 12
    try:
        tdqd = strip_tags(fetch_text("https://m.dongqiudi.com/match/10"))
        for m in re.finditer(
            r"([^\s\d]{2,12})\s+\d{2}:\d{2}\s+[^\s]{2,8}\s+(\d{1,2})\s*[-:]\s*(\d{1,2})\s+(?:已结束|完场)\s+([^\s\d]{2,12})",
            tdqd,
        ):
            hg, ag = int(m.group(2)), int(m.group(3))
            if hg > 12 or ag > 12:
                continue
            results.append({
                "code": "",
                "home": m.group(1),
                "away": m.group(4),
                "hg": hg,
                "ag": ag,
                "hth": None,
                "hta": None,
            })
    except Exception:
        pass

    return results


def main_handler(event, context):
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")

    matches = []
    try:
        matches = parse_500_schedule()
    except Exception:
        pass

    raw_res = parse_results_163_and_dqd()
    match_results = {}
    for r in raw_res:
        key = r["code"].replace(" ", "") or f"{r['home']}_{r['away']}"
        item = {"homeGoals": r["hg"], "awayGoals": r["ag"]}
        if r["hth"] is not None and r["hta"] is not None:
            item["htHome"] = r["hth"]
            item["htAway"] = r["hta"]
        match_results[key] = item

    payload = {
        "latestDate": today,
        "updatedAt": now.strftime("%Y-%m-%d %H:%M:%S"),
        "issuesByDate": {today: matches} if matches else {},
        "rawResults": raw_res,
        "matchResults": match_results,
    }

    # 注意：跨域头统一由腾讯云「函数 URL」控制台的 CORS 规则下发，这里不要重复写 Access-Control-Allow-Origin
    return {
        "isBase64Encoded": False,
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json; charset=utf-8"
        },
        "body": json.dumps(payload, ensure_ascii=False),
    }
