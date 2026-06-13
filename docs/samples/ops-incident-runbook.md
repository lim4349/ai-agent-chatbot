# 운영 런북 요약

이 synthetic 운영 런북은 API 오류율 급증, DB 지연, 백업 복구 기준을 하나의 절차로 정리한다.

## API 오류율 급증 대응

API 오류율이 5%를 넘으면 최근 배포, gateway 로그, upstream timeout을 순서대로 확인한다.
최근 배포가 원인으로 의심되면 배포 owner에게 rollback 가능 여부를 확인하고, 동일 시간대의 5xx 비율을 기록한다.

## DB 지연 대응

DB 지연 알람이 발생하면 slow query, lock wait, connection pool saturation을 확인한다.
읽기 트래픽이 급증한 경우 read replica lag를 함께 확인한다.

## 백업 복구 기준

핵심 운영 DB의 RTO 목표는 30분, RPO 목표는 5분이다.
복구 리허설은 분기마다 1회 수행하고 결과를 운영 점검표에 기록한다.
