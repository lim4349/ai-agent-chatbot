# 프로젝트 학습 사항 (Lessons Learned)

> PR 리뷰 및 개발 과정에서 발견된 문제점과 해결책을 기록하여 반복적인 실수를 방지합니다.
> 이 문서는 Claude Code Review에 의해 자동 업데이트됩니다.

---

## 목차

- [CI/CD](#cicd)
- [Backend](#backend)
- [Frontend](#frontend)
- [Security](#security)
- [Performance](#performance)

---

## CI/CD

### Git Flow 브랜칭
**문제**: main 브랜치에 직접 PR을 병합하여 배포되는 혼란
**해결책**:
- `feat/xxx` → `dev` (CI만 실행)
- `dev` → `main` (CI + CD 실행)
- main에 직접 push 금지 (브랜치 보호 규칙)

**관련 커밋**: `47143a6`

---

## Backend

### Python DI 컨테이너
**문제**: Factory 함수를 클래스보다 뒤에 정의하여 NameError 발생
**해결책**: 모든 `_create_*` 함수를 클래스 정의 전에 배치

```python
# ❌ 잘못된 순서
class DIContainer:
    llm = providers.Singleton(_create_llm)  # NameError!

def _create_llm(config): ...

# ✅ 올바른 순서
def _create_llm(config): ...

class DIContainer:
    llm = providers.Singleton(_create_llm)
```

**관련 파일**: `backend/src/core/di_container.py`

### YAML 문법
**문제**: 중복된 `push` 키로 인한 YAML 파싱 오류
**해결책**: 같은 키는 한 번만 정의, 브랜치 목록으로 관리

```yaml
# ❌ 잘못됨
push:
  branches: [dev]
push:
  branches: [main]

# ✅ 올바름
push:
  branches: [dev, main]
```

---

## Frontend

### 환경 변수
**문제**: `NEXT_PUBLIC_API_URL`을 Secret으로 설정하려 했음
**해결책**: `NEXT_PUBLIC_*` 변수는 Plaintext로 설정 (빌드 타임에 필요)

**관련 설정**: Vercel Dashboard → Environment Variables → Plaintext

---

## Security

### API Key 관리
**문제**: GitHub에 API key를 커밋하려는 시도
**해결책**:
- 모든 API key는 GitHub Secrets에 저장
- `.env.example`에는 dummy 값만 포함
- Render/Vercel 대시보드에서 직접 설정

**필수 Secrets**:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY` (GLM-5 사용 시)
- `TAVILY_API_KEY`

---

## Performance

### ChromaDB 외부 저장소
**문제**: `render.yaml`에서 외부 GitHub 저장소 참조 시 빌드 실패
**해결책**: Blueprint에서 제거하고 수동 설정 가이드 제공

**관련 파일**: `render.yaml`

---

## 자동 업데이트 로그

| 날짜 | PR | 학습 사항 |
|------|-----|----------|
| 2025-02-15 | #1 | Git Flow CI/CD 구성, Claude Code Review 추가 |

---

*마지막 업데이트: 2025-02-15*
*자동 생성: Claude Code Review*
