# 프로젝트 이름: Python Agents SDK 워크플로 Trace 실습
# 설명: 주문 상담과 답변 검토 등의 2개 에이전트를 순차 실행하고 하나의 trace로 기록
# 작성자: 서진호
# 버전: v1.0
# 실행 예시: python main.py --prompt "DEMO-1001 주문의 배송 상태를 알려줘."
# 설정 확인: python main.py --check

import argparse
import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

# 실행 위치와 관계없이 소스 파일 옆의 .env를 찾기 위한 기준 폴더
ROOT = Path(__file__).resolve().parent

# trace 확인 주소와 대시보드에 표시할 워크플로 명
DASHBOARD = "https://platform.openai.com/logs?api=traces"
WORKFLOW = "Python 주문 상담 워크플로"


def settings() -> tuple[str, str]:
    # API 키와 모델 설정을 검사하고 (키, 모델) 튜플을 반환하고 
    # 이미 설정된 셸 환경 변수는 로컬 .env 값보다 우선함 
    load_dotenv(ROOT / ".env", override=False)

    # 설정 값의 앞뒤 공백을 제거하고 모델이 설정되지 않았으면 기본값을 사용함 
    key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()

    # 빈 키, 예제용 키, 빈 모델, tracing 비활성화 설정은 실행 전에 거부함 
    if not key or key == "your_api_key_here":
        raise ValueError("기존 API 키를 .env의 OPENAI_API_KEY 또는 환경 변수에 설정하세요.")
    if not model:
        raise ValueError("OPENAI_MODEL이 비어 있습니다.")
    if os.getenv("OPENAI_AGENTS_DISABLE_TRACING", "").lower() in {"1", "true"}:
        raise ValueError("trace 실습을 위해 OPENAI_AGENTS_DISABLE_TRACING 설정을 해제하세요.")
    return key, model


async def workflow(key: str, model: str, prompt: str) -> None:
    # 상담 → 답변 검토를 비동기로 실행하고 trace 내보내기를 요청함 
    # 실제 실행에 필요한 SDK는 여기서 불러와 --check에서는 사용하지 않음 
    from openai import AsyncOpenAI
    from agents import (
        Agent, Runner, RunConfig, custom_span, function_tool,
        gen_trace_id, set_default_openai_client,
        set_tracing_export_api_key, trace,
    )
    from agents.tracing import get_trace_provider

    @function_tool
    def lookup_order(order_id: str) -> str:
        """Look up a demo order by order ID, such as DEMO-1001."""
        # 에이전트가 호출할 함수 도구입니다. 외부 시스템 없이 가상 주문을 조회함 
        # 주문 ID는 대소문자를 구분하지 않고 비교함 
        if order_id.upper() == "DEMO-1001":
            return "DEMO-1001: 배송 중. 예상 도착: 주문 후 3영업일. 상품: 데모 키보드."
        return "데모 데이터에 해당 주문이 없습니다. 사용 가능한 주문: DEMO-1001."

    # 실행마다 고유한 trace ID와 그룹 ID를 생성함 
    trace_id = gen_trace_id()
    run_group = f"demo_{uuid4().hex}"

    # 요청 제한 시간은 60초이며 자동 재시도는 하지 않음 
    client = AsyncOpenAI(api_key=key, timeout=60.0, max_retries=0)

    # 에이전트의 모델 요청과 trace 전송에 사용할 클라이언트 및 키를 설정함 
    set_default_openai_client(client)
    set_tracing_export_api_key(key)
    
    # trace를 활성화하고 모델·도구의 입력/출력을 포함하고 실습에는 샘플 질문과 가상 주문 데이터를 사용함
    config = RunConfig(tracing_disabled=False, trace_include_sensitive_data=True)

    # 상담 에이전트는 주문 조회 도구를 사용하고 도구가 반환한 사실로 답함 
    support = Agent(
        name="주문 상담 에이전트", model=model, tools=[lookup_order],
        instructions=("한국어로 짧게 답하세요. 주문 상태 질문에는 반드시 lookup_order 도구를 "
                      "사용하세요. 도구가 반환한 데모 데이터만 사실로 사용하세요."),
    )

    # 검토 에이전트는 다음 단계에서 상담 답변과 데모 근거를 비교함 
    reviewer = Agent(
        name="답변 검토 에이전트", model=model,
        instructions="상담 답변이 제공된 근거와 일치하는지 검토하고 한국어로 짧게 결과를 쓰세요.",
    )

    # 대시보드에서 이번 실행을 찾을 수 있도록 이름과 trace ID를 먼저 출력함 
    print(f"워크플로: {WORKFLOW}\nTrace ID: {trace_id}\nLogs: {DASHBOARD}")
    try:
        # 바깥 trace 컨텍스트가 입력 준비와 두 에이전트 실행을 하나로 묶음 
        with trace(WORKFLOW, trace_id=trace_id, group_id=run_group,
                   metadata={"demo": "agents-sdk-trace", "language": "python"}):
            
            # 입력 정리 과정을 별도 span으로 기록하고 빈 질문을 검사함 
            with custom_span("입력 준비", data={"demo_order_id": "DEMO-1001"}):
                prepared = prompt.strip()
                if not prepared:
                    raise ValueError("질문을 입력하세요.")
                
            # 먼저 상담을 실행하고 모델과 도구 호출을 포함해 최대 5턴을 허용함 
            answer = await Runner.run(support, prepared, run_config=config, max_turns=5)

            # 상담 결과와 고정된 데모 근거를 검토 에이전트에 전달함(최대 3턴).
            review = await Runner.run(
                reviewer,
                f"사용자 질문: {prepared}\n상담 답변: {answer.final_output}\n"
                "데모 근거: DEMO-1001은 배송 중, 예상 도착은 주문 후 3영업일, 상품은 데모 키보드.",
                run_config=config, max_turns=3,
            )

            # 두 에이전트의 최종 출력을 콘솔에 표시함 
            print(f"\n상담 답변:\n{answer.final_output}\n\n검토 결과:\n{review.final_output}")
    finally:
        # 에이전트 실행이 실패해도 trace 컨텍스트 종료 후 내보내기를 요청함 
        # 동기 flush는 별도 스레드에서 실행해 이벤트 루프를 막지 않음 
        # 내보내기 요청은 대시보드 수신 성공을 보장하지 않음 
        await asyncio.to_thread(get_trace_provider().force_flush)

        # 비동기 API 클라이언트의 연결 자원을 정리함 
        await client.close()
        print("\ntrace 내보내기를 요청했습니다. 같은 API 프로젝트의 Agents SDK 탭에서 확인하세요.")


def main() -> int:
    # 명령줄 처리, 설정 검사, 비동기 워크플로 실행을 담당하는 진입 함수
    # 정상 종료는 0, 설정 또는 실행 오류는 1을 반환함 

    # --check는 설정만 확인하고, --prompt는 상담 질문을 지정함 
    parser = argparse.ArgumentParser(description="Agents SDK 워크플로 trace 실습")
    parser.add_argument("--check", action="store_true", help="API 호출 없이 설정 확인")
    parser.add_argument("--prompt", default="DEMO-1001 주문의 배송 상태를 알려줘.")
    args = parser.parse_args()
    try:
        # API 요청 전에 키·모델·tracing 설정을 확인함 
        key, model = settings()
        if args.check:
            # 키 값은 숨기며 API 호출이나 인증·권한 검증 없이 종료함 
            print(f"API 키: 설정됨 (값 숨김)\n모델: {model}\nLogs: {DASHBOARD}")
            print("설정만 확인했습니다. 키 유효성 및 API 권한은 확인하지 않았습니다.")
            return 0
        # 이벤트 루프를 만들어 비동기 워크플로가 끝날 때까지 실행함 
        asyncio.run(workflow(key, model, args.prompt))
        return 0
    except Exception as exc:
        # 예외 유형과 안내를 표준 오류로 출력하고 원본 API 예외 메시지, 헤더, 인증 정보는 출력하지 않음 
        print(f"실행 실패: {type(exc).__name__}. .env, API 권한, 네트워크와 Logs를 확인하세요.", file=sys.stderr)
        if isinstance(exc, ValueError):
            # 설정·입력 검사에서 발생한 ValueError는 구체적인 메시지도 안내함 
            print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    # 직접 실행할 때만 main을 호출하고 반환값을 프로세스 종료 코드로 사용함 
    raise SystemExit(main())
