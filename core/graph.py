#수정완료 - 완전 정리

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

class DamageAssessmentFlow:
    """
    체계적인 보이스피싱 피해 단계 체크리스트
    - 단계별 질문-답변 방식
    - 사용자 응답 기록
    - 최종 권장사항 제공
    """
    
    def __init__(self):
        # 피해 단계 체크리스트 (순서대로)
        self.damage_checklist = [
            {
                "id": "victim_status",
                "question": "본인이 피해자인가요? 네 혹은 아니요라고 답해주세요.",
                "type": "yes_no",
                "critical": True
            },
            {
                "id": "account_freeze",
                "question": "계좌지급정지신청하셨나요? 네 혹은 아니요라고 답해주세요.",
                "type": "yes_no",
                "critical": True,
                "urgent_if_no": True
            },
            {
                "id": "police_report",
                "question": "112신고는 하셨나요? 네 혹은 아니요라고 답해주세요.",
                "type": "yes_no",
                "critical": True,
                "urgent_if_no": True
            },
            {
                "id": "bank_visit",
                "question": "은행에 직접 방문하셨나요? 네 혹은 아니요라고 답해주세요.",
                "type": "yes_no",
                "critical": True
            },
            {
                "id": "damage_amount",
                "question": "피해 금액이 얼마인가요? 구체적인 금액을 말씀해주세요.",
                "type": "amount",
                "critical": False
            },
            {
                "id": "damage_time",
                "question": "언제 피해를 당하셨나요? 오늘, 어제, 며칠전 등으로 답해주세요.",
                "type": "time",
                "critical": True,
                "urgent_if": ["오늘", "어제", "방금", "몇시간전"]
            },
            {
                "id": "scammer_contact",
                "question": "사기범과 연락이 계속 오고 있나요? 네 혹은 아니요라고 답해주세요.",
                "type": "yes_no",
                "critical": False
            },
            {
                "id": "additional_accounts",
                "question": "다른 계좌나 카드도 위험할 수 있나요? 네 혹은 아니요라고 답해주세요.",
                "type": "yes_no",
                "critical": False
            },
            {
                "id": "family_safety",
                "question": "가족들도 안전한가요? 네 혹은 아니요라고 답해주세요.",
                "type": "yes_no",
                "critical": False
            }
        ]
        
        # 응답 기록
        self.user_responses = {}
        self.current_step = 0
        self.assessment_complete = False
        
        # 긴급 상황 플래그
        self.urgent_actions_needed = []
        self.critical_missing = []

    def get_next_question(self) -> str:
        """다음 질문 가져오기"""
        if self.current_step >= len(self.damage_checklist):
            self.assessment_complete = True
            return self._generate_final_assessment()
        
        question_data = self.damage_checklist[self.current_step]
        return question_data["question"]

    def process_answer(self, user_answer: str) -> str:
        """사용자 답변 처리하고 다음 질문 또는 결과 반환"""
        if self.assessment_complete:
            return "평가가 이미 완료되었습니다."
        
        current_question = self.damage_checklist[self.current_step]
        processed_answer = self._process_user_answer(user_answer, current_question)
        
        # 답변 기록
        self.user_responses[current_question["id"]] = {
            "raw_answer": user_answer,
            "processed_answer": processed_answer,
            "question": current_question["question"]
        }
        
        # 긴급 상황 체크
        self._check_urgent_situation(current_question, processed_answer)
        
        # 다음 단계로
        self.current_step += 1
        
        # 긴급 상황이면 즉시 조치 안내
        if self._is_immediate_action_needed():
            return self._get_immediate_action_guide()
        
        # 다음 질문 또는 최종 평가
        return self.get_next_question()
    
    def _process_user_answer(self, user_answer: str, question_data: dict) -> dict:
        """사용자 답변 처리"""
        answer_lower = user_answer.lower().strip()
        
        if question_data["type"] == "yes_no":
            if any(word in answer_lower for word in ["네", "예", "응", "맞", "했", "그래"]):
                return {"type": "yes", "confidence": 0.9}
            elif any(word in answer_lower for word in ["아니", "안", "못", "없", "안했"]):
                return {"type": "no", "confidence": 0.9}
            else:
                return {"type": "unclear", "confidence": 0.3}
                
        elif question_data["type"] == "amount":
            # 금액 추출 시도
            numbers = re.findall(r'\d+', user_answer)
            if numbers:
                amount = int(numbers[0])
                if "만" in user_answer:
                    amount *= 10000
                elif "억" in user_answer:
                    amount *= 100000000
                return {"type": "amount", "value": amount, "text": user_answer}
            return {"type": "amount", "value": None, "text": user_answer}
            
        elif question_data["type"] == "time":
            time_urgency = 0
            if any(word in answer_lower for word in ["오늘", "방금", "지금", "몇시간"]):
                time_urgency = 3
            elif any(word in answer_lower for word in ["어제", "하루"]):
                time_urgency = 2
            elif any(word in answer_lower for word in ["이틀", "사흘", "며칠"]):
                time_urgency = 1
            
            return {"type": "time", "urgency": time_urgency, "text": user_answer}
        
        return {"type": "text", "text": user_answer}

    def _check_urgent_situation(self, question_data: dict, processed_answer: dict):
        """긴급 상황 체크"""
        question_id = question_data["id"]
        
        # 중요한 단계를 안 했을 때
        if (question_data.get("urgent_if_no") and 
            processed_answer.get("type") == "no"):
            self.urgent_actions_needed.append(question_id)
        
        # 시간이 급할 때
        if (question_data.get("urgent_if") and 
            processed_answer.get("type") == "time" and 
            processed_answer.get("urgency", 0) >= 2):
            self.urgent_actions_needed.append("time_critical")
        
        # 중요한 정보가 없을 때
        if (question_data.get("critical") and 
            processed_answer.get("confidence", 0) < 0.5):
            self.critical_missing.append(question_id)

    def _is_immediate_action_needed(self) -> bool:
        """즉시 조치가 필요한지 확인"""
        # 계좌지급정지나 112신고를 안 했을 때
        critical_actions = ["account_freeze", "police_report"]
        return any(action in self.urgent_actions_needed for action in critical_actions)

    def _get_immediate_action_guide(self) -> str:
        """즉시 조치 안내"""
        if "account_freeze" in self.urgent_actions_needed:
            return "🚨 긴급! 지금 즉시 계좌지급정지신청하세요! 은행에 전화하거나 인터넷뱅킹에서 가능합니다. 그 다음 질문을 계속하겠습니다."
        
        if "police_report" in self.urgent_actions_needed:
            return "🚨 긴급! 지금 즉시 112번으로 신고하세요! 신고 후 다음 질문을 계속하겠습니다."
        
        return "긴급 상황이 감지되었습니다. 전문가 상담이 필요합니다."

    def _generate_final_assessment(self) -> str:
        """최종 평가 및 권장사항 생성"""
        if not self.user_responses:
            return "평가를 위한 정보가 부족합니다."
        
        # 완료된 조치들
        completed_actions = []
        missing_actions = []
        
        # 기본 체크
        if self.user_responses.get("account_freeze", {}).get("processed_answer", {}).get("type") == "yes":
            completed_actions.append("✅ 계좌지급정지 완료")
        else:
            missing_actions.append("❌ 계좌지급정지 필요")
        
        if self.user_responses.get("police_report", {}).get("processed_answer", {}).get("type") == "yes":
            completed_actions.append("✅ 112신고 완료")
        else:
            missing_actions.append("❌ 112신고 필요")
        
        if self.user_responses.get("bank_visit", {}).get("processed_answer", {}).get("type") == "yes":
            completed_actions.append("✅ 은행 방문 완료")
        else:
            missing_actions.append("❌ 은행 직접 방문 필요")
        
        # 피해 규모 파악
        damage_info = ""
        amount_data = self.user_responses.get("damage_amount", {}).get("processed_answer", {})
        if amount_data.get("value"):
            damage_info = f"\n💰 피해 금액: {amount_data['value']:,}원"
        
        time_data = self.user_responses.get("damage_time", {}).get("processed_answer", {})
        if time_data.get("text"):
            damage_info += f"\n⏰ 피해 시점: {time_data['text']}"
        
        # 최종 메시지 구성
        result = "📋 피해 단계 평가 완료\n\n"
        
        if completed_actions:
            result += "✅ 완료된 조치:\n" + "\n".join(completed_actions) + "\n\n"
        
        if missing_actions:
            result += "❗ 필요한 조치:\n" + "\n".join(missing_actions) + "\n\n"
        
        result += damage_info
        
        # 다음 단계 권장
        if missing_actions:
            result += "\n\n🎯 우선순위: " + missing_actions[0].replace("❌ ", "")
        else:
            result += "\n\n🎉 기본 조치는 모두 완료되었습니다!"
        
        result += "\n\n더 자세한 상담이 필요하시면 132번으로 연락하세요."
        
        return result

    def get_progress_status(self) -> dict:
        """진행 상황 반환"""
        return {
            "current_step": self.current_step,
            "total_steps": len(self.damage_checklist),
            "completion_rate": (self.current_step / len(self.damage_checklist)) * 100,
            "urgent_actions": self.urgent_actions_needed,
            "responses_count": len(self.user_responses),
            "is_complete": self.assessment_complete
        }

    def reset(self):
        """평가 초기화"""
        self.user_responses = {}
        self.current_step = 0
        self.assessment_complete = False
        self.urgent_actions_needed = []
        self.critical_missing = []


class VoiceFriendlyPhishingGraph:
    """
    음성 친화적 보이스피싱 상담 AI 두뇌 - 완전 버전
    - 모든 AI 로직 담당
    - conversation_manager의 단일 인터페이스 제공
    - 응답 길이 대폭 단축 (50-100자)
    - 한 번에 하나씩만 안내
    - 즉시 실행 가능한 조치 중심
    - 실질적 도움 제공
    """
    
    def __init__(self, debug: bool = True):
        self.debug = debug
        self.graph = self._build_voice_friendly_graph()

        # 🆕 conversation_manager 인터페이스용 상태
        self.current_state = None
        self.session_id = None

        # 🆕 피해 평가 시스템 추가
        self.damage_assessment = None
        self.conversation_mode = "normal"  # "normal" 또는 "assessment"

        # 하이브리드 기능 초기화 (안전하게)
        try:
            # hybrid_decision.py가 services에 있는지 확인
            from services.hybrid_decision2 import HybridDecisionEngine
            self.decision_engine = HybridDecisionEngine()
            self.use_gemini = self._check_gemini_available()
            if self.debug:
                print("✅ 하이브리드 모드 초기화 완료")
        except ImportError:
            try:
                # 기존 위치에서도 시도
                from core.hybrid_decision import HybridDecisionEngine
                self.decision_engine = HybridDecisionEngine()
                self.use_gemini = self._check_gemini_available()
                if self.debug:
                    print("✅ 하이브리드 모드 초기화 완료 (기존 위치)")
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

    def _detect_mode_selection(self, user_input: str) -> str:
        """사용자가 1번/2번 중 선택했는지 감지"""
        user_lower = user_input.lower().strip()
        
        if any(pattern in user_lower for pattern in ["1번", "1", "첫번째", "피해단계", "체크"]):
            return "assessment"
        elif any(pattern in user_lower for pattern in ["2번", "2", "두번째", "상담", "대화"]):
            return "normal"
        
        return "unknown"

    # ========================================================================
    # 🆕 conversation_manager용 메인 인터페이스
    # ========================================================================

    async def process_user_input(self, user_input: str) -> str:
        """
        🎯 conversation_manager의 메인 인터페이스 - 모드 선택 지원
        모든 AI 로직이 여기에 집중됨
        """
        try:
            if self.debug:
                print(f"🧠 AI 처리 시작: {user_input}")
            
            # 1. 입력 전처리
            processed_input = self._preprocess_user_input(user_input)
            
            if not processed_input:
                return "다시 말씀해 주세요."
            
            # 2. 🆕 모드 선택 확인 (첫 대화일 때)
            if not self.current_state:
                mode = self._detect_mode_selection(processed_input)
                
                if mode == "assessment":
                    self.conversation_mode = "assessment"
                    self.damage_assessment = DamageAssessmentFlow()
                    await self._initialize_conversation_state()
                    
                    first_question = self.damage_assessment.get_next_question()
                    if self.debug:
                        print(f"📋 체크리스트 모드 시작: {first_question}")
                    
                    return "📋 피해 단계 체크리스트를 시작합니다.\n\n" + first_question
                
                elif mode == "normal":
                    self.conversation_mode = "normal"
                    await self._initialize_conversation_state()
                    
                    if self.debug:
                        print("💬 일반 상담 모드 시작")
                    
                    # 기존 대화 방식으로 계속 진행 (아래 로직 사용)
                    
                elif mode == "unknown":
                    # 모드 선택 안내 (첫 대화에서만)
                    return """어떤 도움이 필요하신가요?

1번: 피해 단계 체크리스트 (단계별 확인)
2번: 일반 상담 (대화형)

1번 또는 2번이라고 말씀해주세요."""
            
            # 3. 🆕 평가 모드 처리
            if self.conversation_mode == "assessment" and self.damage_assessment:
                if self.damage_assessment.assessment_complete:
                    # 평가 완료 후에는 일반 모드로 전환
                    self.conversation_mode = "normal"
                    return "평가가 완료되었습니다. 추가 질문이 있으시면 말씀해주세요."
                else:
                    # 평가 계속 진행
                    result = self.damage_assessment.process_answer(processed_input)
                    if self.debug:
                        print(f"📋 체크리스트 진행: {result[:50]}...")
                    return result

            # 4. 기존 일반 모드 처리
            if self._is_meaningless_input(processed_input):
                return "보이스피싱 상담입니다. 구체적으로 어떤 도움이 필요하신지 말씀해 주세요."
            
            if not self.current_state:
                await self._initialize_conversation_state()
            
            # 5. 기존 continue_conversation 호출
            updated_state = await self.continue_conversation(
                self.current_state, 
                processed_input
            )
            
            # 6. 최신 AI 응답 추출
            if updated_state and updated_state.get('messages'):
                last_message = updated_state['messages'][-1]
                if last_message.get('role') == 'assistant':
                    response = last_message['content']
                    
                    # 응답 길이 제한 (음성 친화적)
                    if len(response) > 80:
                        response = response[:77] + "..."
                    
                    self.current_state = updated_state
                    
                    if self.debug:
                        print(f"🧠 AI 응답 완료: {response}")
                    
                    return response
            
            # 7. 폴백 응답
            if self.debug:
                print("⚠️ AI 응답 없음 - 폴백 사용")
            return "132번으로 상담받으세요."
            
        except Exception as e:
            if self.debug:
                print(f"❌ AI 처리 오류: {e}")
            logger.error(f"AI 처리 오류: {e}")
            return "일시적 문제가 발생했습니다. 132번으로 연락주세요."

    async def _initialize_conversation_state(self):
        """대화 상태 초기화"""
        if not self.session_id:
            self.session_id = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.current_state = await self.start_conversation(self.session_id)
        
        if self.debug:
            print(f"🧠 AI 상태 초기화: {self.session_id}")

    def _preprocess_user_input(self, text: str) -> str:
        """사용자 입력 전처리"""
        if not text:
            return ""
        
        corrections = {
            "지금정지": "지급정지",
            "지금 정지": "지급정지", 
            "보이스 비싱": "보이스피싱",
            "보이스비싱": "보이스피싱",
            "브이스 비싱": "보이스피싱",
            "일삼이": "132", 
            "일팔일일": "1811",
            "명의 도용": "명의도용",
            "계좌 이체": "계좌이체",
            "사기 신고": "사기신고"
        }

        processed = text.strip()
        for wrong, correct in corrections.items():
            processed = processed.replace(wrong, correct)
        
        return processed

    def _is_meaningless_input(self, text: str) -> bool:
        """의미없는 입력 감지"""
        if not text:
            return True
            
        text_lower = text.lower().strip()
        
        # 의미없는 패턴들
        meaningless_patterns = ["안먹", "안했", "못했", "아무거나", "몰라", "그냥"]
        
        if any(pattern in text_lower for pattern in meaningless_patterns):
            return True
        
        if len(text_lower) < 2:
            return True
        
        # 짧은 단어 필터링 (모드 선택 제외)
        short_words = ['네', '예', '응', '어', '음']
        if text.strip() in short_words and self.conversation_mode != "assessment":
            return True
        
        return False

    def get_initial_greeting(self) -> str:
        """초기 인사 메시지 - 모드 선택 포함"""
        return """안녕하세요. 보이스피싱 상담센터입니다.

어떤 도움이 필요하신가요?

1번: 피해 단계 체크리스트 (단계별 확인)
2번: 일반 상담 (대화형)

1번 또는 2번이라고 말씀해주세요."""

    def get_farewell_message(self) -> str:
        """마무리 인사 메시지"""
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
        if self.conversation_mode == "assessment" and self.damage_assessment:
            return self.damage_assessment.assessment_complete
        
        # 기존 종료 조건들
        if self.current_state.get('current_step') == 'consultation_complete':
            return True
        
        conversation_turns = self.current_state.get('conversation_turns', 0)
        if conversation_turns >= 8:
            return True
        
        return False

    def get_assessment_status(self) -> dict:
        """평가 진행 상황 조회"""
        if self.damage_assessment:
            return self.damage_assessment.get_progress_status()
        return {"assessment_active": False}

    async def cleanup(self):
        """AI 정리 작업"""
        try:
            if self.debug:
                print("🧠 AI 두뇌 정리 중...")
            
            # 대화 요약 로그
            if self.current_state:
                summary = self.get_conversation_summary(self.current_state)
                if self.debug:
                    print("🧠 AI 대화 요약:")
                    for key, value in summary.items():
                        print(f"   {key}: {value}")
            
            # 상태 초기화
            self.current_state = None
            self.session_id = None
            self.damage_assessment = None
            self.conversation_mode = "normal"
            
            if self.debug:
                print("✅ AI 두뇌 정리 완료")
                
        except Exception as e:
            if self.debug:
                print(f"❌ AI 정리 오류: {e}")
            logger.error(f"AI 정리 오류: {e}")

    # ========================================================================
    # 그래프 구성 및 노드들
    # ========================================================================

    def _check_gemini_available(self) -> bool:
        """Gemini 사용 가능 여부 확인"""
        try:
            from services.gemini_assistant import gemini_assistant
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
        workflow.add_node("greeting", self._greeting_node)              
        workflow.add_node("urgency_check", self._urgency_check_node)    
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
            }
        )
        
        workflow.add_conditional_edges(
            "action_guide",
            self._route_after_action,
            {
                "action_guide": "action_guide",  
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
        """모드 선택이 포함된 인사"""
        
        if state.get("greeting_done", False):
            return state
        
        # 🆕 모드 선택 포함 인사
        greeting_message = """안녕하세요. 보이스피싱 상담센터입니다.

어떤 도움이 필요하신가요?

1번: 피해 단계 체크리스트 (단계별 확인)
2번: 일반 상담 (대화형)

1번 또는 2번이라고 말씀해주세요."""

        state["messages"].append({
            "role": "assistant",
            "content": greeting_message,
            "timestamp": datetime.now()
        })
        
        state["current_step"] = "greeting_complete"
        state["greeting_done"] = True
        state["action_step_index"] = 0
        
        if self.debug:
            print("✅ 모드 선택 인사 완료")
        
        return state
    
    def _urgency_check_node(self, state: VictimRecoveryState) -> VictimRecoveryState:
        """긴급도 빠른 판단"""
        
        last_message = self._get_last_user_message(state)
        
        if not last_message:
            urgency_level = 5
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
            response = "상황을 파악했습니다. 예방 방법을 알려드릴게요."
        
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
        if urgency_level >= 5:  
            return "action_guide"
        else:
            return "complete"

    def _route_after_action(self, state: VictimRecoveryState) -> Literal["action_guide", "contact_info", "complete"]:
        if state.get("actions_complete", False):
            return "contact_info"
        elif state.get("action_step_index", 0) >= 2:  
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
    # 메인 인터페이스 (기존 유지)
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
            
            from services.gemini_assistant import gemini_assistant
            
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
                timeout=4.0
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