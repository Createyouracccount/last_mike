"""
음성 친화적 보이스피싱 상담 시스템 - SOLID 원칙 적용 리팩토링
- 단일 책임 원칙: 각 클래스가 하나의 책임만 가짐
- 개방-폐쇄 원칙: 확장에는 열려있고 수정에는 닫혀있음
- 리스코프 치환 원칙: 상위 타입을 하위 타입으로 치환 가능
- 인터페이스 분리 원칙: 클라이언트가 사용하지 않는 인터페이스에 의존하지 않음
- 의존 역전 원칙: 추상화에 의존하고 구체화에 의존하지 않음
"""

import sys
import os
from datetime import datetime
from typing import Literal, Dict, Any, List, Optional, Protocol
import asyncio
import re
import logging
from abc import ABC, abstractmethod

# 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from langgraph.graph import StateGraph, START, END

# 수정
# from core.state import VictimRecoveryState, create_initial_recovery_state
# from core.hybrid_decision import SimplifiedHybridDecisionEngine

from .state import VictimRecoveryState, create_initial_recovery_state
from .hybrid_decision import SimplifiedHybridDecisionEngine

logger = logging.getLogger(__name__)

# ============================================================================
# 인터페이스 정의 (SOLID - 인터페이스 분리 원칙)
# ============================================================================

class IConversationStrategy(Protocol):
    """대화 전략 인터페이스"""
    async def process_input(self, user_input: str, context: Dict[str, Any]) -> str:
        """사용자 입력 처리"""
        ...
    
    def is_complete(self) -> bool:
        """완료 여부"""
        ...

class IDamageAssessment(Protocol):
    """피해 평가 인터페이스"""
    def get_next_question(self) -> str:
        """다음 질문 반환"""
        ...
    
    def process_answer(self, answer: str) -> str:
        """답변 처리"""
        ...

class IEmergencyHandler(Protocol):
    """응급 처리 인터페이스"""
    def detect_emergency(self, text: str) -> int:
        """응급도 감지 (1-10)"""
        ...
    
    def get_emergency_response(self, urgency: int) -> str:
        """응급 응답 반환"""
        ...

# ============================================================================
# 피해 평가 시스템 (단일 책임 원칙)
# ============================================================================

class VictimInfoAssessment:
    """피해자 정보 체계적 평가 시스템"""
    
    def __init__(self):
        # 체계적 질문 체크리스트
        self.checklist = [
            {
                "id": "victim_status",
                "question": "본인이 피해자인가요? 네 또는 아니요로 답해주세요.",
                "type": "yes_no",
                "critical": True
            },
            {
                "id": "immediate_danger",
                "question": "지금도 계속 연락이 오고 있나요? 네 또는 아니요로 답해주세요.",
                "type": "yes_no",
                "critical": True
            },
            {
                "id": "money_sent",
                "question": "돈을 보내셨나요? 네 또는 아니요로 답해주세요.",
                "type": "yes_no",
                "critical": True
            },
            {
                "id": "account_frozen",
                "question": "계좌지급정지 신청하셨나요? 네 또는 아니요로 답해주세요.",
                "type": "yes_no",
                "urgent_if_no": True
            },
            {
                "id": "police_report",
                "question": "112 신고하셨나요? 네 또는 아니요로 답해주세요.",
                "type": "yes_no",
                "urgent_if_no": True
            },
            
            {
                "id": "pass_app",
                "question": "패스(PASS) 앱 설치되어 있나요? 네 또는 아니요로 답해주세요.",
                "type": "yes_no",
                "action_needed": True
            }
        ]
        
        self.current_step = 0
        self.responses = {}
        self.urgent_actions = []

        self.immediate_action_delivered = False
        
    def get_next_question(self) -> str:
        """다음 질문 반환"""
        if self.current_step >= len(self.checklist):
            return self._generate_final_assessment()
        
        question_data = self.checklist[self.current_step]
        return question_data["question"]
    
    def process_answer(self, answer: str) -> str:
        """답변 처리"""
        if self.current_step >= len(self.checklist):
            return "평가가 완료되었습니다."
        
        current_q = self.checklist[self.current_step]
        processed = self._process_yes_no(answer)
        
        # 답변 기록
        self.responses[current_q["id"]] = {
            "answer": processed,
            "original": answer
        }
        
        # 긴급 상황 체크
        if current_q.get("urgent_if_no") and processed == "no":
            self.urgent_actions.append(current_q["id"])
            
        self.current_step += 1
        
        # 즉시 조치가 필요한지 확인
        if self._needs_immediate_action() and not self.immediate_action_delivered:
            self.immediate_action_delivered = True  # 메시지를 전달했다고 표시
            return self._get_immediate_action()
        
        return self.get_next_question()
    
    def _process_yes_no(self, answer: str) -> str:
        """예/아니오 처리"""
        answer_lower = answer.lower().strip()
        
        yes_words = ["네", "예", "응", "맞", "했", "그래", "있"]
        no_words = ["아니", "안", "못", "없", "안했", "싫"]
        
        if any(word in answer_lower for word in yes_words):
            return "yes"
        elif any(word in answer_lower for word in no_words):
            return "no"
        else:
            return "unclear"
    
    def _needs_immediate_action(self) -> bool:
        """즉시 조치 필요 여부"""
        # 돈을 보냈는데 계좌정지를 안 했을 때
        money_sent = self.responses.get("money_sent", {}).get("answer") == "yes"
        account_not_frozen = self.responses.get("account_frozen", {}).get("answer") == "no"
        
        return money_sent and account_not_frozen
    
    def _get_immediate_action(self) -> str:
        """즉시 조치 안내"""
        return "🚨 긴급! 지금 즉시 은행에 전화해서 계좌지급정지 신청하세요!"
    
    def _generate_final_assessment(self) -> str:
        """최종 평가 생성"""
        priority_actions = []
        
        # 우선순위 액션 결정
        if self.responses.get("account_frozen", {}).get("answer") == "no":
            priority_actions.append("1. 즉시 계좌지급정지 신청")
        
        if self.responses.get("police_report", {}).get("answer") == "no":
            priority_actions.append("2. 112번 신고")
            
        if self.responses.get("pass_app", {}).get("answer") == "no":
            priority_actions.append("3. PASS 앱에서 명의도용방지 신청")
        
        if not priority_actions:
            return "기본 조치는 완료되었습니다. 추가 상담은 132번으로 연락하세요."
        
        result = "📋 우선순위 조치:\n"
        result += "\n".join(priority_actions[:2])  # 최대 2개만
        result += "\n\n자세한 상담은 132번으로 연락하세요."
        
        return result
    
    def is_complete(self) -> bool:
        """평가 완료 여부"""
        return self.current_step >= len(self.checklist)

# ============================================================================
# 응급 상황 처리기 (단일 책임 원칙)
# ============================================================================

class EmergencyHandler:
    """응급 상황 감지 및 처리"""
    
    def __init__(self):
        self.emergency_keywords = {
            "high": ["돈", "송금", "보냈", "이체", "급해", "사기", "당했"],

            "medium": ["의심", "이상", "전화", "문자", "피싱"],
            
            "time_critical": ["방금", "지금", "분전", "시간전", "오늘"]
        }
        
        self.emergency_responses = {
            9: "🚨 매우 긴급! 즉시 112신고하고 1811-0041번으로 연락하세요!",
            8: "🚨 긴급상황! 지금 132번으로 전화하세요!",
            7: "⚠️ 빠른 조치 필요! 132번 상담받으세요.",
            6: "주의가 필요한 상황입니다. 132번으로 상담받으세요.",
            5: "상담이 도움될 것 같습니다. 132번으로 연락해보세요."
        }
    
    def detect_emergency(self, text: str) -> int:
        """응급도 감지 (1-10)"""
        if not text:
            return 5
            
        text_lower = text.lower()
        urgency = 5
        
        # 고위험 키워드
        for keyword in self.emergency_keywords["high"]:
            if keyword in text_lower:
                urgency += 3
                break
        
        # 중위험 키워드
        for keyword in self.emergency_keywords["medium"]:
            if keyword in text_lower:
                urgency += 2
                break
        
        # 시간 임박성
        for keyword in self.emergency_keywords["time_critical"]:
            if keyword in text_lower:
                urgency += 2
                break
        
        return min(urgency, 10)
    
    def get_emergency_response(self, urgency: int) -> str:
        """응급도에 따른 응답"""
        for level in sorted(self.emergency_responses.keys(), reverse=True):
            if urgency >= level:
                return self.emergency_responses[level]
        
        return "132번으로 상담받으세요."

# ============================================================================
# 상담 전략 구현 (전략 패턴 적용)
# ============================================================================

class PersonalizedConsultationStrategy:
    """개인 맞춤형 상담 전략 (2번 선택) - 수정된 버전"""
    
    def __init__(self):
        self.emergency_handler = EmergencyHandler()
        self.conversation_turns = 0
        self.user_situation = {}
        
        # (중요!) 하이브리드 의사결정 엔진을 여기서 생성하고 사용합니다.
        self.decision_engine = SimplifiedHybridDecisionEngine(debug=True)
        
        self.situation_patterns = {
            "prevention": {
                "keywords": ["예방", "미리", "설정", "막기"],
                "response": "PASS 앱에서 명의도용방지서비스를 신청하세요. 설정 방법을 알려드릴까요?"
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
    
    async def process_input(self, user_input: str, context: Dict[str, Any] = None) -> str:
        """사용자 입력 처리 (의사결정 엔진 사용)"""
        self.conversation_turns += 1
        
        
        # 1. 응급 상황은 최우선으로 처리
        urgency = self.emergency_handler.detect_emergency(user_input)
        if urgency >= 8:
            return self.emergency_handler.get_emergency_response(urgency)
        
        # 2. 하이브리드 엔진을 사용하여 Gemini 사용 여부 결정
        if not context:
            context = {}
        context["conversation_turns"] = self.conversation_turns
        
        # 여기서 정교한 판단이 이루어집니다.
        decision = self.decision_engine.should_use_gemini(user_input, context)
        
        # 3. 결정에 따라 Gemini를 호출하거나 룰 기반으로 응답
        if decision.get("use_gemini"):
            # Gemini를 사용하여 깊이 있는 답변 생성
            return await self._get_gemini_response(user_input, context)
        else:
            # 룰 기반으로 빠르고 간단한 답변 제공
            return self._get_rule_based_response(user_input)

    # _get_rule_based_response를 약간 수정합니다.
    def _get_rule_based_response(self, user_input: str) -> str:
        """룰 기반 응답 (situation 인자 없이 독립적으로 작동)"""
        text_lower = user_input.lower()
        
        for situation, data in self.situation_patterns.items():
            if any(keyword in text_lower for keyword in data["keywords"]):
                return data["response"]

        # Gemini를 쓰지 않기로 결정했을 때의 최종 폴백 응답
        return "상황을 좀 더 구체적으로 말씀해 주시면 더 정확한 도움을 드릴 수 있습니다."
    
    async def _get_gemini_response(self, user_input: str, context: Dict[str, Any]) -> str:
        """Gemini 응답 생성"""
        try:
            from services.gemini_assistant import gemini_assistant
            
            if not gemini_assistant.is_enabled:
                return self._get_rule_based_response(user_input)
            
            # Gemini에 상황 정보 제공
            enhanced_context = {
                "conversation_turns": self.conversation_turns,
                "user_situation": self.user_situation,
                **(context or {})
            }
            
            result = await asyncio.wait_for(
                gemini_assistant.analyze_and_respond(user_input, enhanced_context),
                timeout=3.0
            )
            
            response_text = result.get("response", "")
            suggestion_text = result.get("next_suggestion", "")

            if response_text and suggestion_text:
                # 추천 질문이 있다면, 자연스럽게 안내 문구를 추가합니다.
                return f"{response_text}\n\n다음으로는 '{suggestion_text}'에 대해 물어보실 수 있어요."
            elif response_text:
                # 답변만 있다면 답변만 반환합니다.
                return response_text
            
        except Exception as e:
            logger.warning(f"Gemini 처리 실패: {e}")
        
        return self._get_rule_based_response(user_input)
    
    def is_complete(self) -> bool:
        """대화 완료 여부"""
        return self.conversation_turns >= 8

# ============================================================================
# 메인 그래프 시스템 (의존성 주입 적용)
# ============================================================================

class VoiceFriendlyPhishingGraph:
    """
    음성 친화적 보이스피싱 상담 AI 시스템
    - SOLID 원칙 적용
    - 전략 패턴으로 1번/2번 모드 분리
    - 의존성 주입으로 확장성 확보
    """
    
    def __init__(self, debug: bool = True):
        self.debug = debug
        
        # 의존성 주입
        self.victim_assessment = VictimInfoAssessment()
        self.consultation_strategy = PersonalizedConsultationStrategy()
        self.emergency_handler = EmergencyHandler()
        
        # 🔥 핵심 수정: 그래프를 올바르게 빌드
        self.graph = self._build_corrected_voice_friendly_graph()
        
        # 상태 관리
        self.current_state = None
        self.session_id = None
        self.conversation_mode = "normal"
        
        if debug:
            print("✅ 수정된 SOLID 원칙 적용 음성 친화적 상담 그래프 초기화 완료")

    # ========================================================================
    # 메인 인터페이스 (conversation_manager용)
    # ========================================================================
    
    async def process_user_input(self, user_input: str) -> str:
        """메인 사용자 입력 처리 인터페이스"""
        try:
            if self.debug:
                print(f"🧠 AI 처리 시작: {user_input}")
            
            # 1. 입력 전처리
            processed_input = self._preprocess_input(user_input)
            if not processed_input:
                return "다시 말씀해 주세요."
            
            # 2. 모드 선택 처리 (첫 대화)
            if not self.current_state:
                mode = self._detect_mode_selection(processed_input)
                
                if mode == "assessment":
                    return await self._start_assessment_mode(processed_input)
                elif mode == "consultation":
                    return await self._start_consultation_mode(processed_input)
                elif mode == "unknown":
                    return self._get_mode_selection_message()
            
            # 3. 선택된 모드에 따른 처리
            if self.conversation_mode == "assessment":
                return await self._handle_assessment_mode(processed_input)
            else:
                return await self._handle_consultation_mode(processed_input)
                
        except Exception as e:
            if self.debug:
                print(f"❌ AI 처리 오류: {e}")
            logger.error(f"AI 처리 오류: {e}")
            return "일시적 문제가 발생했습니다. 132번으로 연락주세요."
    
    async def _start_assessment_mode(self, user_input: str) -> str:
        """평가 모드 시작"""
        self.conversation_mode = "assessment"
        await self._initialize_conversation_state()
        
        first_question = self.victim_assessment.get_next_question()
        return f"📋 피해 정보를 체계적으로 확인하겠습니다.\n\n{first_question}"
    
    async def _start_consultation_mode(self, user_input: str) -> str:
        """상담 모드 시작"""
        self.conversation_mode = "consultation"
        await self._initialize_conversation_state()
        
        # 첫 입력부터 처리
        response = await self.consultation_strategy.process_input(user_input)
        return response
    
    async def _handle_assessment_mode(self, user_input: str) -> str:
        """평가 모드 처리 - 수정된 버전"""
        
        # 답변을 먼저 처리합니다.
        response = self.victim_assessment.process_answer(user_input)
        
        # 평가가 방금 완료되었는지 확인합니다.
        if self.victim_assessment.is_complete():
            self.conversation_mode = "consultation" # 상담 모드로 전환
            
            # 수집된 답변들을 바탕으로 Gemini에게 요약 및 조치 제안을 요청합니다.
            assessment_results = self.victim_assessment.responses
            summary_prompt = f"다음은 사용자의 피해 상황 체크리스트 답변입니다: {assessment_results}. 이 정보를 바탕으로 사용자에게 가장 시급하고 중요한 조치 2가지를 80자 이내로 요약해서 알려주세요."
            
            # 상담 전략(consultation_strategy)을 통해 Gemini를 호출합니다.
            final_summary = await self.consultation_strategy.process_input(summary_prompt)
            
            # 기존 평가 완료 메시지 대신, Gemini가 생성한 요약 메시지를 반환합니다.
            return final_summary

        # 평가가 아직 진행 중이라면 다음 질문을 반환합니다.
        return response
    
    async def _handle_consultation_mode(self, user_input: str) -> str:
        """상담 모드 처리"""

        last_ai_message = ""
        if self.current_state and self.current_state.get("messages"):
            for msg in reversed(self.current_state["messages"]):
                if msg.get("role") == "assistant":
                    last_ai_message = msg.get("content", "")
                    break

        context = {
            "urgency_level": 5,
            "conversation_turns": getattr(self.consultation_strategy, 'conversation_turns', 0),
            "last_ai_response": last_ai_message # Gemini에게 이전 답변을 알려줍니다.
        }
        
        response = await self.consultation_strategy.process_input(user_input, context)
        
        # 응답 길이 제한
        if len(response) > 80:
            response = response[:77] + "..."
        
        return response
    
    async def continue_conversation(self, state: VictimRecoveryState, user_input: str) -> VictimRecoveryState:
        """🔥 수정된 대화 계속 - 올바른 노드 실행"""
        
        if not user_input.strip():
            state["messages"].append({
                "role": "assistant",
                "content": "다시 말씀해 주세요.",
                "timestamp": datetime.now()
            })
            return state
        
        # 사용자 메시지 추가
        state["messages"].append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now()
        })
        
        try:
            # 🔥 핵심: LangGraph 실행
            if self.debug:
                print(f"🚀 LangGraph 노드 실행 시작 - 현재 단계: {state.get('current_step')}")
            
            # LangGraph invoke로 노드 실행
            updated_state = self.graph.invoke(state)
            
            if self.debug:
                new_step = updated_state.get('current_step', 'unknown')
                print(f"✅ LangGraph 노드 실행 완료 - 새로운 단계: {new_step}")
            
            return updated_state
            
        except Exception as e:
            if self.debug:
                print(f"❌ LangGraph 노드 실행 실패: {e}")
            
            # 폴백 처리
            state["messages"].append({
                "role": "assistant",
                "content": "일시적 문제가 발생했습니다. 132번으로 연락주세요.",
                "timestamp": datetime.now()
            })
            
            return state

    # ========================================================================
    # 그래프 구성 (기존 인터페이스 호환성 유지)
    # ========================================================================
    
    def _build_corrected_voice_friendly_graph(self) -> StateGraph:
        """🔥 수정된 음성 친화적 그래프 구성"""
        workflow = StateGraph(VictimRecoveryState)
        
        # 노드들 추가
        workflow.add_node("greeting", self._corrected_greeting_node)
        workflow.add_node("mode_selection", self._corrected_mode_selection_node)
        workflow.add_node("assessment", self._corrected_assessment_node)
        workflow.add_node("consultation", self._corrected_consultation_node)
        workflow.add_node("emergency", self._emergency_node)
        workflow.add_node("complete", self._complete_node)
        
        # 🔥 수정된 엣지 구성
        workflow.add_edge(START, "greeting")
        
        # greeting에서 분기
        workflow.add_conditional_edges(
            "greeting",
            self._route_after_greeting,
            {
                "mode_selection": "mode_selection",
                "emergency": "emergency"
            }
        )
        
        # mode_selection에서 분기
        workflow.add_conditional_edges(
            "mode_selection",
            self._route_after_mode,
            {
                "assessment": "assessment",
                "consultation": "consultation",
                "emergency": "emergency"  # 응급상황 추가
            }
        )
        
        # assessment에서 분기
        workflow.add_conditional_edges(
            "assessment",
            self._route_after_assessment,
            {
                "assessment": "assessment",      # 평가 계속
                "consultation": "consultation",  # 평가 완료 후 상담
                "complete": "complete",         # 완료
                "emergency": "emergency"        # 응급상황
            }
        )
        
        # consultation에서 분기
        workflow.add_conditional_edges(
            "consultation",
            self._route_after_consultation,
            {
                "consultation": "consultation",  # 상담 계속
                "complete": "complete",         # 완료
                "emergency": "emergency"        # 응급상황
            }
        )
        
        workflow.add_edge("emergency", "complete")
        workflow.add_edge("complete", END)
        
        return workflow.compile()

    # ========================================================================
    # 노드 구현
    # ========================================================================
    
    def _corrected_greeting_node(self, state: VictimRecoveryState) -> VictimRecoveryState:
        """🔥 수정된 인사 노드 - 모드 선택 포함"""
        
        # 모드 선택 메시지 생성
        greeting = """안녕하세요. 보이스피싱 상담센터입니다.

1번: 피해 상황 체크리스트 (단계별 확인)
2번: 맞춤형 상담 (상황에 맞는 조치)

1번 또는 2번이라고 말씀해주세요."""
        
        state["messages"].append({
            "role": "assistant",
            "content": greeting,
            "timestamp": datetime.now()
        })
        
        state["current_step"] = "greeting_complete"
        state["conversation_turns"] = state.get("conversation_turns", 0) + 1
        
        if self.debug:
            print(f"🎬 인사 노드 실행: {state['current_step']}")
        
        return state
    
    def _corrected_mode_selection_node(self, state: VictimRecoveryState) -> VictimRecoveryState:
        """🔥 수정된 모드 선택 노드"""
        
        last_input = self._get_last_user_message(state)
        
        if not last_input:
            # 입력이 없으면 다시 안내
            response = "1번 또는 2번을 선택해주세요."
        else:
            # 모드 감지
            mode = self._detect_mode_selection(last_input)
            
            if mode == "assessment":
                self.conversation_mode = "assessment"
                response = "📋 피해 상황을 체계적으로 확인하겠습니다."
                state["current_step"] = "mode_selected_assessment"
            elif mode == "consultation":
                self.conversation_mode = "consultation"
                response = "💬 맞춤형 상담을 시작하겠습니다."
                state["current_step"] = "mode_selected_consultation"
            else:
                response = "1번 또는 2번 중에서 선택해주세요."
                state["current_step"] = "mode_selection_retry"
        
        state["messages"].append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now()
        })
        
        state["conversation_turns"] = state.get("conversation_turns", 0) + 1
        
        if self.debug:
            print(f"🎯 모드 선택: {self.conversation_mode}")
        
        return state
    
    def _corrected_assessment_node(self, state: VictimRecoveryState) -> VictimRecoveryState:
        """🔥 수정된 평가 노드 - Gemini 연동 가능"""
        
        last_input = self._get_last_user_message(state)
        
        # 🔥 핵심: 평가 모드에서도 복잡한 질문은 Gemini 활용
        if last_input and self._is_complex_question(last_input):
            # 복잡한 질문은 상담 전략으로 처리
            try:
                context = {
                    "conversation_turns": state.get("conversation_turns", 0),
                    "current_mode": "assessment"
                }
                
                # 🔥 비동기 호출을 동기로 처리 (노드 내에서)
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 이미 이벤트 루프가 실행 중인 경우
                        response = self.consultation_strategy._get_rule_based_response(last_input)
                    else:
                        response = loop.run_until_complete(
                            self.consultation_strategy.process_input(last_input, context)
                        )
                except RuntimeError:
                    # 새로운 이벤트 루프 생성
                    response = asyncio.run(
                        self.consultation_strategy.process_input(last_input, context)
                    )
                
                if self.debug:
                    print(f"🧠 평가 모드에서 Gemini 활용: {response}")
                    
            except Exception as e:
                if self.debug:
                    print(f"⚠️ 평가 모드 Gemini 실패: {e}")
                response = self.victim_assessment.process_answer(last_input)
        else:
            # 일반적인 평가 처리
            if last_input:
                response = self.victim_assessment.process_answer(last_input)
            else:
                response = self.victim_assessment.get_next_question()
        
        state["messages"].append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now()
        })
        
        # 평가 완료 확인
        if self.victim_assessment.is_complete():
            state["current_step"] = "assessment_complete"
        else:
            state["current_step"] = "assessment_in_progress"
        
        state["conversation_turns"] = state.get("conversation_turns", 0) + 1
        
        if self.debug:
            print(f"📋 평가 노드: {state['current_step']}")
        
        return state
    
    def _corrected_consultation_node(self, state: VictimRecoveryState) -> VictimRecoveryState:
        """🔥 수정된 상담 노드 - 완전한 Gemini 연동"""
        
        last_input = self._get_last_user_message(state)
        
        if last_input:
            try:
                # 🔥 핵심: 상담 전략으로 완전한 처리
                context = {
                    "conversation_turns": state.get("conversation_turns", 0),
                    "urgency_level": state.get("urgency_level", 5),
                    "current_mode": "consultation"
                }
                
                # 🔥 비동기 호출 처리
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 동기 버전 사용
                        response = self._sync_consultation_processing(last_input, context)
                    else:
                        response = loop.run_until_complete(
                            self.consultation_strategy.process_input(last_input, context)
                        )
                except RuntimeError:
                    response = asyncio.run(
                        self.consultation_strategy.process_input(last_input, context)
                    )
                
                if self.debug:
                    print(f"💬 상담 노드 Gemini 처리: {response}")
                    
            except Exception as e:
                if self.debug:
                    print(f"⚠️ 상담 노드 처리 실패: {e}")
                
                # 폴백: 응급 상황 처리
                urgency = self.emergency_handler.detect_emergency(last_input)
                if urgency >= 8:
                    response = self.emergency_handler.get_emergency_response(urgency)
                else:
                    response = "상황을 좀 더 구체적으로 말씀해 주시면 더 정확한 도움을 드릴 수 있습니다."
        else:
            response = "어떤 도움이 필요하신지 말씀해 주세요."
        
        state["messages"].append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now()
        })
        
        state["current_step"] = "consultation_in_progress"
        state["conversation_turns"] = state.get("conversation_turns", 0) + 1
        
        # 완료 조건 확인
        if self.consultation_strategy.is_complete():
            state["current_step"] = "consultation_complete"
        
        if self.debug:
            print(f"💬 상담 노드: {state['current_step']}")
        
        return state
    

    def _sync_consultation_processing(self, user_input: str, context: Dict[str, Any]) -> str:
        """동기식 상담 처리 (노드 내 사용)"""
        
        # 하이브리드 엔진 판단
        decision = self.consultation_strategy.decision_engine.should_use_gemini(user_input, context)
        
        if decision.get("use_gemini"):
            # Gemini를 사용해야 하지만 동기 환경에서는 룰 기반으로 폴백
            if self.debug:
                print("🔄 비동기 Gemini → 동기 룰 기반 폴백")
            return self.consultation_strategy._get_rule_based_response(user_input)
        else:
            # 룰 기반 처리
            return self.consultation_strategy._get_rule_based_response(user_input)

    def _is_complex_question(self, user_input: str) -> bool:
        """복잡한 질문 여부 판단"""
        
        complex_indicators = [
            "설명", "뭐예요", "어떻게", "왜", "자세히", 
            "말고", "다른", "추가", "이해", "헷갈"
        ]
        
        user_lower = user_input.lower()
        return any(indicator in user_lower for indicator in complex_indicators)
    # ========================================================================
    # 라우팅 함수들
    # ========================================================================
    
    def _route_after_greeting(self, state: VictimRecoveryState) -> Literal["mode_selection", "emergency"]:
        """인사 후 라우팅"""
        
        last_input = self._get_last_user_message(state)
        
        # 응급 상황 우선 확인
        if last_input:
            urgency = self.emergency_handler.detect_emergency(last_input)
            if urgency >= 9:
                return "emergency"
        
        return "mode_selection"
    
    def _route_after_mode(self, state: VictimRecoveryState) -> Literal["assessment", "consultation", "emergency"]:
        """모드 선택 후 라우팅"""
        
        current_step = state.get("current_step", "")
        last_input = self._get_last_user_message(state)
        
        # 응급 상황 확인
        if last_input:
            urgency = self.emergency_handler.detect_emergency(last_input)
            if urgency >= 9:
                return "emergency"
        
        # 모드에 따른 라우팅
        if current_step == "mode_selected_assessment":
            return "assessment"
        elif current_step == "mode_selected_consultation":
            return "consultation"
        else:
            # 재시도 필요
            return "mode_selection"
    
    def _route_after_assessment(self, state: VictimRecoveryState) -> Literal["assessment", "consultation", "complete", "emergency"]:
        """평가 후 라우팅"""
        
        last_input = self._get_last_user_message(state)
        
        # 응급 상황 확인
        if last_input:
            urgency = self.emergency_handler.detect_emergency(last_input)
            if urgency >= 9:
                return "emergency"
        
        current_step = state.get("current_step", "")
        turns = state.get("conversation_turns", 0)
        
        # 평가 완료 확인
        if current_step == "assessment_complete" or self.victim_assessment.is_complete():
            # 평가 완료 후 상담 모드로 전환
            self.conversation_mode = "consultation"
            return "consultation"
        
        # 최대 턴 수 확인
        if turns >= 15:
            return "complete"
        
        # 평가 계속
        return "assessment"
    
    def _route_after_consultation(self, state: VictimRecoveryState) -> Literal["consultation", "complete", "emergency"]:
        """상담 후 라우팅"""
        
        last_input = self._get_last_user_message(state)
        
        # 응급 상황 확인
        if last_input:
            urgency = self.emergency_handler.detect_emergency(last_input)
            if urgency >= 9:
                return "emergency"
        
        current_step = state.get("current_step", "")
        turns = state.get("conversation_turns", 0)
        
        # 완료 조건 확인
        if (current_step == "consultation_complete" or 
            self.consultation_strategy.is_complete() or 
            turns >= 12):
            return "complete"
        
        # 상담 계속
        return "consultation"

    # ========================================================================
    # 유틸리티 함수들
    # ========================================================================
    
    def _detect_mode_selection(self, user_input: str) -> str:
        """모드 선택 감지"""
        user_lower = user_input.lower().strip()
        
        if any(pattern in user_lower for pattern in ["1번", "1", "첫번째", "피해", "체크"]):
            return "assessment"
        elif any(pattern in user_lower for pattern in ["2번", "2", "두번째", "상담", "대화"]):
            return "consultation"
        
        return "unknown"
    
    def _preprocess_input(self, text: str) -> str:
        """입력 전처리"""
        if not text:
            return ""
        
        # 음성 인식 오류 교정
        corrections = {
            "일삼이": "132",
            "일팔일일": "1811",
            "보이스비싱": "보이스피싱",
            "명의 도용": "명의도용"
        }
        
        processed = text.strip()
        for wrong, correct in corrections.items():
            processed = processed.replace(wrong, correct)
        
        return processed
    
    def _get_mode_selection_message(self) -> str:
        """모드 선택 메시지"""
        return """안녕하세요. 보이스피싱 상담센터입니다.
1번은 피해 상황 체크리스트 (단계별 확인)
2번은 맞춤형 상담 (상황에 맞는 조치)
1번 또는 2번이라고 말씀해주세요."""
    
    def _get_simple_consultation_response(self, user_input: str) -> str:
        """간단한 상담 응답 (동기용)"""
        user_lower = user_input.lower()
        
        # 예방 관련
        if any(word in user_lower for word in ["예방", "미리", "설정"]):
            return "PASS 앱에서 명의도용방지서비스를 신청하세요."
        
        # 피해 후 대응
        if any(word in user_lower for word in ["당했", "피해", "사기"]):
            return "즉시 132번으로 신고하고 1811-0041번으로 지원 신청하세요."
        
        # 의심 상황
        if any(word in user_lower for word in ["의심", "이상", "확인"]):
            return "의심스러우면 절대 응답하지 마시고 132번으로 확인하세요."
        
        # 도움 요청
        if any(word in user_lower for word in ["도와", "도움", "방법"]):
            return "구체적으로 어떤 상황인지 말씀해 주세요."
        
        # 기본 응답
        return "상황을 좀 더 자세히 말씀해 주시면 도움을 드릴 수 있습니다."
    
    def _get_last_user_message(self, state: VictimRecoveryState) -> str:
        """마지막 사용자 메시지 추출"""
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "").strip()
        return ""

    # ========================================================================
    # 기존 인터페이스 호환성 유지
    # ========================================================================
    
    async def start_conversation(self, session_id: str = None) -> VictimRecoveryState:
        """대화 시작"""
        if not session_id:
            session_id = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        initial_state = create_initial_recovery_state(session_id)
        
        try:
            initial_state = self._greeting_node(initial_state)
            
            if self.debug:
                print(f"✅ 대화 시작: {initial_state.get('current_step', 'unknown')}")
            
            return initial_state
            
        except Exception as e:
            if self.debug:
                print(f"❌ 대화 시작 실패: {e}")
            
            # 폴백 상태
            initial_state["current_step"] = "greeting_complete"
            initial_state["messages"].append({
                "role": "assistant",
                "content": self._get_mode_selection_message(),
                "timestamp": datetime.now()
            })
            return initial_state
    
    async def continue_conversation(self, state: VictimRecoveryState, user_input: str) -> VictimRecoveryState:
        """대화 계속"""
        if not user_input.strip():
            state["messages"].append({
                "role": "assistant",
                "content": "다시 말씀해 주세요.",
                "timestamp": datetime.now()
            })
            return state
        
        # 사용자 메시지 추가
        state["messages"].append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now()
        })
        
        state["conversation_turns"] = state.get("conversation_turns", 0) + 1
        
        try:
            # 현재 단계에 따른 처리
            current_step = state.get("current_step", "greeting_complete")
            
            # 응급 상황 체크
            urgency = self.emergency_handler.detect_emergency(user_input)
            if urgency >= 9:
                state = self._emergency_node(state)
                return state
            
            # 모드별 처리
            if current_step == "greeting_complete":
                mode = self._detect_mode_selection(user_input)
                
                if mode == "assessment":
                    self.conversation_mode = "assessment"
                    # 첫 질문 시작
                    response = f"📋 피해 상황을 체계적으로 확인하겠습니다.\n\n{self.victim_assessment.get_next_question()}"
                    state["current_step"] = "assessment"
                elif mode == "consultation":
                    self.conversation_mode = "consultation"
                    # 상담 시작
                    context = {"urgency_level": urgency, "conversation_turns": state["conversation_turns"]}
                    response = await self.consultation_strategy.process_input(user_input, context)
                    state["current_step"] = "consultation"
                else:
                    response = self._get_mode_selection_message()
                    state["current_step"] = "mode_selection_needed"
                
                state["messages"].append({
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now()
                })
            
            elif current_step in ["assessment", "mode_selection_needed"]:
                if self.conversation_mode == "assessment":
                    if self.victim_assessment.is_complete():
                        # 평가 완료 후 상담 모드로 전환
                        self.conversation_mode = "consultation"
                        response = "평가가 완료되었습니다. 추가 질문이 있으시면 말씀해주세요."
                        state["current_step"] = "consultation"
                    else:
                        response = self.victim_assessment.process_answer(user_input)
                        state["current_step"] = "assessment"
                else:
                    # 평가 모드 시작
                    self.conversation_mode = "assessment"
                    response = f"📋 피해 상황을 체계적으로 확인하겠습니다.\n\n{self.victim_assessment.get_next_question()}"
                    state["current_step"] = "assessment"
                
                state["messages"].append({
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now()
                })
            
            elif current_step == "consultation":
                # 상담 계속
                context = {"urgency_level": urgency, "conversation_turns": state["conversation_turns"]}
                response = await self.consultation_strategy.process_input(user_input, context)
                
                # 응답 길이 제한
                if len(response) > 80:
                    response = response[:77] + "..."
                
                state["messages"].append({
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now()
                })
                
                # 완료 조건 체크
                if self.consultation_strategy.is_complete():
                    state["current_step"] = "consultation_complete"
            
            else:
                # 기타 상황
                state["messages"].append({
                    "role": "assistant",
                    "content": "추가 도움이 필요하시면 132번으로 연락하세요.",
                    "timestamp": datetime.now()
                })
            
            if self.debug:
                print(f"✅ 대화 처리: {state.get('current_step')} (턴 {state['conversation_turns']})")
            
            return state
            
        except Exception as e:
            if self.debug:
                print(f"❌ 대화 처리 실패: {e}")
            
            state["messages"].append({
                "role": "assistant",
                "content": "일시적 문제가 발생했습니다. 132번으로 연락주세요.",
                "timestamp": datetime.now()
            })
            return state

    async def _initialize_conversation_state(self):
        """대화 상태 초기화"""
        if not self.session_id:
            self.session_id = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.current_state = await self.start_conversation(self.session_id)
        
        if self.debug:
            print(f"🧠 상태 초기화: {self.session_id}")

    # ========================================================================
    # 외부 인터페이스들
    # ========================================================================
    
    def get_initial_greeting(self) -> str:
        """초기 인사 메시지"""
        return self._get_mode_selection_message()
    
    def get_farewell_message(self) -> str:
        """마무리 메시지"""
        if self.current_state:
            urgency_level = self.current_state.get("urgency_level", 5)
            
            if urgency_level >= 8:
                return "지금 말씀드린 것부터 하세요. 추가 도움이 필요하면 다시 연락하세요."
            elif urgency_level >= 6:
                return "132번으로 상담받아보시고, 더 궁금한 게 있으면 연락주세요."
            else:
                return "예방 설정 해두시고, 의심스러우면 132번으로 상담받으세요."
        
        return "상담이 완료되었습니다. 132번으로 추가 상담받으세요."
    
    def is_conversation_complete(self) -> bool:
        """대화 완료 여부"""
        if not self.current_state:
            return False
        
        # 평가 모드에서는 assessment 완료 여부 확인
        if self.conversation_mode == "assessment":
            return self.victim_assessment.is_complete()
        
        # 상담 모드에서는 strategy 완료 여부 확인
        if self.conversation_mode == "consultation":
            return self.consultation_strategy.is_complete()
        
        # 기존 종료 조건들
        if self.current_state.get('current_step') == 'consultation_complete':
            return True
        
        conversation_turns = self.current_state.get('conversation_turns', 0)
        return conversation_turns >= 12
    
    def get_conversation_summary(self, state: VictimRecoveryState) -> Dict[str, Any]:
        """대화 요약"""
        return {
            "conversation_mode": self.conversation_mode,
            "urgency_level": state.get("urgency_level", 5),
            "conversation_turns": state.get("conversation_turns", 0),
            "current_step": state.get("current_step", "unknown"),
            "assessment_complete": self.victim_assessment.is_complete() if self.conversation_mode == "assessment" else None,
            "consultation_complete": self.consultation_strategy.is_complete() if self.conversation_mode == "consultation" else None,
            "completion_status": state.get("current_step") == "consultation_complete"
        }
    
    async def cleanup(self):
        """정리 작업"""
        try:
            if self.debug:
                print("🧠 AI 시스템 정리 중...")
            
            # 대화 요약 로그
            if self.current_state:
                summary = self.get_conversation_summary(self.current_state)
                if self.debug:
                    print("🧠 대화 요약:")
                    for key, value in summary.items():
                        print(f"   {key}: {value}")
            
            # 상태 초기화
            self.current_state = None
            self.session_id = None
            self.conversation_mode = "normal"
            
            # 전략 객체들 초기화
            self.victim_assessment = VictimInfoAssessment()
            self.consultation_strategy = PersonalizedConsultationStrategy()
            
            if self.debug:
                print("✅ AI 시스템 정리 완료")
                
        except Exception as e:
            if self.debug:
                print(f"❌ AI 정리 오류: {e}")
            logger.error(f"AI 정리 오류: {e}")


# ============================================================================
# 사용되지 않는 코드 제거를 위한 기존 클래스들 통합
# ============================================================================

# 하위 호환성을 위한 별칭들
OptimizedVoicePhishingGraph = VoiceFriendlyPhishingGraph
StructuredVoicePhishingGraph = VoiceFriendlyPhishingGraph