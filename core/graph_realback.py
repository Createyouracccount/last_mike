"""
진짜 LangGraph 아키텍처로 리팩토링
- Node: 각 처리 단계를 독립적 함수로
- Tool: 외부 기능을 도구로 분리
- State: 모든 데이터를 중앙 관리
- Edge: 조건부 흐름 제어
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage

from core.state import VictimRecoveryState, create_initial_recovery_state
from config.settings import settings

logger = logging.getLogger(__name__)

# ============================================================================
# TOOLS: 외부 기능들을 도구로 분리
# ============================================================================

@tool
async def emergency_detector_tool(user_input: str) -> Dict[str, Any]:
    """응급 상황 감지 도구"""
    emergency_keywords = ["돈", "송금", "보냈", "이체", "급해", "사기", "당했"]
    time_critical = ["방금", "지금", "분전", "시간전", "오늘"]
    
    urgency = 5
    for keyword in emergency_keywords:
        if keyword in user_input.lower():
            urgency += 3
            break
    
    for keyword in time_critical:
        if keyword in user_input.lower():
            urgency += 2
            break
    
    urgency = min(urgency, 10)
    
    if urgency >= 9:
        response = "🚨 매우 긴급! 즉시 112신고하고 1811-0041번으로 연락하세요!"
    elif urgency >= 8:
        response = "🚨 긴급상황! 지금 132번으로 전화하세요!"
    else:
        response = ""
    
    return {
        "urgency": urgency,
        "emergency_response": response,
        "is_emergency": urgency >= 8
    }

@tool
async def assessment_question_generator_tool(step: int) -> Dict[str, Any]:
    """체크리스트 질문 생성 도구"""
    checklist = [
        "본인이 피해자인가요? 네 또는 아니요로 답해주세요.",
        "지금도 계속 연락이 오고 있나요? 네 또는 아니요로 답해주세요.",
        "돈을 보내셨나요? 네 또는 아니요로 답해주세요.",
        "계좌지급정지 신청하셨나요? 네 또는 아니요로 답해주세요.",
        "112 신고하셨나요? 네 또는 아니요로 답해주세요.",
        "PASS 앱 설치되어 있나요? 네 또는 아니요로 답해주세요."
    ]
    
    if step < len(checklist):
        return {
            "question": checklist[step],
            "step": step,
            "is_complete": False
        }
    else:
        return {
            "question": "",
            "step": step,
            "is_complete": True
        }

@tool
async def assessment_answer_processor_tool(answer: str, step: int, responses: Dict) -> Dict[str, Any]:
    """체크리스트 답변 처리 도구"""
    # 예/아니오 처리
    yes_words = ["네", "예", "응", "맞", "했", "그래", "있"]
    no_words = ["아니", "안", "못", "없", "안했", "싫"]
    
    if any(word in answer.lower() for word in yes_words):
        processed = "yes"
    elif any(word in answer.lower() for word in no_words):
        processed = "no"
    else:
        processed = "unclear"
    
    # 응답 저장
    question_ids = ["victim_status", "immediate_danger", "money_sent", 
                   "account_frozen", "police_report", "pass_app"]
    
    if step < len(question_ids):
        responses[question_ids[step]] = {
            "answer": processed,
            "original": answer
        }
    
    # 즉시 조치 필요 여부
    immediate_action = ""
    if (responses.get("money_sent", {}).get("answer") == "yes" and 
        responses.get("account_frozen", {}).get("answer") == "no"):
        immediate_action = "🚨 긴급! 지금 즉시 은행에 전화해서 계좌지급정지 신청하세요!"
    
    return {
        "processed_answer": processed,
        "immediate_action": immediate_action,
        "next_step": step + 1,
        "responses": responses
    }

@tool
async def gemini_ai_tool(user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Gemini AI 호출 도구"""
    try:
        from services.gemini_assistant import gemini_assistant
        
        if not gemini_assistant.is_enabled:
            return {"response": "", "source": "gemini_disabled"}
        
        result = await asyncio.wait_for(
            gemini_assistant.analyze_and_respond(user_input, context),
            timeout=3.0
        )
        
        return {
            "response": result.get("response", ""),
            "source": "gemini",
            "success": True
        }
        
    except Exception as e:
        logger.warning(f"Gemini 도구 오류: {e}")
        return {"response": "", "source": "gemini_error", "success": False}

@tool
async def rule_based_responder_tool(user_input: str) -> Dict[str, Any]:
    """룰 기반 응답 도구"""
    user_lower = user_input.lower()
    
    patterns = {
        "prevention": {
            "keywords": ["예방", "미리", "설정", "막기"],
            "response": "PASS 앱에서 명의도용방지서비스를 신청하세요."
        },
        "post_damage": {
            "keywords": ["당했", "피해", "사기", "돈", "송금"],
            "response": "즉시 132번으로 신고하고 1811-0041번으로 지원 신청하세요."
        },
        "suspicious": {
            "keywords": ["의심", "이상", "확인", "맞나"],
            "response": "의심스러우면 절대 응답하지 마시고 132번으로 확인하세요."
        }
    }
    
    for pattern_type, data in patterns.items():
        if any(keyword in user_lower for keyword in data["keywords"]):
            return {
                "response": data["response"],
                "pattern": pattern_type,
                "source": "rule_based"
            }
    
    return {
        "response": "상황을 좀 더 구체적으로 말씀해 주시면 더 정확한 도움을 드릴 수 있습니다.",
        "pattern": "default",
        "source": "rule_based"
    }

@tool
async def hybrid_decision_tool(user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """하이브리드 의사결정 도구"""
    try:
        from core.hybrid_decision import SimplifiedHybridDecisionEngine
        
        engine = SimplifiedHybridDecisionEngine(debug=False)
        decision = engine.should_use_gemini(user_input, context)
        
        return {
            "use_gemini": decision.get("use_gemini", False),
            "confidence": decision.get("confidence", 0.0),
            "reasons": decision.get("reasons", [])
        }
    except Exception as e:
        logger.warning(f"하이브리드 결정 오류: {e}")
        return {"use_gemini": False, "confidence": 0.0, "reasons": ["error"]}

@tool
async def tts_delivery_tool(text: str) -> Dict[str, Any]:
    """TTS 전달 도구"""
    try:
        from services.tts_service import tts_service
        from services.audio_manager import audio_manager
        
        if not tts_service.is_enabled:
            logger.info(f"🤖 {text}")
            return {"delivered": True, "method": "console"}
        
        # TTS 스트림 생성
        audio_stream = tts_service.text_to_speech_stream(text)
        
        # 오디오 재생
        await audio_manager.play_audio_stream(audio_stream)
        
        return {"delivered": True, "method": "tts"}
        
    except Exception as e:
        logger.error(f"TTS 전달 오류: {e}")
        # 폴백: 콘솔 출력
        logger.info(f"🤖 {text}")
        return {"delivered": True, "method": "console_fallback"}

# ============================================================================
# NODES: 각 처리 단계를 독립적 함수로
# ============================================================================

async def greeting_node(state: VictimRecoveryState) -> VictimRecoveryState:
    """인사 노드 - 초기 모드 선택 안내"""
    greeting_message = """안녕하세요. 보이스피싱 상담센터입니다.
1번은 피해 상황 체크리스트 (단계별 확인)
2번은 맞춤형 상담 (상황에 맞는 조치)
1번 또는 2번이라고 말씀해주세요."""
    
    # TTS 전달
    await tts_delivery_tool.ainvoke({"text": greeting_message})
    
    # 상태 업데이트
    state["messages"].append(AIMessage(content=greeting_message))
    state["current_step"] = "greeting_complete"
    
    return state

async def mode_detection_node(state: VictimRecoveryState) -> VictimRecoveryState:
    """모드 감지 노드"""
    last_message = state["messages"][-1] if state["messages"] else None
    user_input = last_message.content if isinstance(last_message, HumanMessage) else ""
    
    # 모드 감지
    user_lower = user_input.lower().strip()
    
    if any(pattern in user_lower for pattern in ["1번", "1", "첫번째", "피해", "체크"]):
        detected_mode = "assessment"
    elif any(pattern in user_lower for pattern in ["2번", "2", "두번째", "상담", "대화"]):
        detected_mode = "consultation"
    else:
        detected_mode = "unknown"
    
    state["conversation_mode"] = detected_mode
    state["current_step"] = "mode_detected"
    
    return state

async def emergency_detection_node(state: VictimRecoveryState) -> VictimRecoveryState:
    """응급 상황 감지 노드"""
    last_message = state["messages"][-1] if state["messages"] else None
    user_input = last_message.content if isinstance(last_message, HumanMessage) else ""
    
    # 응급 상황 감지
    emergency_result = await emergency_detector_tool.ainvoke({"user_input": user_input})
    
    state["urgency_level"] = emergency_result["urgency"]
    
    if emergency_result["is_emergency"]:
        # 즉시 응급 응답
        await tts_delivery_tool.ainvoke({"text": emergency_result["emergency_response"]})
        
        state["messages"].append(AIMessage(content=emergency_result["emergency_response"]))
        state["current_step"] = "emergency_handled"
    
    return state

async def assessment_question_node(state: VictimRecoveryState) -> VictimRecoveryState:
    """평가 질문 노드"""
    current_step = state.get("assessment_step", 0)
    
    # 질문 생성
    question_result = await assessment_question_generator_tool.ainvoke({"step": current_step})
    
    if not question_result["is_complete"]:
        question = question_result["question"]
        
        # TTS 전달
        await tts_delivery_tool.ainvoke({"text": question})
        
        # 상태 업데이트
        state["messages"].append(AIMessage(content=question))
        state["current_step"] = "assessment_waiting"
    else:
        # 평가 완료
        state["current_step"] = "assessment_complete"
    
    return state

async def assessment_answer_node(state: VictimRecoveryState) -> VictimRecoveryState:
    """평가 답변 처리 노드"""
    last_message = state["messages"][-1] if state["messages"] else None
    user_input = last_message.content if isinstance(last_message, HumanMessage) else ""
    
    current_step = state.get("assessment_step", 0)
    responses = state.get("assessment_responses", {})
    
    # 답변 처리
    answer_result = await assessment_answer_processor_tool.ainvoke({
        "answer": user_input,
        "step": current_step,
        "responses": responses
    })
    
    # 상태 업데이트
    state["assessment_step"] = answer_result["next_step"]
    state["assessment_responses"] = answer_result["responses"]
    
    # 즉시 조치 필요시
    if answer_result["immediate_action"]:
        await tts_delivery_tool.ainvoke({"text": answer_result["immediate_action"]})
        state["messages"].append(AIMessage(content=answer_result["immediate_action"]))
    
    return state

async def ai_decision_node(state: VictimRecoveryState) -> VictimRecoveryState:
    """AI vs 룰 기반 결정 노드"""
    last_message = state["messages"][-1] if state["messages"] else None
    user_input = last_message.content if isinstance(last_message, HumanMessage) else ""
    
    context = {
        "conversation_turns": state.get("conversation_turns", 0),
        "urgency_level": state.get("urgency_level", 5)
    }
    
    # 하이브리드 결정
    decision = await hybrid_decision_tool.ainvoke({
        "user_input": user_input,
        "context": context
    })
    
    state["use_ai_response"] = decision["use_gemini"]
    state["decision_confidence"] = decision["confidence"]
    
    return state

async def ai_consultation_node(state: VictimRecoveryState) -> VictimRecoveryState:
    """AI 상담 노드"""
    last_message = state["messages"][-1] if state["messages"] else None
    user_input = last_message.content if isinstance(last_message, HumanMessage) else ""
    
    context = {
        "conversation_turns": state.get("conversation_turns", 0),
        "urgency_level": state.get("urgency_level", 5)
    }
    
    # Gemini AI 호출
    ai_result = await gemini_ai_tool.ainvoke({
        "user_input": user_input,
        "context": context
    })
    
    if ai_result["success"] and ai_result["response"]:
        response = ai_result["response"]
    else:
        # AI 실패시 룰 기반으로 폴백
        rule_result = await rule_based_responder_tool.ainvoke({"user_input": user_input})
        response = rule_result["response"]
    
    # 응답 길이 제한
    if len(response) > 80:
        response = response[:77] + "..."
    
    # TTS 전달
    await tts_delivery_tool.ainvoke({"text": response})
    
    # 상태 업데이트
    state["messages"].append(AIMessage(content=response))
    state["current_step"] = "consultation"
    
    return state

async def rule_consultation_node(state: VictimRecoveryState) -> VictimRecoveryState:
    """룰 기반 상담 노드"""
    last_message = state["messages"][-1] if state["messages"] else None
    user_input = last_message.content if isinstance(last_message, HumanMessage) else ""
    
    # 룰 기반 응답
    rule_result = await rule_based_responder_tool.ainvoke({"user_input": user_input})
    response = rule_result["response"]
    
    # TTS 전달
    await tts_delivery_tool.ainvoke({"text": response})
    
    # 상태 업데이트
    state["messages"].append(AIMessage(content=response))
    state["current_step"] = "consultation"
    
    return state

async def conversation_complete_node(state: VictimRecoveryState) -> VictimRecoveryState:
    """대화 완료 노드"""
    farewell = "상담이 완료되었습니다. 추가 도움이 필요하시면 132번으로 연락하세요."
    
    # TTS 전달
    await tts_delivery_tool.ainvoke({"text": farewell})
    
    # 상태 업데이트
    state["messages"].append(AIMessage(content=farewell))
    state["current_step"] = "conversation_complete"
    
    return state

# ============================================================================
# ROUTING FUNCTIONS: 조건부 흐름 제어
# ============================================================================

def route_after_greeting(state: VictimRecoveryState) -> Literal["emergency", "mode_detection"]:
    """인사 후 라우팅"""
    urgency = state.get("urgency_level", 5)
    
    if urgency >= 9:
        return "emergency"
    return "mode_detection"

def route_after_mode_detection(state: VictimRecoveryState) -> Literal["assessment_question", "ai_decision", "greeting"]:
    """모드 감지 후 라우팅"""
    mode = state.get("conversation_mode", "unknown")
    
    if mode == "assessment":
        return "assessment_question"
    elif mode == "consultation":
        return "ai_decision"
    else:
        return "greeting"  # 다시 인사로

def route_after_assessment_question(state: VictimRecoveryState) -> Literal["assessment_answer", "ai_decision"]:
    """평가 질문 후 라우팅"""
    if state.get("current_step") == "assessment_complete":
        return "ai_decision"  # 평가 완료 후 AI로 요약 요청
    return "assessment_answer"

def route_after_assessment_answer(state: VictimRecoveryState) -> Literal["assessment_question", "ai_decision"]:
    """평가 답변 후 라우팅"""
    question_result = assessment_question_generator_tool.invoke({"step": state.get("assessment_step", 0)})
    
    if question_result["is_complete"]:
        return "ai_decision"  # 평가 완료 -> AI 요약
    return "assessment_question"  # 다음 질문

def route_after_ai_decision(state: VictimRecoveryState) -> Literal["ai_consultation", "rule_consultation"]:
    """AI 결정 후 라우팅"""
    if state.get("use_ai_response", False):
        return "ai_consultation"
    return "rule_consultation"

def route_after_consultation(state: VictimRecoveryState) -> Literal["ai_decision", "conversation_complete"]:
    """상담 후 라우팅"""
    turns = state.get("conversation_turns", 0)
    
    if turns >= 10:  # 최대 턴 제한
        return "conversation_complete"
    
    return "ai_decision"  # 다음 대화 턴

# ============================================================================
# MAIN GRAPH: 진짜 LangGraph 구성
# ============================================================================

class ProperLangGraphPhishingSystem:
    """진짜 LangGraph 아키텍처 보이스피싱 상담 시스템"""
    
    def __init__(self, debug: bool = True):
        self.debug = debug
        self.graph = self._build_proper_langgraph()
        
        logger.info("✅ 진짜 LangGraph 아키텍처 시스템 초기화")
    
    def _build_proper_langgraph(self) -> StateGraph:
        """진짜 LangGraph 구성"""
        
        # StateGraph 생성
        workflow = StateGraph(VictimRecoveryState)
        
        # 모든 노드 추가
        workflow.add_node("greeting", greeting_node)
        workflow.add_node("mode_detection", mode_detection_node)
        workflow.add_node("emergency", emergency_detection_node)
        workflow.add_node("assessment_question", assessment_question_node)
        workflow.add_node("assessment_answer", assessment_answer_node)
        workflow.add_node("ai_decision", ai_decision_node)
        workflow.add_node("ai_consultation", ai_consultation_node)
        workflow.add_node("rule_consultation", rule_consultation_node)
        workflow.add_node("conversation_complete", conversation_complete_node)
        
        # 시작점
        workflow.add_edge(START, "greeting")
        
        # 조건부 엣지들
        workflow.add_conditional_edges(
            "greeting",
            route_after_greeting,
            {
                "emergency": "emergency",
                "mode_detection": "mode_detection"
            }
        )
        
        workflow.add_conditional_edges(
            "mode_detection", 
            route_after_mode_detection,
            {
                "assessment_question": "assessment_question",
                "ai_decision": "ai_decision",
                "greeting": "greeting"
            }
        )
        
        workflow.add_conditional_edges(
            "assessment_question",
            route_after_assessment_question,
            {
                "assessment_answer": "assessment_answer",
                "ai_decision": "ai_decision"
            }
        )
        
        workflow.add_conditional_edges(
            "assessment_answer",
            route_after_assessment_answer,
            {
                "assessment_question": "assessment_question",
                "ai_decision": "ai_decision"
            }
        )
        
        workflow.add_conditional_edges(
            "ai_decision",
            route_after_ai_decision,
            {
                "ai_consultation": "ai_consultation",
                "rule_consultation": "rule_consultation"
            }
        )
        
        workflow.add_conditional_edges(
            "ai_consultation",
            route_after_consultation,
            {
                "ai_decision": "ai_decision",
                "conversation_complete": "conversation_complete"
            }
        )
        
        workflow.add_conditional_edges(
            "rule_consultation",
            route_after_consultation,
            {
                "ai_decision": "ai_decision", 
                "conversation_complete": "conversation_complete"
            }
        )
        
        # 응급 및 완료는 종료
        workflow.add_edge("emergency", "conversation_complete")
        workflow.add_edge("conversation_complete", END)
        
        return workflow.compile()
    
    async def process_user_input(self, user_input: str, session_id: str = None) -> str:
        """사용자 입력 처리 - 진짜 LangGraph 방식"""
        
        try:
            # 세션 상태 생성 또는 조회
            if not hasattr(self, '_current_state') or not self._current_state:
                self._current_state = create_initial_recovery_state(
                    session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
            
            # 사용자 메시지 추가
            self._current_state["messages"].append(HumanMessage(content=user_input))
            self._current_state["conversation_turns"] = self._current_state.get("conversation_turns", 0) + 1
            
            if self.debug:
                logger.info(f"🎯 LangGraph 처리: {user_input}")
            
            # LangGraph 실행 (진짜 그래프 사용!)
            result_state = await self.graph.ainvoke(self._current_state)
            
            # 상태 업데이트
            self._current_state = result_state
            
            # 마지막 AI 응답 추출
            ai_messages = [msg for msg in result_state["messages"] if isinstance(msg, AIMessage)]
            last_response = ai_messages[-1].content if ai_messages else "처리 중 오류가 발생했습니다."
            
            if self.debug:
                logger.info(f"✅ LangGraph 응답: {last_response}")
            
            return last_response
            
        except Exception as e:
            logger.error(f"❌ LangGraph 처리 오류: {e}")
            return "일시적 문제가 발생했습니다. 132번으로 연락주세요."
    
    def get_current_state(self) -> VictimRecoveryState:
        """현재 상태 조회"""
        return getattr(self, '_current_state', None)
    
    def reset_conversation(self):
        """대화 리셋"""
        self._current_state = None
        logger.info("🔄 대화 상태 리셋")
    
    async def cleanup(self):
        """정리"""
        if hasattr(self, '_current_state'):
            del self._current_state
        logger.info("🧹 LangGraph 시스템 정리 완료")

# ============================================================================
# 기존 conversation_manager.py와의 통합
# ============================================================================

class LangGraphConversationManager:
    """LangGraph 기반 대화 매니저 - 기존 인터페이스 완벽 호환"""
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        
        # LangGraph 시스템 초기화
        self.ai_brain = ProperLangGraphPhishingSystem(debug=settings.DEBUG)
        
        # 기존 컴포넌트들
        from services.tts_service import tts_service
        from services.audio_manager import audio_manager
        self.tts_service = tts_service
        self.audio_manager = audio_manager
        
        # STT 설정
        self.stt_client = None
        
        # 상태 관리
        self.is_running = False
        self.is_processing = False
        self.initialization_complete = False
        
        # 콜백
        self.callbacks = {}
        
        logger.info("✅ LangGraph 대화 매니저 초기화 완료")
    
    async def initialize(self) -> bool:
        """초기화 (기존 인터페이스 유지)"""
        try:
            # 1. 오디오 초기화
            if not self.audio_manager.initialize_output():
                logger.error("❌ 오디오 초기화 실패")
                return False
            
            # 2. LangGraph AI 두뇌 테스트
            test_response = await self.ai_brain.process_user_input("초기화 테스트")
            if test_response:
                logger.info("✅ LangGraph AI 두뇌 준비 완료")
            
            # 3. STT 클라이언트 생성
            from services.stream_stt import RTZROpenAPIClient
            self.stt_client = RTZROpenAPIClient(self.client_id, self.client_secret)
            
            # 4. 초기 대화 시작 (LangGraph로!)
            await self.ai_brain.start_conversation()
            
            self.initialization_complete = True
            logger.info("🎉 LangGraph 파이프라인 초기화 완료!")
            return True
            
        except Exception as e:
            logger.error(f"❌ LangGraph 초기화 실패: {e}")
            return False
    
    async def start_conversation(self):
        """대화 시작 (기존 인터페이스 + LangGraph)"""
        if not await self.initialize():
            logger.error("❌ LangGraph 시스템 시작 실패")
            return
        
        self.is_running = True
        logger.info("🎙️ LangGraph 음성 대화 시작")
        
        try:
            # STT 입력 시작
            self._start_stt_input_safe()
            
            # 메인 루프 (LangGraph 기반)
            await self._langgraph_main_loop()
            
        except KeyboardInterrupt:
            logger.info("사용자 종료")
        except Exception as e:
            logger.error(f"LangGraph 대화 실행 오류: {e}")
        finally:
            await self.cleanup()
    
    async def _langgraph_main_loop(self):
        """LangGraph 기반 메인 루프"""
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        logger.info("🔄 LangGraph 메인 루프 시작")
        
        while self.is_running:
            try:
                # STT 입력 확인
                user_input = self._get_stt_input()
                
                if user_input and not self.is_processing:
                    logger.info(f"👤 사용자 입력: {user_input}")
                    await self._langgraph_process_input(user_input)
                
                # 대화 완료 확인 (LangGraph 방식)
                if self.ai_brain.is_conversation_complete():
                    logger.info("✅ LangGraph 대화 완료")
                    break
                
                await asyncio.sleep(0.1)
                consecutive_errors = 0
                        
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"LangGraph 루프 오류 ({consecutive_errors}/{max_consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("❌ LangGraph 루프 연속 오류 한계 초과")
                    break
                
                await asyncio.sleep(min(consecutive_errors * 0.5, 3.0))
    
    async def _langgraph_process_input(self, user_input: str):
        """LangGraph 기반 입력 처리"""
        self.is_processing = True
        
        try:
            # 사용자 입력 콜백
            if self.callbacks.get('on_user_speech'):
                self.callbacks['on_user_speech'](user_input)
            
            # LangGraph로 처리! (핵심)
            ai_response = await self.ai_brain.process_user_input(user_input)
            
            if ai_response:
                logger.info(f"🤖 LangGraph 응답: {ai_response}")
                
                # AI 응답 콜백
                if self.callbacks.get('on_ai_response'):
                    self.callbacks['on_ai_response'](ai_response)
                
                # TTS는 이미 LangGraph 내부에서 처리됨!
                # (tts_delivery_tool에서 처리)
            
        except Exception as e:
            logger.error(f"LangGraph 입력 처리 오류: {e}")
            
            # 폴백 응답
            fallback = "일시적 문제가 발생했습니다. 132번으로 연락주세요."
            await self._safe_tts_delivery(fallback)
            
        finally:
            self.is_processing = False
    
    async def _safe_tts_delivery(self, text: str):
        """안전한 TTS 전달 (폴백용)"""
        try:
            if self.tts_service.is_enabled:
                audio_stream = self.tts_service.text_to_speech_stream(text)
                await self.audio_manager.play_audio_stream(audio_stream)
            else:
                print(f"🤖 {text}")
        except Exception as e:
            logger.error(f"폴백 TTS 오류: {e}")
            print(f"🤖 {text}")
    
    def _start_stt_input_safe(self):
        """STT 입력 시작 (기존 방식 유지)"""
        # 기존 STT 로직 그대로 사용
        import threading
        import queue
        
        self.stt_queue = queue.Queue(maxsize=5)
        
        def stt_worker():
            try:
                if self.stt_client:
                    self.stt_client.reset_stream()
                    
                    def transcript_handler(start_time, transcript, is_final=False):
                        if is_final and transcript.alternatives:
                            text = transcript.alternatives[0].text.strip()
                            if text and len(text) > 1:
                                if not self.stt_queue.full():
                                    self.stt_queue.put_nowait(text)
                    
                    self.stt_client.print_transcript = transcript_handler
                    self.stt_client.transcribe_streaming_grpc()
                    
            except Exception as e:
                logger.error(f"STT 워커 오류: {e}")
        
        self.stt_thread = threading.Thread(target=stt_worker, daemon=True)
        self.stt_thread.start()
    
    def _get_stt_input(self) -> str:
        """STT 입력 가져오기"""
        try:
            return self.stt_queue.get_nowait()
        except:
            return None
    
    def set_callbacks(self, **callbacks):
        """콜백 설정 (기존 인터페이스 유지)"""
        self.callbacks.update(callbacks)
    
    def get_conversation_status(self) -> Dict[str, Any]:
        """대화 상태 조회 (기존 + LangGraph 정보)"""
        base_status = {
            "state": "running" if self.is_running else "idle",
            "is_running": self.is_running,
            "is_processing": self.is_processing,
            "initialization_complete": self.initialization_complete,
            "system_type": "langgraph",  # 새로운 플래그
        }
        
        # LangGraph 상태 추가
        if hasattr(self.ai_brain, '_current_state') and self.ai_brain._current_state:
            langgraph_summary = self.ai_brain.get_conversation_summary(self.ai_brain._current_state)
            base_status.update(langgraph_summary)
        
        return base_status
    
    def get_audio_status(self) -> dict:
        """오디오 상태 (기존 방식 유지)"""
        try:
            return self.audio_manager.get_performance_stats()
        except Exception as e:
            return {'error': str(e), 'langgraph_system': True}
    
    async def cleanup(self):
        """정리 (기존 + LangGraph)"""
        logger.info("🧹 LangGraph 시스템 정리 중...")
        
        try:
            self.is_running = False
            
            # LangGraph 정리
            if hasattr(self.ai_brain, 'cleanup'):
                await self.ai_brain.cleanup()
            
            # 기존 컴포넌트 정리
            if hasattr(self, 'stt_thread') and self.stt_thread.is_alive():
                self.stt_thread.join(timeout=3)
            
            if self.audio_manager:
                self.audio_manager.cleanup()
            
            logger.info("✅ LangGraph 시스템 정리 완료")
            
        except Exception as e:
            logger.error(f"LangGraph 정리 오류: {e}")

# ============================================================================
# 기존 코드와의 완벽한 호환성을 위한 별칭
# ============================================================================

# 기존 이름으로 사용 가능
VoiceFriendlyPhishingGraph = ProperLangGraphPhishingSystem
VoiceFriendlyConversationManager = LangGraphConversationManager

# 하위 호환성
OptimizedVoicePhishingGraph = ProperLangGraphPhishingSystem
StructuredVoicePhishingGraph = ProperLangGraphPhishingSystem
ConversationManager = LangGraphConversationManager

async def main():
    """LangGraph 시스템 테스트"""
    
    system = ProperLangGraphPhishingSystem(debug=True)
    
    test_inputs = [
        "안녕하세요",
        "1번",  # 평가 모드
        "네",   # 피해자임
        "아니요", # 연락 안 옴
        "네",   # 돈 보냄
        "아니요", # 계좌정지 안 함 -> 즉시 조치!
        "132번이 뭐예요?"  # 복잡한 질문 -> AI
    ]
    
    for user_input in test_inputs:
        print(f"\n👤 사용자: {user_input}")
        response = await system.process_user_input(user_input)
        print(f"🤖 상담원: {response}")
        
        # 현재 상태 확인
        current_state = system.get_current_state()
        if current_state:
            print(f"📊 상태: {current_state.get('current_step')} | 모드: {current_state.get('conversation_mode')}")
    
    await system.cleanup()

if __name__ == "__main__":
    asyncio.run(main())