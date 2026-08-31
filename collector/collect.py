#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""항공권 가격을 수집해 docs/data/*.json 에 기록하고, 목표가 이하일 때만 알림을 보낸다.

GitHub Actions 에서 주기 실행되는 것을 전제로 한다.
필요한 환경변수:
    RAPIDAPI_KEY          (필수)
    TELEGRAM_BOT_TOKEN    (선택, 알림용)
    TELEGRAM_CHAT_ID      (선택, 알림용)
"""

import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skyscanner

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")
DATA_DIR = os.path.join(ROOT, "docs", "data")
HISTORY_PATH = os.path.join(DATA_DIR, "history.json")
LATEST_PATH = os.path.join(DATA_DIR, "latest.json")

KST = dt.timezone(dt.timedelta(hours=9))
MAX_OFFERS_KEPT = 12

# 스카이스캐너는 항공사명을 영문으로 준다. 알림 문구를 한글로 맞춘다.
AIRLINE_KO = {
    "Jeju Air": "제주항공", "Jin Air": "진에어", "T'way Air": "티웨이항공",
    "Tway Air": "티웨이항공", "Air Busan": "에어부산", "Air Seoul": "에어서울",
    "Korean Air": "대한항공", "Asiana Airlines": "아시아나항공",
    "Philippine Airlines": "필리핀항공", "Cebu Pacific": "세부퍼시픽",
    "Philippines AirAsia": "필리핀 에어아시아", "AirAsia": "에어아시아",
    "Cathay Pacific": "캐세이퍼시픽", "Singapore Airlines": "싱가포르항공",
    "Scoot": "스쿠트", "EVA Air": "에바항공", "China Airlines": "중화항공",
    "Vietjet Air": "비엣젯항공", "Vietnam Airlines": "베트남항공",
    "Japan Airlines": "일본항공", "All Nippon Airways": "전일본공수",
    "Malaysia Airlines": "말레이시아항공", "Batik Air": "바틱에어",
}


def airline_ko(name):
    if not name:
        return "항공사 미상"
    return AIRLINE_KO.get(name.strip(), name)


def now_kst():
    return dt.datetime.now(KST)


def won(n):
    return "{:,}원".format(int(n))


def read_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return default


def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write("\n")


# ------------------------------------------------------------------ 링크

def booking_links(trip):
    dep_c = trip["departure_date"].replace("-", "")
    ret_c = trip["return_date"].replace("-", "")
    adults = int(trip.get("adults", 1))
    return {
        "skyscanner": "https://www.skyscanner.co.kr/transport/flights/%s/%s/%s/%s/?adults=%d"
                      % (trip["origin"].lower(), trip["destination"].lower(),
                         dep_c[2:], ret_c[2:], adults),
        "naver": "https://flight.naver.com/flights/international/%s-%s-%s/%s-%s-%s?adult=%d"
                 % (trip["origin"], trip["destination"], dep_c,
                    trip["destination"], trip["origin"], ret_c, adults),
        "google": "https://www.google.com/travel/flights?q=" + urllib.parse.quote(
            "Flights from %s to %s on %s through %s"
            % (trip["origin"], trip["destination"],
               trip["departure_date"], trip["return_date"])),
    }


# ------------------------------------------------------------------ 알림

def send_telegram(token, chat_id, text):
    data = urllib.parse.urlencode({
        "chat_id": chat_id, "text": text, "disable_web_page_preview": "true",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.telegram.org/bot%s/sendMessage" % token, data=data)
    with urllib.request.urlopen(req, timeout=25) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError("텔레그램 응답: %s" % payload)


def should_alert(best, alert_cfg, history):
    """30만원대(임계값 이하)일 때만 True. 중복 알림은 억제한다."""
    threshold = int(alert_cfg.get("threshold_per_person", 399000))
    if best > threshold:
        return False, "목표가(%s) 초과" % won(threshold)

    past = history.get("alerts") or []
    if past:
        last = past[-1]
        try:
            last_ts = dt.datetime.fromisoformat(last["at"])
        except (ValueError, KeyError):
            return True, "알림"
        hours = (now_kst() - last_ts).total_seconds() / 3600.0
        if hours < float(alert_cfg.get("repeat_alert_hours", 12)) and best >= last.get("price", 0):
            return False, "최근 %.1f시간 내 동일/상위 가격으로 이미 알림" % hours
    return True, "알림"


def compose_alert(trip, best, offers, alert_cfg, site_url):
    adults = int(trip.get("adults", 1))
    baseline = alert_cfg.get("baseline_per_person")
    links = booking_links(trip)

    lines = [
        "✈️ 보홀 항공권 30만원대 진입!",
        "",
        "%s → %s  (%s ~ %s, %d인)" % (
            trip.get("origin_name", trip["origin"]),
            trip.get("destination_name", trip["destination"]),
            trip["departure_date"], trip["return_date"], adults),
        "최저가 %s / 1인   →   총 %s" % (won(best), won(best * adults)),
    ]
    if baseline:
        d = best - int(baseline)
        lines.append("지난 구매가(%s/인) 대비 %s%s" % (won(baseline), "+" if d > 0 else "", won(d)))
    lines += ["", "── 후보 ──"]
    for o in offers[:4]:
        stops = o.get("stops")
        stop_txt = "직항" if stops == 0 else ("%s회 경유" % stops if stops else "경유 정보 없음")
        when = (o.get("depart_at") or "")[:16].replace("T", " ")
        lines.append("· %s  %s  %s  %s" % (
            won(o["price_per_person"]), airline_ko(o.get("airline")), stop_txt, when))
    lines += [
        "",
        "예약 확인:",
        "· 스카이스캐너 %s" % links["skyscanner"],
        "· 네이버항공권 %s" % links["naver"],
    ]
    if site_url:
        lines += ["", "가격 추이: %s" % site_url]
    lines += ["", "※ 실제 결제가는 예약 사이트에서 최종 확인하세요."]
    return "\n".join(lines)


# ------------------------------------------------------------------ 메인

def main():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)
    trip = config["trip"]
    alert_cfg = config.get("alert") or {}
    adults = int(trip.get("adults", 1))
    site_url = os.environ.get("SITE_URL", "").strip()

    history = read_json(HISTORY_PATH, {"route": None, "points": [], "alerts": []})
    history.setdefault("points", [])
    history.setdefault("alerts", [])

    stamp = now_kst().replace(microsecond=0).isoformat()
    api_key = os.environ.get("RAPIDAPI_KEY", "").strip()

    offers, meta, error = [], {}, None
    if not api_key:
        error = "RAPIDAPI_KEY 가 설정되지 않았습니다."
    else:
        try:
            offers, meta = skyscanner.search_round_trip(
                trip, config.get("sky_ids") or {}, api_key)
        except skyscanner.SkyscannerError as e:
            error = str(e)
        except Exception as e:
            error = "예상치 못한 오류: %s" % e

    status = meta.get("status")
    direct_only = bool(trip.get("non_stop_only"))

    # 직항만 볼 때는 filterStats 의 직항 최저가를 기준으로 삼는다. 응답에 실려 오는
    # 여정 8건에 더 싼 직항이 빠져 있을 수 있기 때문이다.
    listed = offers[0]["price_per_person"] if offers else None
    if direct_only:
        best = meta.get("direct_min") or listed
    else:
        best = listed
    threshold = int(alert_cfg.get("threshold_per_person", 399000))

    # ---- 이력 기록 (실패한 회차도 남겨서 사이트에서 공백을 알 수 있게 한다)
    if best is not None:
        history["points"].append({"at": stamp, "best": best, "count": len(offers)})
    history["route"] = {
        "origin": trip["origin"], "destination": trip["destination"],
        "origin_name": trip.get("origin_name"), "destination_name": trip.get("destination_name"),
        "departure_date": trip["departure_date"], "return_date": trip["return_date"],
        "adults": adults, "currency": trip.get("currency", "KRW"),
    }
    lows = [p["best"] for p in history["points"]]
    history["all_time_low"] = min(lows) if lows else None
    history["updated_at"] = stamp

    # ---- 알림 판정: 30만원대 이하일 때만
    alerted, reason = False, "가격을 가져오지 못함"
    if best is not None:
        ok, reason = should_alert(best, alert_cfg, history)
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        if ok and token and chat_id:
            try:
                send_telegram(token, chat_id,
                              compose_alert(trip, best, offers, alert_cfg, site_url))
                history["alerts"].append({"at": stamp, "price": best})
                alerted, reason = True, "알림 발송"
            except Exception as e:
                reason = "알림 발송 실패: %s" % e
        elif ok:
            reason = "조건 충족했으나 텔레그램 설정이 없어 발송 생략"

    write_json(HISTORY_PATH, history)
    write_json(LATEST_PATH, {
        "collected_at": stamp,
        "trip": history["route"],
        "threshold_per_person": threshold,
        "baseline_per_person": alert_cfg.get("baseline_per_person"),
        "best_per_person": best,
        "best_total": best * adults if best is not None else None,
        "all_time_low": history["all_time_low"],
        "offers": offers[:MAX_OFFERS_KEPT],
        "search_status": status,
        "direct_only": direct_only,
        "listed_best": listed,
        "one_stop_min": meta.get("one_stop_min"),
        "error": error,
        "alerted": alerted,
        "alert_reason": reason,
        "links": booking_links(trip),
    })

    # ---- 로그
    print("[%s] 수집 결과" % stamp)
    if error:
        print("  오류: %s" % error)
    print("  조회 건수: %d%s" % (len(offers), " (직항만)" if direct_only else ""))
    if direct_only and meta.get("one_stop_min"):
        print("  참고 - 1회 경유 최저가: %s" % won(meta["one_stop_min"]))
    if best is not None:
        print("  최저가: %s / 1인 (총 %s)" % (won(best), won(best * adults)))
        print("  역대 최저: %s" % won(history["all_time_low"]))
    print("  알림: %s (%s)" % ("발송" if alerted else "안 함", reason))
    return 0 if not error else 1


if __name__ == "__main__":
    sys.exit(main())
