# Python Agents SDK 워크플로 Trace 실습

[openai-logs-demo](https://github.com/synabreu/openai-logs-demo)의 간단한 Python 실습 형식을 참고한 새 프로젝트입니다. 원본은 Responses 요청 로그를 확인합니다. 이 프로젝트는 Agents SDK로 두 에이전트를 실행하고 **Logs → Agents SDK**에서 하나의 워크플로 trace를 확인합니다.

Python 3.10 이상을 사용하세요. 기존 API 키를 사용하며, 실제 키는 프로젝트에 포함되어 있지 않습니다.

## 1. 설치

main.py가 있는 폴더에서 PowerShell을 열고 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`python` 대신 `py`만 동작하면 첫 명령의 `python`을 `py`로 바꾸세요. 가상환경 활성화 없이 실행할 수 있어 PowerShell 실행 정책 변경이 필요 없습니다.

## 2. OpenAI API Key 설정

```powershell
Copy-Item .env.example .env
notepad .env
```

여러분의 OpenAI API 키를 `your_api_key_here`에 넣어주세요. 

```dotenv
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

셸에 OPENAI_API_KEY가 설정되어 있으면 해당 값이 .env보다 우선합니다. .env는 main.py와 같은 폴더에서 읽습니다. 모델은 프로젝트에서 사용 가능한 모델로 변경할 수 있습니다. 실제 실행에는 API 사용 요금이 발생합니다.

## 3. 설정 확인 — API 호출 없음

```powershell
.\.venv\Scripts\python.exe main.py --check
```

키 값을 출력하지 않습니다. 키의 유효성, 결제 상태, 모델 권한, trace 전송 성공을 검증하는 명령은 아닙니다.

## 4. 워크플로 실행

```powershell
.\.venv\Scripts\python.exe main.py
# 다른 질문
.\.venv\Scripts\python.exe main.py --prompt "DEMO-1001은 언제 도착하나요?"
```

기본 질문에서 기대하는 trace 구조는 다음과 같습니다. 모델 판단에 따라 모델 호출 수는 달라질 수 있습니다.

```text
Python 주문 상담 워크플로 (trace_...)
├── 입력 준비 (custom span)
├── 주문 상담 에이전트
│   ├── 모델 호출
│   ├── lookup_order (function tool)
│   └── 모델 호출 / 상담 답변
└── 답변 검토 에이전트
    └── 모델 호출 / 검토 결과
```

주문 정보는 코드에 정의한 가상 데이터입니다. 외부 주문 시스템에는 연결하지 않습니다. 두 Runner.run()을 바깥쪽 trace()로 묶으므로 하나의 워크플로로 기록합니다. 검토는 명시적인 순차 실행이며 handoff 예제는 아닙니다.

## 5. Agents SDK 탭 확인

1. [Platform Logs](https://platform.openai.com/logs?api=traces)를 엽니다.
2. 기존 API 키가 속한 조직·프로젝트를 선택합니다.
3. **Agents SDK** 탭에서 `Python 주문 상담 워크플로` 또는 터미널의 `trace_...` ID를 찾아봅니다.
4. trace를 열고 모델 입력·출력, 도구 호출·결과, 실행 시간과 오류를 확인합니다.

SDK가 trace를 생성하고 전송합니다. `print()`는 콘솔 출력용이며, `store=True`로 Responses를 저장하는 것과는 별도의 tracing 경로입니다. 종료 시 trace 컨텍스트를 닫은 뒤 force_flush()로 내보내기를 요청합니다. 이 메시지만으로 대시보드 저장 성공이 확인되는 것은 아닙니다. 전송 오류는 SDK 로그를 확인하세요.

이 실습은 입력·출력 내용을 trace에 포함합니다(`trace_include_sensitive_data=True`). 샘플 질문과 가상 주문 데이터로 실습하세요. 이를 False로 바꾸면 해당 모델·도구 입력/출력 기록을 줄일 수 있으나 custom span에 직접 넣은 데이터까지 자동 제거하지는 않습니다.

## 문제 해결

| 증상 | 확인 사항 |
|---|---|
| 모듈을 찾을 수 없음 | 가상환경 Python으로 requirements.txt 설치 |
| 키 설정 오류 | .env.txt가 아닌 .env인지, 샘플 값을 바꿨는지 확인 |
| 인증·한도·모델 오류 | 키 유효성, API 결제, 프로젝트 모델 권한 확인 |
| trace가 나타나지 않음 | Agents SDK 탭, 조직·프로젝트, 날짜 필터, 전송 지연, 네트워크 확인 |
| tracing 비활성화 | OPENAI_AGENTS_DISABLE_TRACING 설정 해제 |
| 조직의 데이터 정책 제한 | Zero Data Retention 등 조직 정책에 따라 tracing을 사용할 수 없을 수 있음 |

자동 재시도는 끄고 요청 제한 시간은 60초로 설정했습니다. 네트워크 오류 뒤 재실행하면 새 실행이 생성되므로 먼저 Logs를 확인하세요.

## macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
# 편집기로 .env에 기존 키를 설정
.venv/bin/python main.py --check
.venv/bin/python main.py
```

## 공식 문서

- [Agents SDK](https://developers.openai.com/api/docs/guides/agents/sdk)
- [워크플로 tracing](https://developers.openai.com/api/docs/guides/agents/integrations-observability#tracing)
