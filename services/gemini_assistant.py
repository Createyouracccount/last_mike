# services/gemini_assistant.py 개선 버전 (수정됨)

import asyncio
import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("google-generativeai 패키지가 설치되지 않음. pip install google-generativeai")

from config.settings import settings

logger = logging.getLogger(__name__)

class ImprovedGeminiAssistant:
    """
    개선된 Gemini 보이스피싱 상담 어시스턴트
    - 의미없는 입력 처리 강화
    - 상황별 맞춤 응답 생성
    - 응답 품질 검증 강화
    - 실질적 도움 중심
    """
    
    def __init__(self):
        self.is_enabled = False
        
        # Gemini 사용 가능성 체크
        if not GEMINI_AVAILABLE:
            logger.warning("❌ Gemini 라이브러리 없음 - 구조화된 모드 사용")
            return
            
        if not settings.GEMINI_API_KEY:
            logger.warning("❌ GEMINI_API_KEY 없음 - 구조화된 모드 사용")
            return
        
        # Gemini 초기화
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                generation_config={
                    "temperature": 0.3,  # 더 일관된 응답
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 200,  # 응답 길이 제한
                }
            )
            self.is_enabled = True
            logger.info("✅ 개선된 Gemini AI 초기화 완료")
        except Exception as e:
            logger.error(f"❌ Gemini 초기화 실패: {e}")
            self.is_enabled = False
        
        # 기본 시스템 프롬프트
        self.base_system_prompt = """당신은 보이스피싱 전문 상담원입니다. 사용자의 상황에 맞는 실질적 도움을 제공하세요.

핵심 원칙:
1. 80자 이내 간결한 응답 (음성 친화적)
2. 즉시 실행 가능한 조치 안내
3. 상황별 맞춤 대응

주요 연락처:
- 132번: 대한법률구조공단 무료 법률 상담
- 1811-0041: 보이스피싱제로 생활비 지원 (최대 300만원)
- 112번: 긴급 신고

주요 서비스:
- mSAFER: 휴대폰 명의도용 차단
- PASS앱: 명의도용방지서비스 신청
- 지급정지: 사기 계좌로의 송금 차단

응답 형식: 반드시 JSON으로 응답하고, response는 80자를 절대 넘지 마세요
{"response": "80자 이내 실질적 조치 안내", "urgency_level": 1-10, "next_action": "immediate_help/expert_consultation/prevention/clarification"}"""
        
        # 대화 기록
        self.conversation_history = []
        
        # 개선된 세션 상태
        self.session_state = {
            'total_turns': 0,
            'urgency_level': 3,
            'practical_guidance_provided': False,
            'user_satisfaction_level': 5,
            'repeated_topics': [],
            'gemini_success_rate': 0.0
        }
        
        # 응답 품질 검증 기준
        self.quality_criteria = {
            'max_length': 80,
            'min_length': 10,
            'forbidden_phrases': [
                '잘 모르겠습니다', '확인이 어렵습니다', '죄송합니다',
                '도움을 드릴 수 없습니다', '정보가 부족합니다'
            ]
        }
        
        # 성공률 추적
        self.success_metrics = {
            'total_requests': 0,
            'successful_responses': 0,
            'timeout_count': 0,
            'validation_failures': 0
        }
    
    async def analyze_and_respond(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """개선된 분석 및 응답 생성"""
        
        self.success_metrics['total_requests'] += 1
        
        if not self.is_enabled:
            return self._enhanced_rule_based_fallback(user_input, context)
        
        try:
            # 상황 분류
            situation_type = self._classify_situation(user_input, context)
            
            # 상황별 맞춤 프롬프트 생성
            prompt = self._generate_situation_prompt(situation_type, user_input, context)
            
            # Gemini API 호출
            gemini_response = await self._call_gemini_with_validation(prompt, context)
            
            # 응답 후처리 및 강화
            enhanced_response = self._enhance_response_quality(gemini_response, user_input, situation_type)
            
            # 세션 상태 업데이트
            self._update_session_state(enhanced_response, situation_type)
            
            # 대화 기록 추가
            self._add_conversation_record(user_input, enhanced_response)
            
            self.success_metrics['successful_responses'] += 1
            
            return enhanced_response
            
        except asyncio.TimeoutError:
            self.success_metrics['timeout_count'] += 1
            logger.warning("Gemini 타임아웃 - 상황별 폴백 사용")
            return self._situation_based_fallback(user_input, context)
        except Exception as e:
            logger.error(f"Gemini 처리 오류: {e}")
            return self._enhanced_rule_based_fallback(user_input, context)
    
    def _classify_situation(self, user_input: str, context: Dict[str, Any] = None) -> str:
        """상황 분류"""
        
        if not user_input or len(user_input.strip()) < 2:
            return "meaningless"
        
        user_lower = user_input.lower()
        
        # 의미없는 입력 체크 (우선순위)
        meaningless_patterns = [
            "안먹", "안했", "못했", "아무거나", "몰라", "그냥",
            "어어", "음음", "아아", "네네"
        ]
        if any(pattern in user_lower for pattern in meaningless_patterns):
            return "meaningless"
        
        # 긴급 상황 체크
        emergency_keywords = ["돈", "송금", "보냈", "이체", "급해", "사기", "당했", "피해"]
        if any(keyword in user_lower for keyword in emergency_keywords):
            return "emergency"
        
        # 컨텍스트 불일치 체크
        if context and context.get('decision_reasons'):
            reasons = context['decision_reasons']
            if any("컨텍스트 불일치" in reason for reason in reasons):
                return "context_mismatch"
        
        # 설명 요청 체크
        explanation_patterns = [
            "뭐예요", "무엇", "어떤", "설명", "의미", "뜻",
            "어디예요", "누구", "언제", "왜", "어떻게"
        ]
        if any(pattern in user_lower for pattern in explanation_patterns):
            return "explanation"
        
        # 불만족 표현 체크
        dissatisfaction_patterns = [
            "아니", "다시", "다른", "더", "또", "별로", "부족",
            "이해 안", "모르겠", "헷갈", "도움 안"
        ]
        if any(pattern in user_lower for pattern in dissatisfaction_patterns):
            return "dissatisfaction"
        
        return "general"
    
    def _generate_situation_prompt(self, situation_type: str, user_input: str, context: Dict[str, Any] = None) -> str:
        """상황별 맞춤 프롬프트 생성"""
        
        base_context = ""
        if context:
            urgency = context.get('urgency_level', 5)
            turns = context.get('conversation_turns', 0)
            base_context = f"\n현재 긴급도: {urgency}/10, 대화 턴: {turns}"
        
        if situation_type == "meaningless":
            return f"""사용자가 의미없는 말을 했습니다: "{user_input}"

적절한 응답을 선택하세요:
1. 혼란스러워하는 경우: 진정시키고 구체적 설명 요청
2. 관련 없는 얘기: 보이스피싱 상담임을 명확히 하고 도움 의도 확인
3. 실수/오타: 다시 말해달라고 정중히 요청

80자 이내로 상황에 맞는 응답을 생성하세요.{base_context}"""
            
        elif situation_type == "context_mismatch":
            last_ai_response = self._get_last_ai_response()
            return f"""사용자가 이전 AI 답변과 다른 방향으로 대화하고 있습니다.

이전 AI: "{last_ai_response}"
사용자: "{user_input}"

사용자의 진짜 의도를 파악해서 도움을 주세요:
- "말고" → 다른 방법 제시
- "아니라" → 잘못 이해한 부분 수정
- 엉뚱한 답변 → 의도 재확인

80자 이내로 사용자가 원하는 대안을 제시하세요.{base_context}"""
            
        elif situation_type == "explanation":
            return f"""사용자가 구체적인 설명을 요청했습니다: "{user_input}"

요청된 내용을 명확하고 이해하기 쉽게 설명하세요:
- 132번, 1811-0041번 등 연락처의 역할
- mSAFER, PASS앱 등 서비스 기능
- 지급정지 등 전문용어의 의미
- 구체적인 이용 방법

80자 이내로 핵심만 간단명료하게 설명하세요.{base_context}"""
            
        elif situation_type == "dissatisfaction":
            return f"""사용자가 불만족을 표현했습니다: "{user_input}"

사용자의 불만을 해결할 수 있는 방법을 제시하세요:
- 더 구체적이고 실용적인 도움 방법
- 다른 연락처나 서비스 소개
- 전문가 직접 상담 연결 안내

80자 이내로 만족할 만한 대안을 제시하세요.{base_context}"""
            
        elif situation_type == "emergency":
            return f"""긴급 상황입니다: "{user_input}"

즉시 취해야 할 조치를 우선순위대로 안내하세요:
1. 긴급 신고나 차단 조치
2. 전문 상담 연결
3. 추가 피해 방지 방법

80자 이내로 가장 중요한 조치 1-2개만 명확히 안내하세요.{base_context}"""
            
        else:  # general
            return f"""사용자 질문: "{user_input}"

보이스피싱 상담 맥락에서 가장 도움이 되는 조치를 안내하세요:
- 상황에 맞는 적절한 서비스나 연락처
- 구체적이고 실행 가능한 다음 단계
- 추가 도움이 필요한 경우의 안내

80자 이내로 실질적 도움을 제공하세요.{base_context}"""
    
    async def _call_gemini_with_validation(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """검증 강화된 Gemini API 호출"""
        
        # 전체 프롬프트 구성
        full_prompt = f"{self.base_system_prompt}\n\n{prompt}"
        
        # Gemini 호출
        response = await asyncio.to_thread(
            self.model.generate_content, 
            full_prompt
        )
        
        # 응답 텍스트 정리
        response_text = response.text.strip()
        
        # JSON 추출 및 파싱
        parsed_response = self._extract_and_parse_json(response_text)
        
        # 응답 검증
        if not self._validate_response_quality(parsed_response):
            raise ValueError("응답 품질 검증 실패")
        
        return parsed_response
    
    def _extract_and_parse_json(self, response_text: str) -> Dict[str, Any]:
        """JSON 추출 및 파싱"""
        
        import re
        
        # JSON 블록 찾기
        json_patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
            r'(\{[^}]*"response"[^}]*\})',
            r'(\{.*\})'
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, response_text, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue
        
        # JSON 파싱 실패 시 텍스트에서 응답 추출
        return self._extract_response_from_text(response_text)
    
    def _extract_response_from_text(self, text: str) -> Dict[str, Any]:
        """텍스트에서 응답 추출 (JSON 실패 시)"""
        
        # 간단한 응답 추출
        lines = text.split('\n')
        response_line = ""
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('**'):
                if len(line) <= 80:  # 길이 제한 확인
                    response_line = line
                    break
        
        if not response_line:
            response_line = text[:80] + "..." if len(text) > 80 else text
        
        # 긴급도 추정
        urgency = 5
        if any(word in text.lower() for word in ['긴급', '즉시', '빨리', '당장']):
            urgency = 8
        elif any(word in text.lower() for word in ['상담', '확인', '문의']):
            urgency = 6
        
        return {
            "response": response_line,
            "urgency_level": urgency,
            "next_action": "continue"
        }
    
    def _validate_response_quality(self, response: Dict[str, Any]) -> bool:
        """응답 품질 검증"""
        
        if not response or not isinstance(response, dict):
            return False
        
        response_text = response.get("response", "")
        
        # 기본 검증
        if not response_text or len(response_text.strip()) < self.quality_criteria['min_length']:
            self.success_metrics['validation_failures'] += 1
            return False
        
        if len(response_text) > self.quality_criteria['max_length']:
            self.success_metrics['validation_failures'] += 1
            return False
        
        # 금지된 문구 체크
        for forbidden in self.quality_criteria['forbidden_phrases']:
            if forbidden in response_text:
                self.success_metrics['validation_failures'] += 1
                return False
        
        # 실질적 도움 여부 체크
        helpful_indicators = [
            "132", "1811", "PASS", "mSAFER", "신고", "상담", 
            "설정", "차단", "지원", "도움", "방법"
        ]
        
        if not any(indicator in response_text for indicator in helpful_indicators):
            self.success_metrics['validation_failures'] += 1
            return False
        
        return True
    
    def _enhance_response_quality(self, response: Dict[str, Any], user_input: str, situation_type: str) -> Dict[str, Any]:
        """응답 품질 강화"""
        
        enhanced = response.copy()
        response_text = enhanced.get("response", "")
        
        # 상황별 응답 강화
        if situation_type == "meaningless":
            if "구체적" not in response_text:
                response_text = f"구체적으로 어떤 도움이 필요하신지 말씀해 주세요."
        
        elif situation_type == "emergency":
            if "132" not in response_text and "112" not in response_text:
                response_text = f"긴급하시면 132번으로 즉시 연락하세요."
        
        elif situation_type == "explanation":
            # 설명에 구체적인 정보 포함 확인
            if not any(info in response_text for info in ["132번", "1811", "PASS", "mSAFER"]):
                if "132" in user_input:
                    response_text = "132번은 대한법률구조공단 무료 법률상담 번호입니다."
                elif "1811" in user_input:
                    response_text = "1811-0041번은 보이스피싱제로 생활비 지원 번호입니다."
        
        # 길이 재조정
        if len(response_text) > 80:
            response_text = response_text[:77] + "..."
        
        enhanced["response"] = response_text
        
        # 긴급도 조정
        if situation_type == "emergency":
            enhanced["urgency_level"] = max(enhanced.get("urgency_level", 5), 8)
        elif situation_type == "meaningless":
            enhanced["urgency_level"] = 3
        
        return enhanced
    
    def _situation_based_fallback(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """상황별 폴백 응답"""
        
        situation_type = self._classify_situation(user_input, context)
        
        fallback_responses = {
            "meaningless": {
                "response": "보이스피싱 상담입니다. 구체적으로 어떤 도움이 필요하신지 말씀해 주세요.",
                "urgency_level": 3,
                "next_action": "clarification"
            },
            "emergency": {
                "response": "긴급상황이시면 즉시 132번으로 전화하거나 112에 신고하세요.",
                "urgency_level": 9,
                "next_action": "immediate_help"
            },
            "context_mismatch": {
                "response": "다른 방법을 원하시는군요. 132번 상담이나 1811-0041번 지원 신청도 가능해요.",
                "urgency_level": 6,
                "next_action": "expert_consultation"
            },
            "explanation": {
                "response": "궁금한 내용을 구체적으로 말씀해 주시면 자세히 설명드릴게요.",
                "urgency_level": 5,
                "next_action": "clarification"
            },
            "dissatisfaction": {
                "response": "더 자세한 도움은 132번 전문상담사와 직접 통화하시는 게 좋겠어요.",
                "urgency_level": 6,
                "next_action": "expert_consultation"
            },
            "general": {
                "response": "132번으로 무료 상담받으시거나 1811-0041번으로 지원 신청하세요.",
                "urgency_level": 5,
                "next_action": "expert_consultation"
            }
        }
        
        return fallback_responses.get(situation_type, fallback_responses["general"])
    
    def _enhanced_rule_based_fallback(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """강화된 룰 기반 폴백"""
        
        if not user_input:
            return {
                "response": "다시 말씀해 주세요.",
                "urgency_level": 3,
                "next_action": "clarification"
            }
        
        user_lower = user_input.lower()
        
        # 긴급 상황 처리
        if any(word in user_lower for word in ["돈", "송금", "급해", "사기"]):
            return {
                "response": "긴급상황입니다! 즉시 132번으로 신고하고 1811-0041번으로 지원받으세요.",
                "urgency_level": 9,
                "next_action": "immediate_help"
            }
        
        # 의미없는 입력 처리
        meaningless_patterns = ["안먹", "안했", "못했", "아무거나", "몰라"]
        if any(pattern in user_lower for pattern in meaningless_patterns):
            return {
                "response": "보이스피싱 상담센터입니다. 어떤 도움이 필요하신지 구체적으로 말씀해 주세요.",
                "urgency_level": 3,
                "next_action": "clarification"
            }
        
        # 설명 요청 처리
        if any(word in user_lower for word in ["뭐예요", "어떻게", "설명"]):
            if "132" in user_input:
                return {
                    "response": "132번은 대한법률구조공단 무료 법률상담 번호입니다.",
                    "urgency_level": 5,
                    "next_action": "expert_consultation"
                }
            elif "1811" in user_input:
                return {
                    "response": "1811-0041번은 보이스피싱제로 생활비 지원 번호입니다.",
                    "urgency_level": 5,
                    "next_action": "expert_consultation"
                }
        
        # 기본 응답
        return {
            "response": "132번으로 무료상담 받으시거나 1811-0041번으로 지원 신청하세요.",
            "urgency_level": 5,
            "next_action": "expert_consultation"
        }
    
    def _get_last_ai_response(self) -> str:
        """마지막 AI 응답 가져오기"""
        
        if not self.conversation_history:
            return ""
        
        for record in reversed(self.conversation_history):
            if record.get('assistant'):
                return record['assistant']
        
        return ""
    
    def _update_session_state(self, response: Dict[str, Any], situation_type: str):
        """세션 상태 업데이트"""
        
        self.session_state['total_turns'] += 1
        self.session_state['urgency_level'] = response.get('urgency_level', 5)
        
        # 상황별 만족도 추정
        if situation_type == "meaningless":
            self.session_state['user_satisfaction_level'] = max(1, self.session_state['user_satisfaction_level'] - 1)
        elif situation_type == "dissatisfaction":
            self.session_state['user_satisfaction_level'] = max(1, self.session_state['user_satisfaction_level'] - 2)
        elif situation_type == "explanation" and len(response.get('response', '')) > 50:
            self.session_state['user_satisfaction_level'] = min(10, self.session_state['user_satisfaction_level'] + 1)
        
        # 성공률 계산
        if self.success_metrics['total_requests'] > 0:
            self.session_state['gemini_success_rate'] = (
                self.success_metrics['successful_responses'] / 
                self.success_metrics['total_requests']
            )
    
    def _add_conversation_record(self, user_input: str, response: Dict[str, Any]):
        """대화 기록 추가"""
        
        self.conversation_history.append({
            'user': user_input,
            'assistant': response.get('response', ''),
            'urgency_level': response.get('urgency_level', 5),
            'timestamp': datetime.now(),
            'source': 'gemini_improved'
        })
        
        # 최대 10개 기록만 유지
        if len(self.conversation_history) > 10:
            self.conversation_history.pop(0)
    
    def get_session_status(self) -> Dict[str, Any]:
        """세션 상태 조회"""
        
        return {
            'is_ai_enabled': self.is_enabled,
            'total_turns': self.session_state['total_turns'],
            'urgency_level': self.session_state['urgency_level'],
            'user_satisfaction_level': self.session_state['user_satisfaction_level'],
            'conversation_length': len(self.conversation_history),
            'success_rate': f"{self.session_state['gemini_success_rate'] * 100:.1f}%",
            'total_requests': self.success_metrics['total_requests'],
            'successful_responses': self.success_metrics['successful_responses'],
            'timeout_count': self.success_metrics['timeout_count'],
            'validation_failures': self.success_metrics['validation_failures']
        }
    
    async def test_connection(self) -> bool:
        """연결 테스트"""
        
        if not self.is_enabled:
            return False
        
        try:
            test_result = await self.analyze_and_respond(
                "테스트", 
                {"urgency_level": 5, "conversation_turns": 0}
            )
            
            success = (test_result and 
                      isinstance(test_result, dict) and 
                      test_result.get("response"))
            
            if success:
                logger.info("✅ 개선된 Gemini 테스트 성공")
            else:
                logger.warning("❌ Gemini 테스트 실패")
            
            return success
            
        except Exception as e:
            logger.error(f"Gemini 테스트 실패: {e}")
            return False

# 전역 인스턴스
gemini_assistant = ImprovedGeminiAssistant()