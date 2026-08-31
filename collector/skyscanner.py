# -*- coding: utf-8 -*-
"""스카이스캐너 항공권 조회 (RapidAPI 'Sky-Scrapper' 래퍼).

주의: 스카이스캐너 공식 API는 상업 파트너십 승인이 필요해 개인은 쓸 수 없다.
여기서는 RapidAPI 에 올라온 비공식 래퍼를 사용한다. 응답 스키마가 예고 없이
바뀔 수 있으므로 모든 필드 접근은 방어적으로 처리한다.

반환 형식(1인 왕복 기준으로 정규화):
    {price_per_person, currency, airline, stops, depart_at, arrive_at,
     return_depart_at, duration_minutes, link}
"""

import json
import urllib.error
import urllib.parse
import urllib.request

HOST = "sky-scrapper.p.rapidapi.com"
BASE = "https://" + HOST
TIMEOUT = 40


class SkyscannerError(Exception):
    pass


def _get(path, params, api_key):
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": HOST,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        if e.code == 429:
            raise SkyscannerError("RapidAPI 호출 한도 초과(429). 무료 등급은 월 100회입니다. %s" % detail)
        if e.code in (401, 403):
            raise SkyscannerError("RapidAPI 인증 실패(%s). RAPIDAPI_KEY 와 Sky-Scrapper 구독 상태를 확인하세요. %s" % (e.code, detail))
        raise SkyscannerError("HTTP %s - %s" % (e.code, detail))
    except urllib.error.URLError as e:
        raise SkyscannerError("네트워크 오류: %s" % e.reason)
    except ValueError as e:
        raise SkyscannerError("JSON 파싱 실패: %s" % e)


def find_airport(query, api_key, locale="ko-KR"):
    """공항 검색 → (skyId, entityId, 표시이름). ID 를 config 에 캐시해 두면 호출을 아낀다."""
    payload = _get("/api/v1/flights/searchAirport",
                   {"query": query, "locale": locale}, api_key)
    items = payload.get("data") or []
    if not items:
        raise SkyscannerError("공항을 찾지 못했습니다: %s" % query)
    top = items[0]
    pres = top.get("presentation") or {}
    nav = top.get("navigation") or {}
    return (
        top.get("skyId") or (nav.get("relevantFlightParams") or {}).get("skyId"),
        top.get("entityId") or (nav.get("relevantFlightParams") or {}).get("entityId"),
        pres.get("title") or pres.get("suggestionTitle") or query,
    )


def _iso(value):
    return value if isinstance(value, str) else None


def _parse_itineraries(payload, currency):
    """응답에서 여정 목록을 뽑아 정규화한다."""
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SkyscannerError("예상과 다른 응답 형식입니다: %s" % str(payload)[:300])

    itineraries = data.get("itineraries")
    if itineraries is None:
        # 일부 응답은 data.itineraries.results 형태로 내려온다
        itineraries = ((data.get("itineraries") or {}) if isinstance(data.get("itineraries"), dict) else {}).get("results")
    if not itineraries:
        return [], (data.get("context") or {}).get("status")

    offers = []
    for it in itineraries:
        if not isinstance(it, dict):
            continue
        price = it.get("price") or {}
        raw = price.get("raw")
        if raw is None:
            continue
        legs = it.get("legs") or []
        out = legs[0] if len(legs) > 0 and isinstance(legs[0], dict) else {}
        back = legs[1] if len(legs) > 1 and isinstance(legs[1], dict) else {}

        carriers = (out.get("carriers") or {}).get("marketing") or []
        airline = None
        for c in carriers:
            if isinstance(c, dict) and c.get("name"):
                airline = c["name"]
                break

        offers.append({
            "price_per_person": int(round(float(raw))),
            "currency": currency,
            "airline": airline,
            "stops": out.get("stopCount"),
            "depart_at": _iso(out.get("departure")),
            "arrive_at": _iso(out.get("arrival")),
            "return_depart_at": _iso(back.get("departure")),
            "duration_minutes": out.get("durationInMinutes"),
            "link": None,
        })

    offers.sort(key=lambda o: o["price_per_person"])
    return offers, (data.get("context") or {}).get("status")


def search_round_trip(trip, ids, api_key):
    """왕복 조회. 1인 기준으로 요청해 가격을 1인가로 확정한다."""
    missing = [k for k in ("origin_sky_id", "origin_entity_id",
                           "destination_sky_id", "destination_entity_id")
               if not ids.get(k)]
    if missing:
        raise SkyscannerError(
            "config.json 의 sky_ids 가 비어 있습니다(%s). "
            "먼저 `python3 collector/find_ids.py` 를 실행하세요." % ", ".join(missing))

    params = {
        "originSkyId": ids["origin_sky_id"],
        "destinationSkyId": ids["destination_sky_id"],
        "originEntityId": ids["origin_entity_id"],
        "destinationEntityId": ids["destination_entity_id"],
        "date": trip["departure_date"],
        "returnDate": trip["return_date"],
        "adults": 1,
        "cabinClass": trip.get("cabin_class", "economy"),
        "currency": trip.get("currency", "KRW"),
        "market": trip.get("market", "ko-KR"),
        "countryCode": trip.get("country_code", "KR"),
    }
    payload = _get("/api/v1/flights/searchFlights", params, api_key)

    if payload.get("status") is False:
        raise SkyscannerError("조회 실패: %s" % (payload.get("message") or payload))

    offers, status = _parse_itineraries(payload, trip.get("currency", "KRW"))
    return offers, status
