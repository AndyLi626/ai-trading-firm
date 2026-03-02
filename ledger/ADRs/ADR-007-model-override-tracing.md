# ADR-007 — 모델 오버라이드 추적 규칙

**상태**: 승인  
**날짜**: 2026-03-02  
**배경**: audit-daily가 설정(gemini-2.0-flash) 대신 이전 모델(claude-haiku-4-5)을 사용함

## 근본 원인
Gateway가 재시작되지 않으면 새 openclaw.json 설정이 실행 중인 cron에 반영되지 않음.
모델 변경 후 gateway reload를 하지 않으면 stale 캐시로 이전 모델이 사용됨.

## 규칙
1. **모델 변경 → 즉시 gateway reload** 필수
2. **모델 변경은 CHANGELOG.md에 기록** (변경 전 모델, 변경 후 모델, 이유)
3. **다음 cron 실행에서 model= 필드를 반드시 verify** (runs/ 파일에서 실증)
4. **불일치 발견 시 ticketify()로 즉시 티켓 생성**

## 검증 방법
```bash
# runs/ 디렉터리에서 실제 사용 모델 확인
python3 -c "
import json, os
runs = '/home/lishopping913/.openclaw/cron/runs'
d    = json.load(open('/home/lishopping913/.openclaw/cron/jobs.json'))
for j in d['jobs']:
    rf = f'{runs}/{j[\"id\"]}.jsonl'
    if not os.path.exists(rf): continue
    fins = [json.loads(l) for l in open(rf) if '\"finished\"' in l]
    if fins: print(j['name'], fins[-1].get('model','?'))
"
```
