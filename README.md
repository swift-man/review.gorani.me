# Mac mini MLX PR Review Webhook

이 저장소는 GitHub webhook을 받아 PR diff를 읽고, MLX로 리뷰한 뒤 GitHub Review API로
라인 코멘트와 전체 리뷰를 등록하는 서버 구성을 담고 있습니다.

## 목표 구조

Mac mini 안의 고정 경로 예시:

```text
/Users/runner/pr-review/
├── deploy/
│   └── nginx-pr-review.conf
├── review_runner/
│   ├── __init__.py
│   ├── review_service.py
│   ├── review_pr.py
│   ├── sample_mlx_client.py
│   ├── webhook_app.py
│   └── requirements.txt
├── scripts/
│   └── run_webhook_server.sh
└── venv/
```

외부 트래픽은 Nginx가 받고, FastAPI 서버는 로컬에서 `/github/webhook`만 처리합니다.

## 1. 전제 조건

Mac mini에서 아래 항목이 준비되어 있어야 합니다.

- Python 3와 `venv`
- Nginx
- GitHub webhook secret
- GitHub Review API를 호출할 토큰
- MLX 실행 커맨드

## 2. 리뷰 스크립트와 venv를 Mac mini에 설치

이 저장소 내용을 Mac mini에서 한 번 받아둔 뒤 아래처럼 고정 경로에 설치합니다.

```bash
./scripts/install_local_review.sh /Users/runner/pr-review
```

그 뒤 아래 환경 변수를 설정합니다.

- `LOCAL_REVIEW_HOME=/Users/runner/pr-review`
- `GITHUB_TOKEN=...`
- `GITHUB_WEBHOOK_SECRET=...`
- `MLX_REVIEW_CMD=/Users/runner/pr-review/venv/bin/python -m review_runner.sample_mlx_client`
- `GITHUB_API_URL=https://api.github.com` (옵션)

실전에서는 `sample_mlx_client.py` 대신 실제 MLX 실행 어댑터로 교체하면 됩니다.

## 3. FastAPI 서버 실행

```bash
export LOCAL_REVIEW_HOME=/Users/runner/pr-review
export GITHUB_TOKEN=ghp_xxx
export GITHUB_WEBHOOK_SECRET=replace-me
export MLX_REVIEW_CMD="/Users/runner/pr-review/venv/bin/python -m review_runner.sample_mlx_client"
zsh /Users/runner/pr-review/scripts/run_webhook_server.sh
```

FastAPI 앱 엔트리포인트는 [`review_runner/webhook_app.py`](/Users/m4_25/develop/codereview/review_runner/webhook_app.py)입니다.

## 4. Nginx 프록시

샘플 설정은 [`deploy/nginx-pr-review.conf`](/Users/m4_25/develop/codereview/deploy/nginx-pr-review.conf)에 있습니다.
`/github/webhook`와 `/healthz`만 FastAPI로 프록시하면 됩니다.

## 5. 웹훅 처리 흐름

[`review_runner/webhook_app.py`](/Users/m4_25/develop/codereview/review_runner/webhook_app.py)와 [`review_runner/review_service.py`](/Users/m4_25/develop/codereview/review_runner/review_service.py)는 다음을 수행합니다.

1. `POST /github/webhook` 수신
2. `X-Hub-Signature-256` 서명 검증
3. `pull_request` 이벤트와 허용 액션만 통과
4. GitHub API `pulls/{number}/files`로 파일 목록과 patch 조회
5. patch를 MLX 프롬프트 JSON으로 직렬화
6. MLX JSON 응답 검증
7. GitHub Review API payload로 변환
8. 라인 코멘트와 전체 리뷰를 한 번에 등록

## 6. CLI 테스트

기존 CLI 테스트도 유지됩니다. [`review_runner/review_pr.py`](/Users/m4_25/develop/codereview/review_runner/review_pr.py)는 다음을 수행합니다.

1. `GITHUB_EVENT_PATH`에서 PR 번호를 읽음
2. GitHub API `pulls/{number}/files`로 파일 목록과 patch를 읽음
3. 각 파일의 RIGHT-side comment 가능 라인을 계산함
4. patch를 MLX 프롬프트 JSON으로 직렬화함
5. MLX JSON 응답을 검증함
6. GitHub Review API payload로 변환함
7. 라인 코멘트와 전체 리뷰를 한 번에 등록함

## 7. MLX 어댑터 교체 포인트

[`review_runner/sample_mlx_client.py`](/Users/m4_25/develop/codereview/review_runner/sample_mlx_client.py)는 스텁입니다.
실제 사용 시 stdin으로 받은 프롬프트를 MLX 모델에 넘기고, 아래 JSON 형식으로 stdout에 출력하세요.

```json
{
  "summary": "The diff introduces one likely regression.",
  "event": "REQUEST_CHANGES",
  "comments": [
    {
      "path": "src/app.py",
      "line": 42,
      "body": "This branch now skips the None check and can raise an exception."
    }
  ]
}
```

`line`은 반드시 해당 patch의 RIGHT-side 유효 라인이어야 합니다.

## 8. GitHub Webhook 설정

GitHub 저장소 Settings -> Webhooks에서 아래처럼 연결하면 됩니다.

- Payload URL: `https://your-domain.example/github/webhook`
- Content type: `application/json`
- Secret: `GITHUB_WEBHOOK_SECRET`와 같은 값
- Events: `Pull requests`

## 9. 로컬 dry run

```bash
export GITHUB_TOKEN=ghp_xxx
export GITHUB_REPOSITORY=OWNER/REPO
export GITHUB_EVENT_PATH=/path/to/event.json
export MLX_REVIEW_CMD="/Users/runner/pr-review/venv/bin/python -m review_runner.sample_mlx_client"
export DRY_RUN=1
export PYTHONPATH=/Users/runner/pr-review
/Users/runner/pr-review/venv/bin/python -m review_runner.review_pr
```

# pr.review.gorani.me
