#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""공항 skyId / entityId 를 1회 조회해 config.json 에 채워 넣는다.

    RAPIDAPI_KEY=xxxx python3 collector/find_ids.py

이 ID 는 바뀌지 않으므로 한 번만 실행하면 되고, 이후 수집은 API 호출 1회만 쓴다.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skyscanner

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config.json")


def main():
    api_key = os.environ.get("RAPIDAPI_KEY", "").strip()
    if not api_key:
        sys.exit("환경변수 RAPIDAPI_KEY 가 필요합니다.\n예)  RAPIDAPI_KEY=발급받은키 python3 collector/find_ids.py")

    with open(CONFIG, encoding="utf-8") as f:
        config = json.load(f)
    trip = config["trip"]
    locale = trip.get("market", "ko-KR")

    updated = dict(config.get("sky_ids") or {})
    for role, code in (("origin", trip["origin"]), ("destination", trip["destination"])):
        try:
            sky_id, entity_id, title = skyscanner.find_airport(code, api_key, locale)
        except skyscanner.SkyscannerError as e:
            sys.exit("%s(%s) 조회 실패: %s" % (role, code, e))
        print("%-12s %s → skyId=%s  entityId=%s" % (role, title, sky_id, entity_id))
        updated["%s_sky_id" % role] = sky_id
        updated["%s_entity_id" % role] = str(entity_id)

    config["sky_ids"] = updated
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("\nconfig.json 의 sky_ids 를 갱신했습니다. 이 파일을 커밋하세요.")


if __name__ == "__main__":
    main()
