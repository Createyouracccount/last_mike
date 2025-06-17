from langgraph.graph import StateGraph, START, END
from typing import Literal

from datetime import datetime
import re
import asyncio
import logging

from core.state import VictimState, create_initial_state, calculate_risk_score
from core.nodes import VoicePhishingNodes

class VoicePhishingGraph:
    """
    1. START/END 명확한 시작점과 종료점
    2. 상황별 동적 라우팅 (긴급도에 따라 다른 경로)
    3. 되돌아가기 기능 (새로운 정보 발견 시)
    4. LLM 확장 준비 완료
    5. 실제 피해자 대화 패턴 반영
    6. 에러 핸들링 및 로깅 강화
    """
    
    def __init__(self, use_llm: bool = False, debug: bool = False):
        self.nodes = VoicePhishingNodes(use_llm=use_llm)
        self.use_llm = use_llm
        self.debug = debug
        self.graph = self._build_graph()
        
        # 로깅 설정
        if debug:
            logging.basicConfig(level=logging.DEBUG)
            self.logger = logging.getLogger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
    
    def _build_graph(self) -> StateGraph:
        """실제 상담 흐름을 반영한 워크플로우 구성"""
        
        workflow = StateGraph(VictimState)
        
        # ===== 노드 추가 =====
        workflow.add_node("greeting", self.nodes.greeting_node)
        workflow.add_node("initial_assessment", self.nodes.initial_assessment_node)
        workflow.add_node("emergency_response", self.nodes.emergency_response_node)
        workflow.add_node("detailed_analysis", self.nodes.detailed_analysis_node)
        workflow.add_node("action_guidance", self.nodes.action_guidance_node)
        workflow.add_node("verification", self.nodes.verification_node)
        workflow.add_node("follow_up", self.nodes.follow_up_node)
        workflow.add_node("escalation", self.nodes.escalation_node)
        
        # ===== 시작점 설정 =====
        workflow.add_edge(START, "greeting")
        
        # ===== 기본 흐름 =====
        workflow.add_edge("greeting", "initial_assessment")
        
        # ===== 조건부 라우팅 1: 초기 평가 후 =====
        workflow.add_conditional_edges(
            "initial_assessment",
            self._route_after_assessment,
            {
                "emergency": "emergency_response",      # 긴급 상황
                "normal": "detailed_analysis",          # 일반 상담
                "unclear": "initial_assessment",        # 정보 부족, 다시 질문
                "escalate": "escalation"                # 인간 상담원 필요
            }
        )
        
        # ===== 조건부 라우팅 2: 긴급 대응 후 =====
        workflow.add_conditional_edges(
            "emergency_response",
            self._route_after_emergency,
            {
                "continue": "detailed_analysis",        # 긴급 조치 완료, 세부 상담
                "repeat": "emergency_response",         # 조치 재안내 필요
                "escalate": "escalation",               # 복잡한 상황
                "complete": "follow_up"                 # 모든 처리 완료
            }
        )
        
        # ===== 조건부 라우팅 3: 세부 분석 후 =====
        workflow.add_conditional_edges(
            "detailed_analysis", 
            self._route_after_analysis,
            {
                "action_needed": "action_guidance",     # 구체적 조치 안내
                "verify_info": "verification",          # 정보 확인 필요
                "re_assess": "initial_assessment",      # 새로운 정보로 재평가
                "complete": "follow_up"                 # 상담 완료
            }
        )
        
        # ===== 조건부 라우팅 4: 행동 안내 후 =====
        workflow.add_conditional_edges(
            "action_guidance",
            self._route_after_action,
            {
                "next_step": "action_guidance",         # 다음 단계 안내
                "verify": "verification",               # 완료 확인
                "re_analyze": "detailed_analysis",      # 상황 변화로 재분석
                "complete": "follow_up"
            }
        )
        
        # ===== 조건부 라우팅 5: 검증 후 =====
        workflow.add_conditional_edges(
            "verification",
            self._route_after_verification,
            {
                "continue": "action_guidance",          # 계속 안내
                "success": "follow_up",                 # 성공적 완료
                "problem": "detailed_analysis"          # 문제 발생, 재분석
            }
        )
        
        # ===== 종료점 설정 =====
        workflow.add_edge("follow_up", END)
        workflow.add_edge("escalation", END)
        
        return workflow.compile()
    
    # ========================================================================
    # 라우팅 로직들 - 실제 상담 상황을 반영
    # ========================================================================
    
    def _route_after_assessment(self, state: VictimState) -> Literal["emergency", "normal", "unclear", "escalate"]:
        """초기 평가 후 라우팅 - 가장 중요한 분기점"""
        
        try:
            last_message = self._get_last_user_message(state)
            urgency = state.get("urgency_level", 5)
            confidence = state.get("analysis_confidence", 0.5)
            conversation_turns = state.get("conversation_turns", 0)
            
            # ⭐ 무한루프 방지: assessment_attempts 카운터 체크
            assessment_attempts = state.get("assessment_attempts", 0)
            
            if self.debug:
                self.logger.debug(f"Assessment routing - urgency: {urgency}, confidence: {confidence}, turns: {conversation_turns}, attempts: {assessment_attempts}")
            
            # 최대 시도 횟수 초과 시 강제로 normal 처리
            if assessment_attempts >= 3:
                self.logger.warning("Max assessment attempts reached - routing to normal")
                return "normal"
            
            # assessment_attempts 증가
            state["assessment_attempts"] = assessment_attempts + 1
            
            # 1. 긴급 상황 감지
            emergency_keywords = [
                "돈을 보냈", "이체했", "송금했", "계좌번호를 알려줬",
                "비밀번호를 말했", "앱을 설치했", "지금도 전화가", "계속 연락",
                "큰 돈", "많은 돈", "전 재산", "대출받아서"
            ]
            
            has_emergency = any(keyword in last_message for keyword in emergency_keywords)
            
            if has_emergency or urgency >= 8:
                self.logger.info(f"Emergency detected - keywords: {has_emergency}, urgency: {urgency}")
                return "emergency"
            
            # 2. 메시지가 너무 짧거나 신뢰도가 낮으면 unclear (단, 시도 횟수 제한)
            if (confidence < 0.3 or len(last_message.split()) < 3) and assessment_attempts < 2:
                return "unclear"
            
            # 3. 복잡한 상황
            complex_indicators = [
                "여러 번", "계속", "몇 달째", "복잡해서",
                "이해 못하겠", "너무 어려워", "모르겠어요"
            ]
            
            if any(indicator in last_message for indicator in complex_indicators):
                return "escalate"
            
            # 4. 기본값: normal (무한루프 방지)
            return "normal"
            
        except Exception as e:
            self.logger.error(f"Error in assessment routing: {e}")
            return "normal"  # 에러 시 normal로 진행
    
    def _route_after_emergency(self, state: VictimState) -> Literal["continue", "repeat", "escalate", "complete"]:
        """긴급 대응 후 라우팅"""
        
        try:
            last_message = self._get_last_user_message(state)
            completed_actions = state.get("completed_actions", [])
            emergency_repeat_count = state.get("emergency_repeat_count", 0)
            
            # 완료 확인 키워드
            completion_keywords = ["완료했", "했습니다", "끝났", "신고했", "처리됐", "됐어요"]
            confusion_keywords = ["모르겠", "어떻게", "못하겠", "어려워", "이해 안 돼"]
            
            if any(keyword in last_message for keyword in completion_keywords):
                if len(completed_actions) >= 2:  # 주요 조치 완료
                    return "complete"
                else:
                    return "continue"
            
            elif any(keyword in last_message for keyword in confusion_keywords):
                if emergency_repeat_count >= 2:  # 2번 반복 후에도 혼란
                    return "escalate"
                else:
                    state["emergency_repeat_count"] = emergency_repeat_count + 1
                    return "repeat"
            
            # 새로운 긴급 상황 발생
            new_emergency_keywords = ["또 다른", "추가로", "그런데 또", "새로운"]
            if any(keyword in last_message for keyword in new_emergency_keywords):
                return "continue"  # 추가 분석 필요
            
            else:
                if emergency_repeat_count >= 3:  # 3번 반복하면 전문가에게
                    return "escalate"
                state["emergency_repeat_count"] = emergency_repeat_count + 1
                return "repeat"
                
        except Exception as e:
            self.logger.error(f"Error in emergency routing: {e}")
            return "escalate"
    
    def _route_after_analysis(self, state: VictimState) -> Literal["action_needed", "verify_info", "re_assess", "complete"]:
        """세부 분석 후 라우팅"""
        
        try:
            last_message = self._get_last_user_message(state)
            
            # 새로운 정보 감지 (중요한 추가 정보)
            new_info_keywords = ["그런데", "아 그리고", "추가로", "또", "사실은", "참고로"]
            critical_new_info = ["더 많은 돈", "다른 계좌", "또 다른 앱", "추가 피해"]
            
            has_new_info = any(keyword in last_message for keyword in new_info_keywords)
            has_critical_info = any(keyword in last_message for keyword in critical_new_info)
            
            if has_new_info and has_critical_info:
                return "re_assess"  # 중요한 새 정보는 재평가
            
            # 구체적 행동 필요
            next_actions = state.get("next_actions", [])
            if next_actions and len(next_actions) > 0:
                return "action_needed"
            
            # 정보 확인 필요
            uncertainty_keywords = ["확실하지", "기억이", "잘 모르겠", "애매해"]
            if any(keyword in last_message for keyword in uncertainty_keywords):
                return "verify_info"
            
            # 피해자가 만족하거나 더 이상 할 일이 없음
            satisfaction_keywords = ["고마워", "도움됐", "알겠어", "이해했"]
            if any(keyword in last_message for keyword in satisfaction_keywords):
                return "complete"
            
            return "action_needed"  # 기본값
            
        except Exception as e:
            self.logger.error(f"Error in analysis routing: {e}")
            return "complete"
    
    def _route_after_action(self, state: VictimState) -> Literal["next_step", "verify", "re_analyze", "complete"]:
        """행동 안내 후 라우팅"""
        
        try:
            last_message = self._get_last_user_message(state)
            next_actions = state.get("next_actions", [])
            action_repeat_count = state.get("action_repeat_count", 0)
            
            # 완료 확인
            completion_indicators = ["완료", "했습니다", "처리했", "끝났", "됐어요"]
            if any(indicator in last_message for indicator in completion_indicators):
                return "verify"
            
            # 새로운 상황 발생
            problem_keywords = ["안 돼", "오류", "막혔", "문제가", "실패", "안 돼요"]
            if any(keyword in last_message for keyword in problem_keywords):
                return "re_analyze"
            
            # 추가 질문이나 혼란
            question_keywords = ["어떻게", "언제", "어디서", "뭘", "왜"]
            if any(keyword in last_message for keyword in question_keywords):
                if action_repeat_count >= 2:
                    return "re_analyze"  # 2번 설명 후에도 혼란이면 재분석
                else:
                    state["action_repeat_count"] = action_repeat_count + 1
                    return "next_step"
            
            # 다음 단계 진행
            if next_actions and len(next_actions) > 0:
                return "next_step"
            
            return "complete"
            
        except Exception as e:
            self.logger.error(f"Error in action routing: {e}")
            return "complete"
    
    def _route_after_verification(self, state: VictimState) -> Literal["continue", "success", "problem"]:
        """검증 후 라우팅"""
        
        try:
            last_message = self._get_last_user_message(state)
            
            success_keywords = ["성공", "완료됐", "해결됐", "잘 됐", "처리됐"]
            problem_keywords = ["실패", "안 됐", "문제가", "막혔", "오류"]
            
            if any(keyword in last_message for keyword in success_keywords):
                return "success"
            elif any(keyword in last_message for keyword in problem_keywords):
                return "problem"
            else:
                # 명확하지 않으면 계속 진행
                return "continue"
                
        except Exception as e:
            self.logger.error(f"Error in verification routing: {e}")
            return "success"  # 에러 시 성공으로 간주
    
    # ========================================================================
    # 메인 처리 함수들
    # ========================================================================
    
    async def process_user_input(self, state: VictimState, user_input: str) -> VictimState:
        """
        사용자 입력 처리 - LLM 통합 지점
        """
        
        try:
            # 입력 유효성 검사
            if not user_input or not user_input.strip():
                return self._handle_empty_input(state)
            
            # 사용자 메시지 추가
            state = self._add_user_message(state, user_input)
            
            # LLM 사전 처리 (선택적)
            if self.use_llm:
                state = await self._llm_preprocess(state, user_input)
            
            # 상태 업데이트
            state = self._update_state_metadata(state)
            
            # LangGraph 실행
            if self.debug:
                self.logger.debug(f"Processing input: {user_input[:100]}...")
                self.logger.debug(f"Current state: {state['current_step']}")
            
            result = await self.graph.ainvoke(state)
            
            # LLM 후처리 (선택적)
            if self.use_llm:
                result = await self._llm_postprocess(result)
            
            # 최종 상태 검증
            result = self._validate_final_state(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing user input: {e}")
            return self._handle_processing_error(state, str(e))
    
    async def start_new_conversation(self, session_id: str = None) -> VictimState:
        """새로운 상담 시작"""
        
        if not session_id:
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        initial_state = create_initial_state(session_id)
        
        # 인사말 실행
        try:
            result = await self.graph.ainvoke(initial_state)
            return result
        except Exception as e:
            self.logger.error(f"Error starting conversation: {e}")
            return self._handle_processing_error(initial_state, str(e))
    
    async def get_conversation_summary(self, state: VictimState) -> str:
        """상담 요약 생성"""
        
        try:
            messages = state.get("messages", [])
            scam_type = state.get("scam_type", "미분류")
            urgency = state.get("urgency_level", 5)
            completed_actions = state.get("completed_actions", [])
            estimated_damage = state.get("estimated_damage")
            
            summary = f"""=== 보이스피싱 상담 요약 ===
세션 ID: {state['session_id']}
상담 시작: {state['conversation_start'].strftime('%Y-%m-%d %H:%M:%S')}
현재 단계: {state['current_step']}

피해 유형: {scam_type}
긴급도: {urgency}/10
예상 피해액: {self._format_amount(estimated_damage)}

완료된 조치: {', '.join(completed_actions) if completed_actions else '없음'}
대화 턴 수: {state.get('conversation_turns', 0)}

위험 요소:
- 송금 여부: {'예' if state.get('money_transferred') else '아니오'}
- 개인정보 노출: {'예' if state.get('personal_info_exposed') else '아니오'}
- 악성앱 설치: {'예' if state.get('malicious_app_installed') else '아니오'}

현재 위험도: {state.get('current_risk_score', 3)}/10
==========================="""
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating summary: {e}")
            return f"요약 생성 중 오류 발생: {e}"
    
    # ========================================================================
    # LLM 통합 준비 - 확장 포인트
    # ========================================================================
    
    async def _llm_preprocess(self, state: VictimState, user_input: str) -> VictimState:
        """
        LLM을 이용한 사전 처리
        - 감정 상태 분석
        - 의도 파악
        - 핵심 정보 추출
        """
        
        try:
            # TODO: OpenAI/Claude API 호출
            # 예시 구조:
            """
            prompt = f'''
            보이스피싱 상담 전문가로서 다음 사용자 입력을 분석하세요:
            
            사용자 입력: {user_input}
            현재 상황: {state.get('scam_type', '미분류')}
            긴급도: {state.get('urgency_level', 5)}/10
            
            다음 항목들을 JSON 형태로 분석해주세요:
            1. emotional_state: 감정 상태 (panic, anger, confusion, relief, calm, anxiety)
            2. urgency_indicators: 긴급성 지표들
            3. key_information: 추출된 핵심 정보
            4. action_required: 필요한 조치들
            5. confidence_score: 분석 신뢰도 (0-1)
            '''
            
            llm_response = await llm_client.generate(prompt)
            llm_analysis = json.loads(llm_response)
            
            # LLM 분석 결과를 상태에 반영
            state["llm_analysis"] = llm_analysis
            state["emotional_state"] = llm_analysis.get("emotional_state", ["calm"])
            
            # 긴급도 재조정
            if llm_analysis.get("urgency_indicators"):
                current_urgency = state.get("urgency_level", 5)
                llm_urgency = len(llm_analysis["urgency_indicators"])
                state["urgency_level"] = min(10, max(current_urgency, llm_urgency + 3))
            """
            
            # 현재는 플레이스홀더
            if self.debug:
                self.logger.debug("LLM preprocessing (placeholder)")
                
        except Exception as e:
            self.logger.error(f"LLM preprocessing error: {e}")
        
        return state
    
    async def _llm_postprocess(self, state: VictimState) -> VictimState:
        """
        LLM을 이용한 후처리
        - 응답 개선
        - 톤 조정
        - 개인화
        """
        
        try:
            # TODO: 응답 개선 로직
            if self.debug:
                self.logger.debug("LLM postprocessing (placeholder)")
                
        except Exception as e:
            self.logger.error(f"LLM postprocessing error: {e}")
            
        return state
    
    # ========================================================================
    # 유틸리티 및 헬퍼 함수들
    # ========================================================================
    
    def _get_last_user_message(self, state: VictimState) -> str:
        """마지막 사용자 메시지 추출"""
        
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "").lower()
        return ""
    
    def _add_user_message(self, state: VictimState, user_input: str) -> VictimState:
        """사용자 메시지 추가"""
        
        message = {
            "role": "user",
            "content": user_input.strip(),
            "timestamp": datetime.now(),
            "metadata": {
                "length": len(user_input),
                "word_count": len(user_input.split())
            }
        }
        
        state["messages"].append(message)
        state["last_activity"] = datetime.now()
        state["conversation_turns"] += 1
        
        return state
    
    def _update_state_metadata(self, state: VictimState) -> VictimState:
        """상태 메타데이터 업데이트"""
        
        # 위험도 재계산
        state["current_risk_score"] = calculate_risk_score(state)
        
        # 응답 시간 계산
        if len(state["messages"]) >= 2:
            last_two = state["messages"][-2:]
            if len(last_two) == 2:
                time_diff = (last_two[1]["timestamp"] - last_two[0]["timestamp"]).total_seconds()
                current_avg = state.get("response_time", 0)
                turns = state.get("conversation_turns", 1)
                state["response_time"] = (current_avg * (turns - 1) + time_diff) / turns
        
        return state
    
    def _validate_final_state(self, state: VictimState) -> VictimState:
        """최종 상태 검증"""
        
        try:
            # 필수 필드 확인
            required_fields = ["session_id", "current_step", "messages"]
            for field in required_fields:
                if field not in state:
                    self.logger.warning(f"Missing required field: {field}")
                    state[field] = self._get_default_value(field)
            
            # 범위 검증
            if state.get("urgency_level", 0) > 10:
                state["urgency_level"] = 10
            elif state.get("urgency_level", 0) < 1:
                state["urgency_level"] = 1
            
            if state.get("current_risk_score", 0) > 10:
                state["current_risk_score"] = 10
            elif state.get("current_risk_score", 0) < 1:
                state["current_risk_score"] = 1
                
        except Exception as e:
            self.logger.error(f"State validation error: {e}")
        
        return state
    
    def _handle_empty_input(self, state: VictimState) -> VictimState:
        """빈 입력 처리"""
        
        state["messages"].append({
            "role": "assistant",
            "content": "죄송합니다. 메시지가 전달되지 않았습니다. 다시 말씀해 주시겠어요?",
            "timestamp": datetime.now(),
            "metadata": {"type": "error_response"}
        })
        
        return state
    
    def _handle_processing_error(self, state: VictimState, error_msg: str) -> VictimState:
        """처리 오류 핸들링"""
        
        error_response = """시스템에 일시적인 문제가 발생했습니다. 

🚨 긴급한 경우 즉시 연락하세요:
• 전기통신금융사기 통합신고센터: 1566-1188
• 경찰 신고: 112

💬 잠시 후 다시 시도해 주시거나, 위 번호로 직접 연락해 주세요."""
        
        state["messages"].append({
            "role": "assistant", 
            "content": error_response,
            "timestamp": datetime.now(),
            "metadata": {
                "type": "error_response",
                "error": error_msg
            }
        })
        
        state["current_step"] = "error_occurred"
        
        return state
    
    def _get_default_value(self, field: str):
        """기본값 반환"""
        
        defaults = {
            "session_id": f"recovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "current_step": "greeting",
            "messages": [],
            "urgency_level": 5,
            "current_risk_score": 3
        }
        
        return defaults.get(field)
    
    def _format_amount(self, amount) -> str:
        """금액 포맷팅"""
        
        if not amount:
            return "확인 필요"
        
        try:
            amount = int(amount)
            if amount >= 100000000:  # 1억 이상
                return f"{amount // 100000000}억 {(amount % 100000000) // 10000}만원"
            elif amount >= 10000:  # 1만원 이상
                return f"{amount // 10000}만원"
            else:
                return f"{amount:,}원"
        except (ValueError, TypeError):
            return "확인 필요"
    
    def _analyze_message_complexity(self, message: str) -> float:
        """메시지 복잡도 분석 (0-1)"""
        
        word_count = len(message.split())
        sentence_count = len([s for s in message.split('.') if s.strip()])
        question_count = message.count('?')
        
        if word_count < 5:
            return 0.2
        elif word_count > 50:
            return 0.9
        else:
            base_complexity = min(0.8, word_count / 30)
            question_factor = min(0.2, question_count * 0.1)
            sentence_factor = min(0.2, sentence_count / 10)
            
            return base_complexity + question_factor + sentence_factor

# ========================================================================
# 사용 예시 및 테스트 함수들
# ========================================================================

async def demo_conversation():
    """실제 대화 시나리오 테스트"""
    
    print("=== 보이스피싱 상담 워크플로우 데모 ===\n")
    
    # 그래프 초기화 (LLM 없이 시작, 디버그 모드)
    graph = VoicePhishingGraph(use_llm=False, debug=True)
    
    # 새 상담 시작
    print("1. 새 상담 시작...")
    state = await graph.start_new_conversation()
    print(f"초기 상태: {state['current_step']}")
    print(f"마지막 메시지: {state['messages'][-1]['content'][:100]}...\n")
    
    # 시나리오 1: 긴급 상황
    print("2. 긴급 상황 시나리오")
    user_input_1 = "도와주세요! 은행에서 전화가 와서 300만원을 보냈는데 사기당한 것 같아요!"
    
    state = await graph.process_user_input(state, user_input_1)
    print(f"처리 후 단계: {state['current_step']}")
    print(f"긴급도: {state['urgency_level']}/10")
    print(f"위험도: {state['current_risk_score']}/10")
    if state['messages']:
        print(f"시스템 응답: {state['messages'][-1]['content'][:200]}...\n")
    
    # 시나리오 2: 추가 정보 제공
    print("3. 추가 정보 제공")
    user_input_2 = "그런데 앱도 설치했어요. 어떡하죠?"
    
    state = await graph.process_user_input(state, user_input_2)
    print(f"업데이트된 단계: {state['current_step']}")
    print(f"업데이트된 긴급도: {state['urgency_level']}/10")
    print(f"완료된 조치: {state.get('completed_actions', [])}")
    if state['messages']:
        print(f"시스템 응답: {state['messages'][-1]['content'][:200]}...\n")
    
    # 시나리오 3: 조치 완료 확인
    print("4. 조치 완료 확인")
    user_input_3 = "112에 신고했고 지급정지 신청 완료했습니다"
    
    state = await graph.process_user_input(state, user_input_3)
    print(f"최종 단계: {state['current_step']}")
    print(f"완료된 조치: {state.get('completed_actions', [])}")
    if state['messages']:
        print(f"시스템 응답: {state['messages'][-1]['content'][:200]}...\n")
    
    # 상담 요약 출력
    print("5. 상담 요약")
    summary = await graph.get_conversation_summary(state)
    print(summary)

async def test_routing_logic():
    """라우팅 로직 테스트"""
    
    print("=== 라우팅 로직 테스트 ===\n")
    
    graph = VoicePhishingGraph(use_llm=False, debug=True)
    
    # 테스트 케이스들
    test_cases = [
        {
            "name": "긴급 상황 - 송금 완료",
            "input": "돈을 보냈는데 사기당한 것 같아요",
            "expected_urgency": 8,
            "expected_route": "emergency"
        },
        {
            "name": "일반 상담 - 의심 상황",
            "input": "이상한 전화가 왔는데 사기인지 궁금해요",
            "expected_urgency": 5,
            "expected_route": "normal"
        },
        {
            "name": "정보 부족 - 불명확",
            "input": "네",
            "expected_urgency": 3,
            "expected_route": "unclear"
        },
        {
            "name": "복잡한 상황 - 전문가 필요",
            "input": "몇 달째 계속 여러 사람한테서 연락이 와서 너무 복잡해서 이해를 못하겠어요",
            "expected_urgency": 7,
            "expected_route": "escalate"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"{i}. {test_case['name']}")
        
        # 새 상태 생성
        state = create_initial_state(f"test_{i}")
        state = graph._add_user_message(state, test_case['input'])
        
        # 초기 평가 실행
        state = await graph.nodes.initial_assessment_node(state)
        
        # 라우팅 결정
        route = graph._route_after_assessment(state)
        
        print(f"   입력: {test_case['input']}")
        print(f"   예상 긴급도: {test_case['expected_urgency']}, 실제: {state['urgency_level']}")
        print(f"   예상 라우팅: {test_case['expected_route']}, 실제: {route}")
        print(f"   테스트 결과: {'✅ 통과' if route == test_case['expected_route'] else '❌ 실패'}\n")

async def test_error_handling():
    """에러 핸들링 테스트"""
    
    print("=== 에러 핸들링 테스트 ===\n")
    
    graph = VoicePhishingGraph(use_llm=False, debug=True)
    
    # 빈 입력 테스트
    print("1. 빈 입력 테스트")
    state = create_initial_state("error_test")
    result = await graph.process_user_input(state, "")
    print(f"결과: {result['messages'][-1]['content'][:100]}...\n")
    
    # 매우 긴 입력 테스트
    print("2. 매우 긴 입력 테스트")
    long_input = "사기 " * 1000  # 매우 긴 입력
    result = await graph.process_user_input(state, long_input)
    print(f"처리 완료: {len(result['messages'])} 메시지\n")
    
    # 잘못된 상태 테스트
    print("3. 잘못된 상태 복구 테스트")
    corrupted_state = {"session_id": "corrupted"}  # 필수 필드 누락
    recovered_state = graph._validate_final_state(corrupted_state)
    print(f"복구된 필드: {list(recovered_state.keys())}\n")

async def benchmark_performance():
    """성능 벤치마크"""
    
    print("=== 성능 벤치마크 ===\n")
    
    graph = VoicePhishingGraph(use_llm=False, debug=False)
    
    # 연속 처리 성능 테스트
    test_inputs = [
        "안녕하세요",
        "대출 관련 전화가 왔어요", 
        "앱을 설치하라고 하더라고요",
        "계좌번호를 알려달라고 했어요",
        "이상해서 연락드려요"
    ]
    
    start_time = datetime.now()
    
    state = await graph.start_new_conversation("benchmark")
    
    for i, user_input in enumerate(test_inputs):
        step_start = datetime.now()
        state = await graph.process_user_input(state, user_input)
        step_time = (datetime.now() - step_start).total_seconds()
        print(f"단계 {i+1} 처리 시간: {step_time:.3f}초")
    
    total_time = (datetime.now() - start_time).total_seconds()
    print(f"\n총 처리 시간: {total_time:.3f}초")
    print(f"평균 응답 시간: {total_time/len(test_inputs):.3f}초")
    print(f"메시지 수: {len(state['messages'])}")
    print(f"최종 상태: {state['current_step']}")

class VoicePhishingGraphManager:
    """
    워크플로우 매니저 클래스
    - 다중 세션 관리
    - 세션 상태 지속성
    - 통계 및 모니터링
    """
    
    def __init__(self, use_llm: bool = False, max_sessions: int = 100):
        self.use_llm = use_llm
        self.max_sessions = max_sessions
        self.active_sessions = {}
        self.session_stats = {}
        self.global_stats = {
            "total_sessions": 0,
            "completed_sessions": 0,
            "emergency_cases": 0,
            "escalated_cases": 0,
            "avg_conversation_length": 0
        }
    
    async def create_session(self, session_id: str = None) -> str:
        """새 세션 생성"""
        
        if not session_id:
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        if len(self.active_sessions) >= self.max_sessions:
            # 가장 오래된 세션 제거
            oldest_session = min(self.active_sessions.keys(), 
                               key=lambda x: self.active_sessions[x]['last_activity'])
            await self.close_session(oldest_session)
        
        # 새 그래프 인스턴스 생성
        graph = VoicePhishingGraph(use_llm=self.use_llm, debug=False)
        state = await graph.start_new_conversation(session_id)
        
        self.active_sessions[session_id] = {
            "graph": graph,
            "state": state,
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }
        
        self.session_stats[session_id] = {
            "start_time": datetime.now(),
            "message_count": 0,
            "urgency_peaks": [],
            "routing_history": []
        }
        
        self.global_stats["total_sessions"] += 1
        
        return session_id
    
    async def process_message(self, session_id: str, user_input: str) -> dict:
        """세션에서 메시지 처리"""
        
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session_data = self.active_sessions[session_id]
        graph = session_data["graph"]
        state = session_data["state"]
        
        # 이전 단계 저장
        previous_step = state.get("current_step")
        previous_urgency = state.get("urgency_level", 5)
        
        # 메시지 처리
        updated_state = await graph.process_user_input(state, user_input)
        
        # 세션 데이터 업데이트
        session_data["state"] = updated_state
        session_data["last_activity"] = datetime.now()
        
        # 통계 업데이트
        stats = self.session_stats[session_id]
        stats["message_count"] += 1
        stats["routing_history"].append({
            "from": previous_step,
            "to": updated_state.get("current_step"),
            "timestamp": datetime.now()
        })
        
        # 긴급도 변화 추적
        current_urgency = updated_state.get("urgency_level", 5)
        if current_urgency != previous_urgency:
            stats["urgency_peaks"].append({
                "from": previous_urgency,
                "to": current_urgency,
                "timestamp": datetime.now()
            })
        
        # 글로벌 통계 업데이트
        if updated_state.get("urgency_level", 0) >= 8:
            self.global_stats["emergency_cases"] += 1
        
        if updated_state.get("current_step") == "escalated":
            self.global_stats["escalated_cases"] += 1
        
        # 응답 준비
        last_message = updated_state["messages"][-1] if updated_state["messages"] else None
        
        return {
            "session_id": session_id,
            "response": last_message["content"] if last_message else "",
            "current_step": updated_state.get("current_step"),
            "urgency_level": updated_state.get("urgency_level"),
            "risk_score": updated_state.get("current_risk_score"),
            "conversation_complete": updated_state.get("current_step") in ["consultation_complete", "escalated"],
            "metadata": {
                "message_count": stats["message_count"],
                "conversation_duration": (datetime.now() - stats["start_time"]).total_seconds()
            }
        }
    
    async def close_session(self, session_id: str) -> dict:
        """세션 종료 및 요약"""
        
        if session_id not in self.active_sessions:
            return {"error": "Session not found"}
        
        session_data = self.active_sessions[session_id]
        stats = self.session_stats[session_id]
        
        # 세션 요약 생성
        summary = await session_data["graph"].get_conversation_summary(session_data["state"])
        
        # 세션 통계
        duration = (datetime.now() - stats["start_time"]).total_seconds()
        
        session_summary = {
            "session_id": session_id,
            "duration_seconds": duration,
            "message_count": stats["message_count"],
            "final_step": session_data["state"].get("current_step"),
            "max_urgency": max([peak["to"] for peak in stats["urgency_peaks"]] + [5]),
            "routing_changes": len(stats["routing_history"]),
            "summary": summary
        }
        
        # 글로벌 통계 업데이트
        if session_data["state"].get("current_step") in ["consultation_complete", "escalated"]:
            self.global_stats["completed_sessions"] += 1
        
        # 평균 대화 길이 업데이트
        current_avg = self.global_stats["avg_conversation_length"]
        total_sessions = self.global_stats["total_sessions"]
        self.global_stats["avg_conversation_length"] = (current_avg * (total_sessions - 1) + stats["message_count"]) / total_sessions
        
        # 세션 제거
        del self.active_sessions[session_id]
        del self.session_stats[session_id]
        
        return session_summary
    
    def get_active_sessions(self) -> list:
        """활성 세션 목록"""
        
        return [
            {
                "session_id": sid,
                "created_at": data["created_at"],
                "last_activity": data["last_activity"],
                "current_step": data["state"].get("current_step"),
                "message_count": self.session_stats[sid]["message_count"]
            }
            for sid, data in self.active_sessions.items()
        ]
    
    def get_global_statistics(self) -> dict:
        """전체 통계 조회"""
        
        return {
            **self.global_stats,
            "active_sessions_count": len(self.active_sessions),
            "timestamp": datetime.now()
        }

# ========================================================================
# 메인 실행부
# ========================================================================

if __name__ == "__main__":
    import asyncio
    
    async def main():
        """메인 실행 함수"""
        
        print("🛡️ 보이스피싱 상담 워크플로우 시스템")
        print("=" * 50)
        
        # 기본 데모 실행
        await demo_conversation()
        
        print("\n" + "=" * 50)
        
        # 라우팅 로직 테스트
        await test_routing_logic()
        
        print("\n" + "=" * 50)
        
        # 에러 핸들링 테스트
        await test_error_handling()
        
        print("\n" + "=" * 50)
        
        # 성능 벤치마크
        await benchmark_performance()
        
        print("\n" + "=" * 50)
        
        # 매니저 테스트
        print("=== 세션 매니저 테스트 ===\n")
        
        manager = VoicePhishingGraphManager(use_llm=False)
        
        # 세션 생성
        session_id = await manager.create_session()
        print(f"세션 생성: {session_id}")
        
        # 메시지 처리
        test_messages = [
            "안녕하세요",
            "사기 의심 전화가 왔어요",
            "300만원 송금하라고 하더라고요"
        ]
        
        for msg in test_messages:
            result = await manager.process_message(session_id, msg)
            print(f"처리 결과: {result['current_step']}, 긴급도: {result['urgency_level']}")
        
        # 세션 종료
        summary = await manager.close_session(session_id)
        print(f"세션 요약: {summary['message_count']}개 메시지, {summary['duration_seconds']:.1f}초")
        
        # 전체 통계
        stats = manager.get_global_statistics()
        print(f"전체 통계: {stats}")
        
        print("\n✅ 모든 테스트 완료!")
    
    # 비동기 실행
    asyncio.run(main())

# import pprint

# def stream_graph(inputs, config, exclude_node=[]):
#     for output in graph.stream(inputs, config, stream_mode="updates"):
#         for k, v in output.items():
#             if k not in exclude_node:
#                 pprint.pprint(f"Output from node '{k}':")
#                 pprint.pprint("---")
#                 pprint.pprint(v, indent=2, width=80, depth=None)
#         pprint.pprint("\n---\n")
# # Case 1.
# config = {"configurable": {"thread_id": "1"}}
# inputs = {"messages": [("user", "제가 지금 사기를 당한거 같은데 진짜 죽고싶어요! 어떻게 해야 될까요? 정말 너무 힘들어요")]}

# stream_graph(inputs, config)