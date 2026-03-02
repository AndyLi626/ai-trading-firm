# ADR-009 — 활성 세션 중 Gateway Restart 금지

**상태**: 승인
**날짜**: 2026-03-02
**배경**: Gateway restart 3회 반복으로 세션 단절 + synthetic error 발생

## 근본 원인
Gateway = 세션 관리자. Restart 시 모든 활성 WebSocket 연결 종료 → 현재 대화 세션 강제 종료 → 도구 결과 truncated → synthetic error 삽입

## 규칙
1. **활성 대화 세션 중 `systemctl restart openclaw-gateway` 절대 금지**
2. **`openclaw gateway restart` 절대 금지** (동일 효과)
3. config 변경 후 반영 방법:
   - `openclaw gateway reload` (hot-reload, 세션 유지) — 지원 시 사용
   - 또는: 사람이 직접 재시작 (Boss가 명시적으로 요청)
   - 또는: 다음 자연 재시작까지 대기

## 위반 시 결과
- 세션 단절 → 이미 실행된 작업의 결과 손실
- Gateway restart counter 폭주 (오늘 counter=220+)

## 안전한 config 변경 절차
1. `python3 shared/tools/config_check.py`로 검증
2. 변경 내용 파일에 직접 쓰기 (openclaw.json)
3. **restart 없이** — gateway는 파일 변경을 자동 감지하거나, Boss 재시작 시 반영
4. 즉각 반영이 필요한 경우 Boss에게 요청
