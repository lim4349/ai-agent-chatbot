# DB 성능 진단 리포트

## 성능 목표

| Metric | Target | First Check |
|---|---:|---|
| p95 latency | 120ms 이하 | slow query |
| lock wait | 50ms 이하 | transaction scope |
| connection usage | 80% 이하 | pool sizing |

p95 latency 목표는 120ms 이하이며 초과 시 slow query와 lock wait를 점검한다.

## 권장 조치

쿼리 플랜이 불안정하면 통계 정보를 갱신하고, 반복되는 full scan은 인덱스 후보로 기록한다.
