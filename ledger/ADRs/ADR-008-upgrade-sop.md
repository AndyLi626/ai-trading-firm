# ADR-008 — OpenClaw 업그레이드 SOP

**상태**: 승인  
**날짜**: 2026-03-02  
**배경**: 2026-03-02 감사에서 CLI(2026.2.26) vs Gateway(2026.2.26) vs user-level(2026.3.1) 버전 분열 발견.
서비스가 구버전을 계속 사용하는 "반쪽 업그레이드" 상태 방지를 위해 SOP 필수.

---

## Phase 1 — Upgrade Proposal (제안)

InfraBot이 제안 파일 작성: `memory/proposals/upgrade_<ver>_<date>.md`

필수 포함 항목:
```
target_version: 2026.X.Y
current_version: 2026.A.B
change_scope: CLI / gateway / cron runner / skills
risk:
  - config format 변경 여부 (package.json changelog 확인)
  - plugins/skills 호환성
  - PATH 충돌 가능성 (system vs user-level)
rollback:
  - 이전 서비스 파일 백업 경로: ~/.config/systemd/user/openclaw-gateway.service.bak_<ver>
  - 이전 npm 패키지: npm install -g openclaw@<prev_ver>
  - gateway restart → 이전 버전 재기동
```

---

## Phase 2 — Preflight (업그레이드 전 필수 검사)

```bash
python3 shared/scripts/e2e_smoke.py --dry-run   # 6/6 PASS 필수
python3 shared/scripts/arch_lock.py check        # drift=0 필수
python3 shared/scripts/check_budget_status.py   # budget_mode != stop
python3 -c "import json; \
  hb=json.load(open('memory/infra_ticket_poller_heartbeat.json')); \
  print('heartbeat:', hb['status'])"             # status=alive
```

**하나라도 실패 시 업그레이드 중단.**

---

## Phase 3 — Apply (실행)

```bash
# 1. config freeze (봇이 live config 쓰기 금지)
touch /tmp/openclaw_config_freeze

# 2. 서비스 파일 백업
cp ~/.config/systemd/user/openclaw-gateway.service \
   ~/.config/systemd/user/openclaw-gateway.service.bak_$(openclaw --version)

# 3. 업그레이드 (user-level source of truth)
npm install -g openclaw@<target_ver>
sudo npm install -g openclaw@<target_ver>   # system-level 동기화

# 4. 서비스 파일 ExecStart + Description 갱신
sed -i "s|/usr/lib/node_modules|$HOME/.npm-global/lib/node_modules|g" \
  ~/.config/systemd/user/openclaw-gateway.service
sed -i "s|v[0-9]*\.[0-9]*\.[0-9]*|v<target_ver>|g" \
  ~/.config/systemd/user/openclaw-gateway.service

# 5. OPENCLAW_SERVICE_VERSION 환경변수 갱신
sed -i "s|OPENCLAW_SERVICE_VERSION=.*|OPENCLAW_SERVICE_VERSION=<target_ver>|" \
  ~/.config/systemd/user/openclaw-gateway.service

# 6. meta 갱신
python3 -c "
import json,datetime,pathlib
p = pathlib.Path('/home/lishopping913/.openclaw/openclaw.json')
d = json.load(open(p))
d['meta']['lastTouchedVersion'] = '<target_ver>'
d['meta']['lastTouchedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump(d, open(p,'w'), indent=2)
"

# 7. reload + restart (ADR-007 준수)
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
sleep 5

# 8. Telegram 1건 상태 통지 (1건만)
openclaw send --to 1555430296 --channel telegram \
  "⬆️ Upgrade applied: openclaw <target_ver> | gateway restart OK | verify 진행 중"
```

---

## Phase 4 — Verify (검증)

```bash
# 버전 일관성 4-way 확인
which openclaw && openclaw --version
~/.npm-global/bin/openclaw --version
node -e "require('/usr/lib/node_modules/openclaw/package.json').version" | xargs echo system:
systemctl --user show openclaw-gateway.service --property=Description

# E2E smoke
python3 shared/scripts/e2e_smoke.py  # 6/6 PASS 필수

# Healthcheck
python3 shared/scripts/healthcheck.py  # 7/7 PASS 필수

# config freeze 해제 (검증 통과 후에만)
rm -f /tmp/openclaw_config_freeze
```

**검증 통과 조건: 4-way 버전 일치 + smoke 6/6 + healthcheck 7/7**

---

## Phase 5 — Rollback (실패 시)

```bash
# 1. 이전 버전 재설치
npm install -g openclaw@<prev_ver>
sudo npm install -g openclaw@<prev_ver>

# 2. 서비스 파일 복원
cp ~/.config/systemd/user/openclaw-gateway.service.bak_<prev_ver> \
   ~/.config/systemd/user/openclaw-gateway.service

# 3. reload + restart
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service

# 4. incident 작성 (경량 postmortem)
# memory/incident_upgrade_fail_<date>.md:
#   시도 버전, 실패 원인, 롤백 시각, 영향 범위

# 5. Telegram 1건 통지
openclaw send --to 1555430296 --channel telegram \
  "⚠️ Upgrade rollback: 복원 → <prev_ver> | 원인: <reason>"
```

---

## Phase 6 — 자동화 전략 (주 1회 체크, 수동 업그레이드)

**원칙**: 자동 업그레이드 금지. 체크만 자동, 실행은 Boss 승인.

```json
{
  "check_cron": "매주 월요일 09:00 UTC",
  "action": "버전 체크만 — 새 버전 있으면 proposal 파일 생성",
  "upgrade_window": "UTC 08:00–10:00 (거래 시간 외)",
  "version_policy": "stable tag만 추종 (latest 금지)",
  "auto_execute": false,
  "boss_approval_required": true
}
```

주간 체크 스크립트 위치: `shared/scripts/upgrade_check.py`

---

## 적용 기록

| 날짜 | 이전 버전 | 적용 버전 | 방식 | 결과 |
|------|---------|---------|------|------|
| 2026-03-02 | 2026.2.26 (service) | 2026.3.1 | 수동 (감사 후 즉시) | PASS |

