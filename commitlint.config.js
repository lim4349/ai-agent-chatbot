module.exports = {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "type-enum": [
      2,
      "always",
      [
        "feat", // 새로운 기능
        "fix", // 버그 수정
        "docs", // 문서 변경
        "style", // 코드 스타일 변경
        "refactor", // 리팩토링
        "test", // 테스트 추가/수정
        "chore", // 빌드 과정이나 보조 도구 변경
        "build", // 빌드 시스템 변경
        "ci", // CI 설정 변경
        "perf", // 성능 개선
        "revert", // 이전 커밋 되돌리기
        "release", // 릴리즈
      ],
    ],
    "subject-case": [2, "never", ["start-case", "pascal-case", "upper-case"]],
    "subject-max-length": [2, "always", 72],
    "subject-min-length": [2, "always", 3],
  },
};
