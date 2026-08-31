# 보홀 항공권 최저가 추적 (ICN ⇄ TAG)

인천 → 보홀 팡라오 **2026-11-18(수) 출발 / 2026-11-21(토) 귀국** 왕복 항공권을
GitHub Actions 가 **12시간마다 자동으로 수집**해서 웹사이트에 기록하고,
**1인 30만원대(399,000원 이하)** 로 떨어지면 텔레그램으로 알립니다.

**직항편만 추적합니다.** (인천-보홀 직항은 현재 제주항공이 운항)

맥북과 무관하게 GitHub 서버에서 돌기 때문에 노트북이 꺼져 있어도 계속 수집됩니다.

- 데이터 수집: GitHub Actions (무료)
- 웹사이트: GitHub Pages (무료)
- 가격 이력 저장: 저장소의 `docs/data/*.json` (별도 DB 불필요)
- 알림: 텔레그램 (무료)

---

## 1. 사전에 가입해야 하는 것

### ① GitHub 계정 — 필수
저장소 호스팅 + 수집 스케줄러 + 웹사이트를 전부 담당합니다. 무료 계정으로 충분합니다.
- 가입: https://github.com/signup
- **저장소는 Public 으로 만드세요.** 무료 계정은 Public 저장소에서만 GitHub Pages 를 쓸 수 있습니다.
  (API 키는 저장소가 아니라 Secrets 에 넣으므로 공개되지 않습니다.)

### ② RapidAPI 계정 + Sky-Scrapper 구독 — 필수
- 가입: https://rapidapi.com/auth/sign-up
- 접속: https://rapidapi.com/apiheya/api/sky-scrapper → **Subscribe to Test → Basic (무료)** 선택
- 무료 등급은 **월 100회** 호출 제한 → 12시간 주기(하루 2회 ≈ 월 62회)로 여유 있게 잡았습니다.
- 구독 후 `X-RapidAPI-Key` 값을 복사해 두세요.

> ⚠️ **스카이스캐너 공식 API 는 개인이 가입할 수 없습니다.** 상업적 파트너십 심사를 거친
> 승인된 여행 사업자에게만 열려 있고 공개 무료 등급이 없습니다. Sky-Scrapper 는 RapidAPI 에
> 올라온 **비공식 서드파티 래퍼**이며, 스카이스캐너 데이터를 대신 긁어 전달합니다.
> 응답 형식이 예고 없이 바뀌거나 서비스가 중단될 수 있습니다.

### ③ 텔레그램 봇 — 알림 받으려면 필수
1. 텔레그램에서 **@BotFather** 검색 → `/newbot` → 이름 입력 → **봇 토큰** 받기
2. 방금 만든 봇과 대화창을 열고 아무 메시지나 한 번 보내기 *(이걸 해야 봇이 나에게 말을 걸 수 있습니다)*
3. 텔레그램에서 **@userinfobot** 검색 → `/start` → 표시되는 **Id 숫자**가 chat_id

---

## 2. 설치 순서

### 2-1. 저장소 만들고 올리기
GitHub 에서 새 저장소(예: `bohol-flight`)를 **Public** 으로 만든 뒤, 이 폴더에서:

```bash
cd ~/비행기티켓팅 && git init -b main && git add . && git commit -m "보홀 항공권 추적기 초기 설정"
```

```bash
git remote add origin https://github.com/<내계정>/bohol-flight.git && git push -u origin main
```

### 2-2. Secrets 등록
저장소 → **Settings → Secrets and variables → Actions → New repository secret** 에서 3개 등록:

| 이름 | 값 |
|---|---|
| `RAPIDAPI_KEY` | RapidAPI 에서 복사한 키 |
| `TELEGRAM_BOT_TOKEN` | BotFather 가 준 토큰 |
| `TELEGRAM_CHAT_ID` | userinfobot 이 알려준 숫자 |

같은 화면의 **Variables** 탭에서 `SITE_URL` 도 등록하면(값: 아래 2-4 의 주소) 알림에 사이트 링크가 함께 옵니다.

### 2-3. 공항 ID 한 번 채우기
API 호출을 아끼기 위해 공항 ID 를 미리 저장해 둡니다. 맥북에서 한 번만 실행하세요:

```bash
cd ~/비행기티켓팅 && RAPIDAPI_KEY=발급받은키 python3 collector/find_ids.py
```

그다음 바뀐 `config.json` 을 커밋:

```bash
git add config.json && git commit -m "공항 ID 설정" && git push
```

### 2-4. 웹사이트 켜기
저장소 → **Settings → Pages** → Source: **Deploy from a branch** →
Branch: **main**, 폴더: **/docs** → Save.

1~2분 뒤 아래 주소에서 열립니다 (북마크해 두세요):

```
https://<내계정>.github.io/bohol-flight/
```

### 2-5. 첫 수집 실행
저장소 → **Actions** 탭 → 왼쪽 **항공권 가격 수집** → **Run workflow** 버튼.
1분 안에 끝나고, 사이트를 새로고침하면 첫 가격이 표시됩니다.

> Actions 탭에 "workflows aren't being run on this forked repository" 같은 안내가 뜨면
> **I understand my workflows, go ahead and enable them** 을 눌러 활성화하세요.

---

## 3. 알림 기준

| 항목 | 값 | 설명 |
|---|---|---|
| 알림 임계값 | **399,000원 / 1인** | 이하로 내려가면 텔레그램 발송. 30만원 미만도 당연히 포함됩니다. |
| 참고 기준가 | 350,000원 / 1인 | 지난 2·4월 실제 구매가. 알림에 차액이 표시됩니다. |
| 중복 억제 | 12시간 | 같은 값 이상으로는 12시간 내 다시 알리지 않습니다. |

임계값을 바꾸려면 `config.json` 의 `alert.threshold_per_person` 을 고치고 push 하세요.
목표가 위에서는 **알림이 전혀 가지 않습니다.** 가격 추이는 웹사이트에서 언제든 확인할 수 있습니다.

---

## 4. 알아두실 점

- **무료 한도**: 월 100회, 자동 수집은 월 약 62회. 수동 실행(`Run workflow`)도 한도를 소모합니다.
  한도를 넘기면 사이트에 "RapidAPI 호출 한도 초과" 오류가 표시됩니다.
- **가격 정확도**: 스카이스캐너 데이터 기반이지만 LCC 특가·유류할증료 반영 시점 차이로
  실제 결제가와 다를 수 있습니다. **알림은 "지금 확인할 때"라는 신호**로 쓰시고,
  결제 전 사이트의 스카이스캐너·네이버항공권 링크에서 최종 가격을 확인하세요.
- **스케줄 지연**: GitHub Actions 의 cron 은 최선노력 방식이라 정시보다 수십 분 늦을 수 있습니다.
- **60일 규칙**: 공개 저장소의 스케줄 워크플로는 저장소가 60일간 활동이 없으면 자동 비활성화됩니다.
  이 워크플로는 매 수집마다 데이터를 커밋하므로 해당되지 않습니다.

## 5. 파일 구성

| 경로 | 역할 |
|---|---|
| `config.json` | 여행 조건 · 알림 임계값 · 공항 ID |
| `collector/collect.py` | 수집 → 기록 → 알림 판정 → 텔레그램 발송 |
| `collector/skyscanner.py` | Sky-Scrapper API 어댑터 |
| `collector/find_ids.py` | 공항 ID 1회 조회용 |
| `.github/workflows/collect.yml` | 12시간 주기 자동 실행 (한국시간 09:10 / 21:10) |
| `docs/index.html` | 대시보드 (GitHub Pages 로 서빙) |
| `docs/data/*.json` | 가격 이력 · 최신 결과 (자동 갱신·커밋) |

---

## 직항만 추적하는 방식

이 API 는 `stops=direct` 같은 서버측 경유 필터를 **무시합니다**(경유편이 그대로 옵니다).
그래서 두 가지를 함께 씁니다.

1. 응답으로 오는 여정 목록에서 `stopCount == 0` 인 것만 걸러 화면에 표시
2. 최저가 판정은 `filterStats.stopPrices.direct` 값을 사용
   — 응답에 실려 오지 않은 더 싼 직항까지 반영된 값이라 1번보다 정확합니다

경유편도 다시 보고 싶으면 `config.json` 의 `trip.non_stop_only` 를 `false` 로 바꾸세요.
단, 직항 기준으로 쌓인 이력과 섞이면 그래프가 왜곡되므로 `docs/data/history.json` 의
`points` 를 비우는 편이 좋습니다.
