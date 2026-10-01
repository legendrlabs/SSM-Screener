# Special Situation Microcap Screener (SSM)

미국 상장 마이크로캡 중 **구조적 재평가 가능성이 있는 특수상황**을 재현 가능한 규칙으로 1차 선별하는 스크리너입니다.

핵심 원칙:

> **Basic market cap이 아니라 fully diluted economics를 본다.**  
> **보도자료보다 SEC filing에서 event proof를 확인한다.**  
> **숫자가 불완전하면 PASS가 아니라 DATA_HOLD다.**

## 찾는 유형

- 사업모델 전환 / 사명·티커 변경 / 역합병
- 사업부 매각 후 신사업 전환
- AI / 데이터센터 / 로봇 / 바이오 / 크립토 등 구조적 pivot
- 현금·증권·토큰·지분·부동산·광물 등 자산가치 대비 할인
- 회사 규모 대비 큰 계약 / 라이선스 / 정부계약 / 전략투자
- 부채 제거 / preferred redemption / refinancing
- low float + 확인 가능한 catalyst
- PIPE / 전략적 투자자가 시장가격과 다른 가격에 참여한 상황
- 8-K / 10-Q에서 확인되는 시장 미반영 변화

## 기본 Gate

`config/default.json`에서 조정합니다.

- 거래소: NASDAQ / NYSE / NYSE American
- 선호 basic MC: $20M ~ $500M
- 확장 universe: $1B 이하
- material event: 최근 60일
- 10-Q/10-K freshness: 210일
- ADV20: $250k 이상 PASS, $50k~250k WATCH, $50k 미만 REJECT
- cap table low confidence: `DATA_HOLD`

## 실행

```bash
python -m pip install -e .
export SEC_USER_AGENT="Your Name your@email.com"

ssm scan --days 7 --out output
ssm check AGPU AIB VIP --out output
pytest -q
```

기본 시장데이터 provider는 `yfinance`입니다. Alpaca를 사용하려면:

```bash
export SSM_MARKET_PROVIDER=alpaca
export APCA_API_KEY_ID=...
export APCA_API_SECRET_KEY=...
```

## SEC discovery modes

SSM은 두 가지 SEC discovery 경로를 지원합니다.

- `SSM_SEC_DISCOVERY_MODE=atom` — GitHub-hosted/public 배포 기본값. SEC Latest Filings Atom feed로 신규 filing을 발견하고, `data.sec.gov/submissions` + `companyfacts`로 검증한 뒤 filing 본문을 직접 읽습니다.
- `SSM_SEC_DISCOVERY_MODE=daily-index` — 로컬/self-hosted 전용. EDGAR daily master index를 사용합니다.
- `auto` — daily-index를 먼저 시도하고 403이면 atom으로 자동 fallback합니다.

GitHub-hosted runner에서는 EDGAR daily-index가 403을 반환할 수 있지만, Atom feed, submissions API, companyfacts API, 개별 filing 문서는 정상 접근되는 것을 endpoint probe로 확인했습니다.

```bash
export SSM_SEC_DISCOVERY_MODE=atom
ssm scan --days 7 --out output
```

## 결과 파일

- `output/quality.json`
- `output/candidates.csv`
- `output/dilution_check.csv`
- `output/event_ledger.csv`
- `output/latest.md`

## 수동 Override

SEC filing의 warrant / convert / preferred 구조는 표준 XBRL 태그가 없는 경우가 많기 때문에 완전 자동화가 불가능합니다. 검증된 숫자는 `config/overrides.json`에 기록하고 source/as-of를 남깁니다.

## v0.1 범위

1. SEC recent filing scanner
2. Event proof classifier
3. Conservative dilution parser
4. Hard gate / DATA_HOLD
5. Deterministic research-priority score
6. Existing watchlist recheck

향후 우선순위:

- filing table parser 강화
- warrant strike / exercise cash 자동 추출
- S-1/S-3/424B shelf capacity ledger
- reverse split / Nasdaq deficiency history
- 13D/G / Form 4 strategic validation
- thesis diff / position tracker


## 10-Q / 10-K second pass

신규 후보 발견은 8-K / S-1 / S-3 / 424B / 13D/G / Proxy 등 이벤트성 filing에서 시작합니다.

후보가 잡히면 최신 10-Q 또는 10-K primary document를 별도로 다시 읽어 다음 항목을 2차 검증합니다.

- warrants / pre-funded warrants
- convertible notes / preferred
- ATM / equity line
- stock-based compensation / RSUs
- going concern
- related-party transactions
- subsequent events
- debt / commitments / contingencies
- stockholders' equity

이 2차 검토가 완료되지 않으면 해당 후보는 `DATA_HOLD`를 유지합니다.

이벤트 filing과 10-Q/K에 같은 증권이 반복 기재되는 경우 share equivalents는 단순 합산하지 않고 보수적으로 각 항목의 최대값을 사용해 중복계산을 피합니다.
