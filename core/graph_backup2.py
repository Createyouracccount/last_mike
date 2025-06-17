import sys
import os
from datetime import datetime
from typing import Literal, Dict, Any, List, Optional
import asyncio
import re
import logging

# 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from langgraph.graph import StateGraph, START, END
from core.state import VictimRecoveryState, create_initial_recovery_state

# logger 설정
logger = logging.getLogger(__name__)

class VoiceFriendlyPhishingGraph:
    """
    음성 친화적 보이스피싱 상담 그래프
    - 응답 길이 대폭 단축 (50-100자)
    - 한 번에 하나씩만 안내
    - 즉시 실행 가능한 조치 중심
    - 실질적 도움 제공
    """
    
    def __init__(self, debug: bool = True):
        self.debug = debug
        self.graph = self._build_voice_friendly_graph()

        # 하이브리드 기능 초기화
        try:
            from .hybrid_decision_backup import HybridDecisionEngine
            self.decision_engine = HybridDecisionEngine()
            self.use_gemini = self._check_gemini_available()
            if self.debug:
                print("✅ 하이브리드 모드 초기화 완료")
        except ImportError:
            self.decision_engine = None
            self.use_gemini = False
            if self.debug:
                print("⚠️ 하이브리드 모드 비활성화 (hybrid_decision.py 없음)")
        
        # 간결한 단계별 진행
        self.action_steps = {
            "emergency": [
                {
                    "action": "명의도용_차단",
                    "question": "PASS 앱 있으신가요?",
                    "guidance": "PASS 앱에서 전체 메뉴, 명의도용방지서비스 누르세요."
                },
                {
                    "action": "지원_신청",
                    "question": "생활비 지원 받고 싶으신가요?",
                    "guidance": "1811-0041번으로 전화하세요. 최대 300만원 받을 수 있어요."
                },
                {
                    "action": "연락처_제공",
                    "question": "전화번호 더 필요하신가요?",
                    "guidance": "무료 상담은 132번입니다."
                }
            ],
            "normal": [
                {
                    "action": "전문상담",
                    "question": "무료 상담 받아보실래요?",
                    "guidance": "132번으로 전화하시면 무료로 상담받을 수 있어요."
                },
                {
                    "action": "예방설정",
                    "question": "예방 설정 해보실까요?",
                    "guidance": "PASS 앱에서 명의도용방지 설정하시면 됩니다."
                }
            ]
        }
        
        if debug:
            print("✅ 음성 친화적 상담 그래프 초기화 완료")

    def _check_gemini_available(self) -> bool:
        """Gemini 사용 가능 여부 확인 - 개선된 버전"""
        try:
            from services.gemini_assistant3 import gemini_assistant
            is_available = gemini_assistant.is_enabled
            
            if self.debug:
                if is_available:
                    print("✅ Gemini 사용 가능")
                else:
                    print("⚠️ Gemini API 키 없음 - 룰 기반만 사용")
            
            return is_available
        except ImportError:
            if self.debug:
                print("⚠️ Gemini 모듈 없음 - 룰 기반만 사용")
            return False
        except Exception as e:
            if self.debug:
                print(f"⚠️ Gemini 확인 오류: {e} - 룰 기반만 사용")
            return False
    
    def _build_voice_friendly_graph(self) -> StateGraph:
        """음성 친화적 그래프 구성"""
        
        workflow = StateGraph(VictimRecoveryState)
        
        # 간소화된 노드들
        workflow.add_node("greeting", self._greeting_node)              # 초기 응대에만 집중 → 정확한 상황 파악
        workflow.add_node("urgency_check", self._urgency_check_node)    # 긴급도 판단에만 특화
        workflow.add_node("action_guide", self._action_guide_node)
        workflow.add_node("contact_info", self._contact_info_node)
        workflow.add_node("complete", self._complete_node)
        
        # 단순한 흐름
        workflow.add_edge(START, "greeting")
        
        workflow.add_conditional_edges(
            "greeting",
            self._route_after_greeting,
            {
                "urgency_check": "urgency_check",
            }
        )
        
        workflow.add_conditional_edges(
            "urgency_check",
            self._route_after_urgency,
            {
                "action_guide": "action_guide",
                # "complete": "complete"
                # 긴급도 파악 후 넘기는 식으로, 완료가 나버리지 않도록 수정
            }
        )
        
        workflow.add_conditional_edges(
            "action_guide",
            self._route_after_action,
            {
                "action_guide": "action_guide",  # 다음 액션
                "contact_info": "contact_info",
                "complete": "complete"
            }
        )
        
        workflow.add_conditional_edges(
            "contact_info",
            self._route_after_contact,
            {
                "complete": "complete"
            }
        )
        
        workflow.add_edge("complete", END)
        
        return workflow.compile()
    
    def _greeting_node(self, state: VictimRecoveryState) -> VictimRecoveryState:
        """간결한 인사"""
        
        if state.get("greeting_done", False):
            return state
            
        greeting_message = "안녕하세요. 보이스피싱 상담센터입니다. 지금 급하게 도움이 필요한 상황인가요?"

        state["messages"].append({
            "role": "assistant",
            "content": greeting_message,
            "timestamp": datetime.now()
        })
        
        state["current_step"] = "greeting_complete"
        state["greeting_done"] = True
        state["action_step_index"] = 0
        
        if self.debug:
            print("✅ 간결한 인사 완료")
        
        return state
    
    def _urgency_check_node(self, state: VictimRecoveryState) -> VictimRecoveryState:
        """긴급도 빠른 판단"""
        
        last_message = self._get_last_user_message(state)
        
        if not last_message:
            urgency_level = 5
            # 기본적으로 응급도는 5로 정함.
        else:
            urgency_level = self._quick_urgency_assessment(last_message)
        
        state["urgency_level"] = urgency_level
        state["is_emergency"] = urgency_level >= 7
        
        # 긴급도별 즉시 응답
        if urgency_level >= 8:
            response = "매우 급한 상황이시군요. 지금 당장 해야 할 일을 알려드릴게요."
        elif urgency_level >= 6:
            response = "걱정되는 상황이네요. 도움 받을 수 있는 방법이 있어요."
        else:
            response = "정확한 상황 파악과 확인을 위해 다시 한 번 질문하겠습니다. 어떤 상황인지 말씀해주시겠어요?"
        
        state["messages"].append({
            "role": "assistant", 
            "content": response,
            "timestamp": datetime.now()
        })
        
        state["current_step"] = "urgency_assessed"
        
        if self.debug:
            print(f"✅ 긴급도 판단: {urgency_level}")
        
        return state
    
    def _action_guide_node(self, state: VictimRecoveryState) -> VictimRecoveryState:
        """한 번에 하나씩 액션 안내"""
        
        urgency_level = state.get("urgency_level", 5)
        action_step_index = state.get("action_step_index", 0)
        
        # 긴급도에 따른 액션 리스트 선택
        if urgency_level >= 7:
            action_list = self.action_steps["emergency"]
        else:
            action_list = self.action_steps["normal"]
        
        # 이전 답변 처리 (첫 번째가 아닌 경우)
        if action_step_index > 0:
            last_user_message = self._get_last_user_message(state)
            # 간단한 답변 확인만
            if last_user_message and any(word in last_user_message.lower() for word in ["네", "예", "응", "맞", "해"]):
                state["user_confirmed"] = True
        
        # 현재 액션 가져오기
        if action_step_index < len(action_list):
            current_action = action_list[action_step_index]
            
            # 질문 먼저, 그 다음 안내
            if not state.get("action_explained", False):
                response = current_action["question"]
                state["action_explained"] = True
            else:
                response = current_action["guidance"]
                state["action_step_index"] = action_step_index + 1
                state["action_explained"] = False
        else:
            # 모든 액션 완료
            response = "도움이 더 필요하시면 말씀해 주세요."
            state["actions_complete"] = True
        
        state["messages"].append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now()
        })
        
        state["current_step"] = "action_guiding"
        
        if self.debug:
            print(f"✅ 액션 안내: 단계 {action_step_index}")
        
        return state
    
    def _contact_info_node(self, state: VictimRecoveryState) -> VictimRecoveryState:
        """핵심 연락처만 간단히"""
        
        urgency_level = state.get("urgency_level", 5)
        
        if urgency_level >= 8:
            response = "긴급 연락처를 알려드릴게요. 1811-0041번과 132번입니다."
        elif urgency_level >= 6:
            response = "무료 상담은 132번이에요. 메모해 두세요."
        else:
            response = "궁금한 게 있으면 132번으로 전화하세요."
        
        state["messages"].append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now()
        })
        
        state["current_step"] = "contact_provided"
        
        if self.debug:
            print("✅ 핵심 연락처 제공")
        
        return state
    
    def _complete_node(self, state: VictimRecoveryState) -> VictimRecoveryState:
        """간결한 마무리"""
        
        urgency_level = state.get("urgency_level", 5)
        
        if urgency_level >= 8:
            response = "지금 말씀드린 것부터 하세요. 추가 도움이 필요하면 다시 연락하세요."
        elif urgency_level >= 6:
            response = "132번으로 상담받아보시고, 더 궁금한 게 있으면 연락주세요."
        else:
            response = "예방 설정 해두시고, 의심스러우면 132번으로 상담받으세요."
        
        state["messages"].append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now()
        })
        
        state["current_step"] = "consultation_complete"
        
        if self.debug:
            print("✅ 간결한 상담 완료")
        
        return state
    
    # ========================================================================
    # 라우팅 함수들
    # ========================================================================
    
    def _route_after_greeting(self, state: VictimRecoveryState) -> Literal["urgency_check"]:
        return "urgency_check"

    def _route_after_urgency(self, state: VictimRecoveryState) -> Literal["action_guide", "complete"]:
        urgency_level = state.get("urgency_level", 5)
        if urgency_level >= 5:  # 대부분 액션 안내
            return "action_guide"
        else:
            return "complete"

    def _route_after_action(self, state: VictimRecoveryState) -> Literal["action_guide", "contact_info", "complete"]:
        if state.get("actions_complete", False):
            return "contact_info"
        elif state.get("action_step_index", 0) >= 2:  # 2단계 후 연락처 제공
            return "contact_info"
        else:
            return "action_guide"
        
    def _route_after_contact(self, state: VictimRecoveryState) -> Literal["complete"]:
        return "complete"
    
    # ========================================================================
    # 유틸리티 함수들
    # ========================================================================
    
    def _quick_urgency_assessment(self, user_input: str) -> int:
        """빠른 긴급도 판단 (단순화)"""
        
        user_lower = user_input.lower().strip()
        urgency_score = 5  # 기본값
        
        # 고긴급 키워드
        high_urgency = ['돈', '송금', '보냈', '이체', '급해', '도와', '사기', '억', '만원', '계좌', '틀렸']
        medium_urgency = ['의심', '이상', '피싱', '전화', '문자']
        
        # 키워드 매칭
        for word in high_urgency:
            if word in user_lower:
                urgency_score += 3
                break
        
        for word in medium_urgency:
            if word in user_lower:
                urgency_score += 2
                break
        
        # 시간 표현 (최근일수록 긴급)
        if any(time_word in user_lower for time_word in ['방금', '지금', '분전', '시간전', '오늘']):
            urgency_score += 2
        
        return min(urgency_score, 10)
    
    def _get_last_user_message(self, state: VictimRecoveryState) -> str:
        """마지막 사용자 메시지 추출"""
        
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "").strip()
        return ""
    
    def _get_last_ai_message(self, state: VictimRecoveryState) -> str:
        """마지막 AI 메시지 추출"""
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                return msg.get("content", "")
        return ""
    
    # ========================================================================
    # 메인 인터페이스
    # ========================================================================
    
    async def start_conversation(self, session_id: str = None) -> VictimRecoveryState:
        """음성 친화적 상담 시작"""
        
        if not session_id:
            session_id = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        initial_state = create_initial_recovery_state(session_id)
        
        try:
            # 간단한 시작
            initial_state = self._greeting_node(initial_state)
            
            if self.debug:
                print(f"✅ 음성 친화적 상담 시작: {initial_state.get('current_step', 'unknown')}")
            
            return initial_state
            
        except Exception as e:
            if self.debug:
                print(f"❌ 상담 시작 실패: {e}")
            
            # 실패 시 기본 상태
            initial_state["current_step"] = "greeting_complete"
            initial_state["messages"].append({
                "role": "assistant",
                "content": "상담센터입니다. 어떤 일인지 간단히 말씀해 주세요.",
                "timestamp": datetime.now()
            })
            return initial_state
    
    async def continue_conversation(self, state: VictimRecoveryState, user_input: str) -> VictimRecoveryState:
        """단계별 간결한 대화 처리 - 하이브리드 지원"""
        
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
        
        # 🆕 하이브리드 판단 (decision_engine이 있을 때만)
        if self.decision_engine and self.use_gemini:
            last_ai_message = self._get_last_ai_message(state)
            decision = self.decision_engine.should_use_gemini(
                user_input, 
                state["messages"], 
                last_ai_message
            )
            
            if self.debug:
                print(f"🔍 하이브리드 판단: {decision['use_gemini']} (신뢰도: {decision['confidence']:.2f})")
                if decision['reasons']:
                    print(f"   이유: {', '.join(decision['reasons'])}")
            
            if decision["use_gemini"]:
                # Gemini 처리
                if self.debug:
                    print("🤖 Gemini 처리 시작")
                return await self._handle_with_gemini(user_input, state, decision)
            else:
                if self.debug:
                    print("⚡ 룰 기반 처리 선택")
        else:
            if self.debug:
                print("⚠️ 하이브리드 모드 비활성화 - 룰 기반만 사용")
        
        # 기존 룰 기반 처리
        try:
            # 현재 단계에 따른 처리
            current_step = state.get("current_step", "greeting_complete")
            
            if current_step == "greeting_complete":
                state = self._urgency_check_node(state)
                
            elif current_step == "urgency_assessed":
                state = self._action_guide_node(state)
                
            elif current_step == "action_guiding":
                state = self._action_guide_node(state)
                
                # 액션 완료 시 연락처 또는 완료로
                if state.get("actions_complete", False) or state.get("action_step_index", 0) >= 2:
                    state = self._contact_info_node(state)
            
            elif current_step == "contact_provided":
                state = self._complete_node(state)
            
            else:
                # 완료 상태에서는 간단한 응답
                state["messages"].append({
                    "role": "assistant",
                    "content": "자세한 도움이 필요하시다면 대한법률구조공단 일삼이(132)에 도움을 요청하는것도 좋은 방법입니다.",
                    "timestamp": datetime.now()
                })
            
            if self.debug:
                print(f"✅ 간결한 처리: {state.get('current_step')} (턴 {state['conversation_turns']})")
            
            return state
            
        except Exception as e:
            if self.debug:
                print(f"❌ 대화 처리 실패: {e}")
            
            state["messages"].append({
                "role": "assistant",
                "content": "문제가 생겼습니다! 피싱 사기는 시간이 가장 중요합니다. 새로고침을 했을 때 정상화면이 보이지 않는다면 즉시 112번으로 연락하여 도움을 요청하세요.",
                "timestamp": datetime.now()
            })
            return state
    
    async def _handle_with_gemini(self, user_input: str, state: VictimRecoveryState, decision: dict) -> VictimRecoveryState:
        """Gemini로 처리 - 개선된 버전"""
        try:
            if self.debug:
                print(f"🤖 Gemini 처리 중... 이유: {decision['reasons']}")
            
            from services.gemini_assistant3 import gemini_assistant
            
            # 현재 상황 정보 수집
            urgency_level = state.get("urgency_level", 5)
            conversation_turns = state.get("conversation_turns", 0)
            
            # 간단한 프롬프트 구성
            context_prompt = f"""사용자가 보이스피싱 상담에서 말했습니다: "{user_input}"

다음 중 가장 적절한 응답을 80자 이내로 해주세요:

1. 질문유형이 어떻게 대처해야 되는가에 대한 질문이라면: 너무 걱정마시고 다음의 방법을 통해 해결하세요. 라고 말하고 나머지 내용은 우리 graph.py를 보고 사용할만한 내용을 말해 것.
2. 설명 요청이면: 피해자의 질문한 내용에 대해서 자세하고 구체적으로 설명
3. 불만족 표현이면: 다른 방법 제시


JSON 형식: {{"response": "80자 이내 답변"}}"""
            
            # Gemini에 컨텍스트 제공
            context = {
                "urgency_level": urgency_level,
                "conversation_turns": conversation_turns,
                "decision_reasons": decision["reasons"]
            }
            
            # Gemini 응답 생성
            gemini_result = await asyncio.wait_for(
                gemini_assistant.analyze_and_respond(context_prompt, context),
                timeout=4.0  # 4.0초로 단축
            )
            
            # 응답 추출
            ai_response = gemini_result.get("response", "")
            
            # 응답이 없거나 너무 길면 폴백
            if not ai_response or len(ai_response) > 80:
                if self.debug:
                    print("⚠️ Gemini 응답 부적절 - 룰 기반 폴백")
                return await self._fallback_to_rules(state, user_input)
            
            # 80자 제한
            if len(ai_response) > 80:
                ai_response = ai_response[:77] + "..."
            
            state["messages"].append({
                "role": "assistant",
                "content": ai_response,
                "timestamp": datetime.now(),
                "source": "gemini"
            })
            
            if self.debug:
                print(f"✅ Gemini 성공: {ai_response}")
            
            logger.info(f"🤖 Gemini 처리 완료: {decision['reasons']}")
            
            return state
            
        except asyncio.TimeoutError:
            if self.debug:
                print("⏰ Gemini 타임아웃 - 룰 기반 폴백")
            logger.warning("Gemini 타임아웃 - 룰 기반 폴백")
            return await self._fallback_to_rules(state, user_input)
        except Exception as e:
            if self.debug:
                print(f"❌ Gemini 오류: {e} - 룰 기반 폴백")
            logger.error(f"Gemini 처리 실패: {e} - 룰 기반으로 폴백")
            return await self._fallback_to_rules(state, user_input)
    
    async def _fallback_to_rules(self, state: VictimRecoveryState, user_input: str) -> VictimRecoveryState:
        """룰 기반으로 폴백 처리 - 개선된 버전"""
        
        user_lower = user_input.lower()
        
        # "말고" 패턴 감지 - 사용자가 다른 방법을 원함
        if "말고" in user_lower:
            if any(keyword in user_lower for keyword in ["예방", "사후", "다른"]):
                response = "패스(PASS) 앱에서 명의도용방지서비스를 신청하시거나 대한법률구조공단의 132번으로 무료상담받으세요."
            else:
                response = "보이스피싱제로 일팔일일 다시 공공사일(1811-0041)번을 통해 피해 지원사업을 신청하실수도 있어요."
            
        # 설명 요청 감지
        elif any(word in user_lower for word in ["뭐예요", "무엇", "어떤", "설명"]):
            if "132" in user_input:
                response = "132번은 대한법률구조공단 무료 상담 번호예요."
            elif "설정" in user_input:
                response = "명의도용방지 설정은 PASS 앱에서 할 수 있어요."
            else:
                response = "자세한 설명은 132번으로 전화하시면 들을 수 있어요."
        
        # 위치/장소 질문
        elif any(word in user_lower for word in ["어디예요", "어디", "누구"]):
            if "132" in user_input:
                response = "전국 어디서나 132번으로 전화하시면 됩니다."
            else:
                response = "132번으로 전화하시면 자세히 알려드려요."
        
        # 추가 방법 요청
        elif any(word in user_lower for word in ["다른", "또", "추가", "더", "어떻게"]):
            response = "보이스피싱제로 1811-0041번으로 생활비 지원도 받을 수 있어요."
        
        # 불만족 표현
        elif any(word in user_lower for word in ["아니", "다시", "별로", "부족"]):
            response = "그럼 132번으로 전문상담 받아보시는 게 좋겠어요."
        
        # 기본 응답
        else:
            response = "궁금한 점이 있으시면 132번으로 전화하세요."
        
        state["messages"].append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now(),
            "source": "rule_fallback"
        })
        
        if self.debug:
            print(f"🔧 룰 기반 폴백: {response}")
        
        return state
    
    def get_conversation_summary(self, state: VictimRecoveryState) -> Dict[str, Any]:
        """대화 요약"""
        
        return {
            "urgency_level": state.get("urgency_level", 5),
            "is_emergency": state.get("is_emergency", False),
            "action_step": state.get("action_step_index", 0),
            "conversation_turns": state.get("conversation_turns", 0),
            "current_step": state.get("current_step", "unknown"),
            "completion_status": state.get("current_step") == "consultation_complete",
            "hybrid_enabled": self.decision_engine is not None,
            "gemini_available": self.use_gemini
        }

# 하위 호환성을 위한 별칭
OptimizedVoicePhishingGraph = VoiceFriendlyPhishingGraph
StructuredVoicePhishingGraph = VoiceFriendlyPhishingGraph