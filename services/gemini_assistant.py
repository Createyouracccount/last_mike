"""
최적화된 Gemini 어시스턴트 - SOLID 원칙 적용
- 단일 책임: 복잡한 사용자 질문에 대한 맞춤형 응답 생성만 담당
- 개방-폐쇄: 새로운 응답 전략 추가 가능
- 의존 역전: 추상화된 응답 전략 인터페이스 사용
"""

import asyncio
import logging
import json
import re
from datetime import datetime
from typing import Dict, Any, Optional, Protocol
from abc import ABC, abstractmethod

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("google-generativeai 패키지가 설치되지 않음")

from config.settings import settings

logger = logging.getLogger(__name__)

# ============================================================================
# 응답 전략 인터페이스 (SOLID - 인터페이스 분리 원칙)
# ============================================================================

class IResponseStrategy(Protocol):
    """응답 전략 인터페이스"""
    def generate_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        """프롬프트 생성"""
        ...
    
    def validate_response(self, response: str) -> bool:
        """응답 검증"""
        ...

# ============================================================================
# 구체적인 응답 전략들 (전략 패턴)
# ============================================================================

class ExplanationStrategy:
    """설명 요청 전략"""
    
    def generate_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        return f"""사용자가 설명을 요청했습니다: "{user_input}"

다음 중 해당하는 내용을 80자 이내로 명확하게 설명하세요:

1. 132번 → 대한법률구조공단 무료 법률상담
2. 1811-0041번 → 보이스피싱제로 생활비 지원 (최대 300만원)
3. PASS 앱 → 명의도용방지서비스 신청
4. mSAFER → 휴대폰 명의도용 차단 서비스
5. 지급정지 → 사기 계좌로의 송금 차단

JSON 형식으로 응답: {{"response": "80자 이내 설명"}}"""
    
    def validate_response(self, response: str) -> bool:
        """설명 응답 검증"""
        return (len(response) <= 80 and 
                any(keyword in response for keyword in ["132", "1811", "PASS", "mSAFER", "지급정지"]))

class AlternativeStrategy:
    """대안 요청 전략"""
    
    def generate_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        # ▼▼▼▼▼▼▼▼▼▼▼▼▼ 이 메서드 전체를 교체하세요 ▼▼▼▼▼▼▼▼▼▼▼▼▼
        last_ai_response = context.get("last_ai_response", "없음")
        
        return f"""사용자가 다른 방법을 요청했습니다: "{user_input}"
AI의 이전 답변은 "{last_ai_response}" 이었습니다.
이전 답변과 겹치지 않는 새로운 해결책을 80자 이내로 제시하고, 사용자가 궁금해할 만한 다음 질문을 제안하세요.
JSON 형식으로 응답: {{"response": "80자 이내 대안 제시", "next_suggestion": "사용자가 다음으로 물어볼 만한 질문"}}"""

    
    def validate_response(self, response: str) -> bool:
        """대안 응답 검증"""
        return (len(response) <= 80 and
                any(keyword in response for keyword in ["대신", "다른", "또는", "방법"]))

class ClarificationStrategy:
    """명확화 요청 전략"""
    
    def generate_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        return f"""사용자의 말이 명확하지 않습니다: "{user_input}"

상황을 파악하기 위한 구체적인 질문을 80자 이내로 하세요:

보이스피싱 상담 맥락에서:
- 현재 상황이 무엇인지
- 어떤 도움이 필요한지
- 피해를 당했는지 예방하려는지

친근하고 도움이 되는 톤으로 질문하세요.

JSON 형식으로 응답: {{"response": "80자 이내 명확화 질문"}}"""
    
    def validate_response(self, response: str) -> bool:
        """명확화 응답 검증"""
        return (len(response) <= 80 and 
                ("?" in response or "까요" in response))

# ============================================================================
# 최적화된 Gemini 어시스턴트 (SOLID 원칙 적용)
# ============================================================================

class OptimizedGeminiAssistant:
    """
    최적화된 Gemini 보이스피싱 상담 어시스턴트
    - 명확한 단일 책임: 복잡한 질문에 대한 맞춤형 응답 생성
    - 빠른 응답 (3초 이내)
    - 80자 이내 제한
    - 실용적 도움 중심
    """
    
    def __init__(self):
        self.is_enabled = False
        self.model = None
        
        # Gemini 초기화
        if GEMINI_AVAILABLE and settings.GEMINI_API_KEY:
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.model = genai.GenerativeModel(
                    model_name=settings.GEMINI_MODEL,
                    generation_config={
                        "temperature": 0.2,  # 일관된 응답
                        "top_p": 0.8,
                        "top_k": 20,
                        "max_output_tokens": 150,  # 응답 길이 제한
                    }
                )
                self.is_enabled = True
                logger.info("✅ 최적화된 Gemini 초기화 완료")
            except Exception as e:
                logger.error(f"❌ Gemini 초기화 실패: {e}")
                self.is_enabled = False
        else:
            logger.warning("❌ Gemini 사용 불가 - API 키 없음 또는 라이브러리 없음")
        
        # 응답 전략들 (전략 패턴)
        self.strategies = {
            "explanation": ExplanationStrategy(),
            "alternative": AlternativeStrategy(),
            "clarification": ClarificationStrategy()
        }
        
        # 기본 시스템 프롬프트
        self.base_prompt = """당신은 보이스피싱 전문 상담원입니다.

규칙:
1. 80자 이내로 핵심만 간결하게 응답합니다.
2. 사용자가 다음에 무엇을 물어보면 좋을지 "next_suggestion"으로 항상 제안합니다.
3. 반드시 아래 JSON 형식으로만 응답합니다.

{
  "response": "사용자 질문에 대한 핵심 답변 (80자 이내)",
  "next_suggestion": "사용자가 다음으로 궁금해할 만한 질문 (예: 지원금 신청 방법)"
}"""
        
        # 성능 통계
        self.stats = {
            "total_requests": 0,
            "successful_responses": 0,
            "timeouts": 0,
            "validation_failures": 0
        }
    
    async def analyze_and_respond(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """메인 분석 및 응답 생성"""
        
        self.stats["total_requests"] += 1
        
        if not self.is_enabled:
            return self._create_fallback_response(user_input, "gemini_disabled")
        
        if not context:
            context = {}
        
        try:
            # 1. 상황 분류
            situation_type = self._classify_situation(user_input)
            
            # 2. 적절한 전략 선택
            strategy = self._select_strategy(situation_type)
            
            # 3. 프롬프트 생성
            prompt = self._build_prompt(strategy, user_input, context)
            
            # 4. Gemini 호출 (타임아웃 적용)
            response = await asyncio.wait_for(
                self._call_gemini(prompt),
                timeout=3.0
            )
            
            # 5. 응답 검증 및 후처리
            validated_response = self._validate_and_enhance(response, strategy, user_input)
            
            self.stats["successful_responses"] += 1
            return validated_response
            
        except asyncio.TimeoutError:
            self.stats["timeouts"] += 1
            logger.warning("Gemini 타임아웃 - 폴백 응답")
            return self._create_fallback_response(user_input, "timeout")
        except Exception as e:
            logger.error(f"Gemini 처리 오류: {e}")
            return self._create_fallback_response(user_input, "error")
    
    def _classify_situation(self, user_input: str) -> str:
        """상황 분류"""
        
        if not user_input or len(user_input.strip()) < 3:
            return "unclear"
        
        user_lower = user_input.lower()
        
        # 설명 요청
        explanation_indicators = [
            "뭐예요", "무엇", "어떤", "설명", "의미", "뜻",
            "어디예요", "누구", "언제", "어떻게", "왜"
        ]
        if any(indicator in user_lower for indicator in explanation_indicators):
            return "explanation"
        
        # 대안 요청
        alternative_indicators = [
            "말고", "다른", "또", "추가", "대신", "아니라"
        ]
        if any(indicator in user_lower for indicator in alternative_indicators):
            return "alternative"
        
        # 불만족/명확화 필요
        dissatisfaction_indicators = [
            "이해 안", "모르겠", "헷갈", "어려워", "복잡해"
        ]
        if any(indicator in user_lower for indicator in dissatisfaction_indicators):
            return "clarification"
        
        return "general"
    
    def _select_strategy(self, situation_type: str) -> IResponseStrategy:
        """전략 선택"""
        
        if situation_type in self.strategies:
            return self.strategies[situation_type]
        
        # 기본값: 명확화 전략
        return self.strategies["clarification"]
    
    def _build_prompt(self, strategy: IResponseStrategy, user_input: str, context: Dict[str, Any]) -> str:
        """프롬프트 구성"""
        
        strategy_prompt = strategy.generate_prompt(user_input, context)
        
        return f"{self.base_prompt}\n\n{strategy_prompt}"
    
    async def _call_gemini(self, prompt: str) -> str:
        """Gemini API 호출"""
        
        def sync_generate():
            response = self.model.generate_content(prompt)
            return response.text
        
        # 비동기 처리
        response_text = await asyncio.to_thread(sync_generate)
        return response_text.strip()
    
    def _validate_and_enhance(self, response: str, strategy: IResponseStrategy, user_input: str) -> Dict[str, Any]:
        """응답 검증 및 강화"""
        
        # JSON 파싱 시도
        parsed_response = self._extract_json_response(response)
        
        if not parsed_response:
            self.stats["validation_failures"] += 1
            return self._create_fallback_response(user_input, "parse_error")
        
        response_text = parsed_response.get("response", "")
        
        # 기본 검증
        if not response_text or len(response_text) > 80:
            self.stats["validation_failures"] += 1
            return self._create_fallback_response(user_input, "validation_error")
        
        # 전략별 검증
        if not strategy.validate_response(response_text):
            self.stats["validation_failures"] += 1
            return self._create_fallback_response(user_input, "strategy_validation_error")
        
        # 검증 통과
        return {
            "response": response_text,
            "urgency_level": 5,
            "next_action": "continue",
            "source": "gemini_optimized"
        }
    
    def _extract_json_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """JSON 응답 추출"""
        
        # JSON 블록 패턴들
        json_patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
            r'(\{[^}]*"response"[^}]*\})',
            r'(\{.*?"response".*?\})'
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, response_text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
        
        # 직접 JSON 파싱 시도
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _create_fallback_response(self, user_input: str, reason: str) -> Dict[str, Any]:
        """폴백 응답 생성"""
        
        user_lower = user_input.lower() if user_input else ""
        
        # 상황별 폴백 응답
        if any(word in user_lower for word in ["132", "일삼이"]):
            response = "132번은 대한법률구조공단 무료 법률상담 번호입니다."
        elif any(word in user_lower for word in ["1811", "일팔일일"]):
            response = "1811-0041번은 보이스피싱제로 생활비 지원 번호입니다."
        elif any(word in user_lower for word in ["pass", "패스"]):
            response = "PASS 앱에서 명의도용방지서비스를 신청할 수 있습니다."
        elif any(word in user_lower for word in ["설명", "뭐예요", "무엇"]):
            response = "구체적으로 어떤 부분이 궁금하신지 말씀해 주세요."
        elif any(word in user_lower for word in ["말고", "다른"]):
            response = "132번 상담이나 1811-0041번 지원 신청도 가능합니다."
        else:
            response = "구체적인 상황을 말씀해 주시면 더 정확한 도움을 드릴 수 있습니다."
        
        return {
            "response": response,
            "urgency_level": 5,
            "next_action": "continue",
            "source": f"fallback_{reason}"
        }
    
    async def test_connection(self) -> bool:
        """연결 테스트"""
        
        if not self.is_enabled:
            return False
        
        try:
            test_result = await asyncio.wait_for(
                self.analyze_and_respond("테스트", {"conversation_turns": 0}),
                timeout=2.0
            )
            
            success = (test_result and 
                      isinstance(test_result, dict) and 
                      test_result.get("response"))
            
            if success:
                logger.info("✅ 최적화된 Gemini 테스트 성공")
            else:
                logger.warning("❌ Gemini 테스트 실패")
            
            return success
            
        except Exception as e:
            logger.error(f"Gemini 테스트 실패: {e}")
            return False
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 조회"""
        
        total = self.stats["total_requests"]
        if total == 0:
            return {**self.stats, "success_rate": "0%"}
        
        success_rate = (self.stats["successful_responses"] / total) * 100
        timeout_rate = (self.stats["timeouts"] / total) * 100
        validation_failure_rate = (self.stats["validation_failures"] / total) * 100
        
        return {
            **self.stats,
            "success_rate": f"{success_rate:.1f}%",
            "timeout_rate": f"{timeout_rate:.1f}%",
            "validation_failure_rate": f"{validation_failure_rate:.1f}%",
            "is_enabled": self.is_enabled
        }
    
    def add_strategy(self, name: str, strategy: IResponseStrategy):
        """새로운 전략 추가 (개방-폐쇄 원칙)"""
        self.strategies[name] = strategy
        logger.info(f"✅ 새로운 응답 전략 추가: {name}")

# ============================================================================
# 전역 인스턴스
# ============================================================================

# 최적화된 어시스턴트 인스턴스
gemini_assistant = OptimizedGeminiAssistant()

# 하위 호환성을 위한 별칭
ImprovedGeminiAssistant = OptimizedGeminiAssistant