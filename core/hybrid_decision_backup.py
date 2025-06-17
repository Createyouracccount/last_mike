"""
하이브리드 의사결정 엔진
언제 Gemini를 사용할지 판단하는 모듈
"""

import logging

logger = logging.getLogger(__name__)

class HybridDecisionEngine:
    """
    언제 Gemini를 쓸지 판단하는 엔진
    - 룰 기반으로 해결 안되는 경우 감지
    - 사용자 의도 파악 필요 시점 감지
    - 맞춤형 설명 필요 시점 감지
    """
    
    def __init__(self):
        # 룰 기반으로 처리 가능한 패턴들
        self.rule_patterns = {
            "emergency_keywords": ["돈", "송금", "보냈", "이체", "급해", "사기", "당했"],
            "help_requests": ["도와", "도움", "알려", "방법"],
            "yes_no": ["네", "예", "아니", "싫어", "안해"],
            "simple_questions": ["뭐예요", "어디예요", "언제", "얼마"]
        }
        
        # Gemini가 필요한 상황들
        self.gemini_triggers = {
            "context_mismatch": [
                "말고", "아니라", "다른", "또 다른", "추가로", "그리고",
                "구체적으로", "자세히", "어떻게", "왜"
            ],
            "explanation_needed": [
                "뭐예요", "무엇", "어떤", "설명", "의미", "뜻",
                "어디예요", "누구", "언제", "왜", "어떻게"
            ],
            "dissatisfaction": [
                "아니", "다시", "다른", "더", "또", "별로", "부족",
                "이해 안", "모르겠", "헷갈"
            ],
            "complex_situation": [
                "그런데", "하지만", "그리고", "또한", "게다가",
                "복잡", "여러", "동시에", "한번에"
            ]
        }
        
        # 대화 히스토리 분석용
        self.conversation_patterns = {
            "repeated_questions": [],
            "user_frustration_indicators": [],
            "context_switches": []
        }
    
    def should_use_gemini(self, user_input: str, conversation_history: list, 
                         last_ai_response: str = None) -> dict:
        """Gemini 사용 여부 및 이유 판단"""
        
        decision = {
            "use_gemini": False,
            "confidence": 0.0,
            "reasons": [],
            "fallback_rule": None
        }
        
        # 1. 컨텍스트 불일치 감지
        context_score = self._detect_context_mismatch(user_input, last_ai_response)
        if context_score > 0.7:
            decision["use_gemini"] = True
            decision["reasons"].append(f"컨텍스트 불일치 (점수: {context_score:.2f})")
        
        # 2. 설명 요청 감지
        explanation_score = self._detect_explanation_request(user_input)
        if explanation_score > 0.5:  # 
            decision["use_gemini"] = True
            decision["reasons"].append(f"설명 요청 감지 (점수: {explanation_score:.2f})")
        
        # 3. 사용자 불만족 감지
        dissatisfaction_score = self._detect_dissatisfaction(user_input, conversation_history)
        if dissatisfaction_score > 0.5:
            decision["use_gemini"] = True
            decision["reasons"].append(f"사용자 불만족 (점수: {dissatisfaction_score:.2f})")
        
        # 4. 반복 질문 감지
        repetition_score = self._detect_repetition(user_input, conversation_history)
        if repetition_score > 0.4:  # 0.5 → 0.4로 낮춤
            decision["use_gemini"] = True
            decision["reasons"].append(f"반복 질문 (점수: {repetition_score:.2f})")
        
        # 5. 복잡한 상황 감지
        complexity_score = self._detect_complexity(user_input)
        if complexity_score > 0.5:  # 0.6 → 0.5로 낮춤
            decision["use_gemini"] = True
            decision["reasons"].append(f"복잡한 상황 (점수: {complexity_score:.2f})")
        
        # 최종 신뢰도 계산
        decision["confidence"] = max(context_score, explanation_score, 
                                   dissatisfaction_score, repetition_score, complexity_score)
        
        # 룰 기반 폴백 준비
        if not decision["use_gemini"]:
            decision["fallback_rule"] = self._suggest_rule_fallback(user_input)
        
        return decision
    
    # 왜 이렇게 했는가? : Gemini API를 지속적으로 호출하면 긴급한 사람들에게 기다리는 시간이 늘어나니까
    def _detect_context_mismatch(self, user_input: str, last_ai_response: str) -> float:
        """컨텍스트 불일치 감지"""
        
        if not last_ai_response:
            return 0.0
        
        user_lower = user_input.lower()
        score = 0.0
        
        # "말고", "아니라" 등 반박 표현
        contradiction_words = ["말고", "아니라", "다른", "또 다른", "추가로"]
        for word in contradiction_words:
            if word in user_lower:
                score += 0.3
        
        # 예시: "예방방법 말고 사후 대처 방법"
        if "예방" in last_ai_response and "예방" in user_input and "말고" in user_input:
            score += 0.5
        
        # AI가 질문했는데 사용자가 다른 얘기
        if "?" in last_ai_response and not any(word in user_lower for word in ["네", "예", "아니", "싫어"]):
            score += 0.2
        
        return min(score, 1.0)
    
    def _detect_explanation_request(self, user_input: str) -> float:
        """설명 요청 감지 - 더 민감하게"""
        
        user_lower = user_input.lower()
        score = 0.0
        
        # 직접적인 질문 패턴
        question_patterns = [
            "뭐예요", "무엇", "어떤", "설명", "의미", "뜻",
            "어디예요", "누구", "언제", "왜", "어떻게",
            "뭘", "뭔", "무슨", "어느",  # 기존
            "해야", "하면", "방법", "어디서"  # 추가: 행동 질문
        ]
        
        for pattern in question_patterns:
            if pattern in user_lower:
                score += 0.4
        
        # "무엇을 해야" 패턴 강화
        if "무엇" in user_input and "해야" in user_input:
            score += 0.5
        
        # "뭘 해야", "어떻게 해야" 패턴
        if "해야" in user_input and any(word in user_lower for word in ["뭘", "어떻게", "무엇"]):
            score += 0.5
        
        # "132번이 어디예요?" - 구체적 정보 요청
        if any(num in user_input for num in ["132", "1811"]) and "어디" in user_lower:
            score += 0.6
        
        # "예방 설정이 뭐예요?" - 용어 설명 요청
        if "설정" in user_input and any(word in user_lower for word in ["뭐", "뭘", "무엇"]):
            score += 0.5
        
        # "~이 뭘 말하는 걸까요?" 패턴
        if "말하는" in user_input and any(word in user_lower for word in ["뭘", "무엇", "어떤"]):
            score += 0.6
        
        return min(score, 1.0)
    
    def _detect_dissatisfaction(self, user_input: str, conversation_history: list) -> float:
        """사용자 불만족 감지"""
        
        user_lower = user_input.lower()
        score = 0.0
        
        # 불만족 표현 (더 많이 추가)
        dissatisfaction_words = [
            "아니", "다시", "다른", "더", "또", "별로", "부족",
            "그런", "정말", "진짜", "제대로"  # 추가
        ]
        for word in dissatisfaction_words:
            if word in user_lower:
                score += 0.2
        
        # 강한 불만족 표현
        strong_dissatisfaction = [
            "아니 그런", "정말 도움 안", "진짜 도움 안", "제대로 도움 안", "제발 제대로 이해", "멍청한", "이럴거면 다른",
        ]
        for phrase in strong_dissatisfaction:
            if phrase in user_lower:
                score += 0.4
        
        # "이해 안되", "모르겠" 등
        confusion_phrases = ["이해 안", "모르겠", "헷갈", "잘 모르", "뭐라고", "무슨 말", "이해를 못"]
        for phrase in confusion_phrases:
            if phrase in user_lower:
                score += 0.4
        
        # 같은 주제 반복 질문
        if len(conversation_history) >= 2:
            recent_topics = [msg.get("content", "") for msg in conversation_history[-2:]]
            if any("132" in topic for topic in recent_topics) and "132" in user_input:
                score += 0.3  # 같은 주제 반복
        
        return min(score, 1.0)
    
    def _detect_repetition(self, user_input: str, conversation_history: list) -> float:
        """반복 질문 감지"""
        
        if len(conversation_history) < 2:
            return 0.0
        
        score = 0.0
        user_lower = user_input.lower()
        
        # 최근 대화에서 유사한 키워드 찾기
        recent_user_messages = [
            msg.get("content", "").lower() 
            for msg in conversation_history[-3:] 
            if msg.get("role") == "user"
        ]
        
        for recent_msg in recent_user_messages:
            # 공통 키워드 수 계산
            user_keywords = set(user_lower.split())
            recent_keywords = set(recent_msg.split())
            common_keywords = user_keywords.intersection(recent_keywords)
            
            if len(common_keywords) >= 2:  # 2개 이상 공통 키워드
                score += 0.3
        
        return min(score, 1.0)
    
    def _detect_complexity(self, user_input: str) -> float:
        """복잡한 상황 감지"""
        
        user_lower = user_input.lower()
        score = 0.0
        
        # 긴 문장 (50자 이상)
        if len(user_input) > 50:
            score += 0.2
        
        # 복잡성 지시어
        complexity_words = ["그런데", "하지만", "그리고", "또한", "게다가", "복잡", "여러", "동시에"]
        for word in complexity_words:
            if word in user_lower:
                score += 0.3
        
        # 다중 질문 ("그리고 다른 방법 더 있을까요")
        if "그리고" in user_lower and ("?" in user_input or "까요" in user_input):
            score += 0.4
        
        return min(score, 1.0)
    
    def _suggest_rule_fallback(self, user_input: str) -> str:
        """룰 기반 폴백 제안"""
        
        user_lower = user_input.lower()
        
        # 긴급 키워드 감지
        if any(word in user_lower for word in ["돈", "송금", "급해", "사기"]):
            return "emergency_response"
        
        # 도움 요청
        if any(word in user_lower for word in ["도와", "도움", "알려"]):
            return "help_guidance"
        
        # 연락처 문의
        if any(word in user_lower for word in ["132", "1811", "번호", "연락"]):
            return "contact_info"
        
        return "general_guidance"

# 실제 사용 예시 (테스트용)
def analyze_conversation_log():
    """로그 분석 예시"""
    
    decision_engine = HybridDecisionEngine()
    
    # 실제 로그 상황들 분석
    test_cases = [
        {
            "user_input": "예방방법 말고 사후 대처 방법에 대해 알려주세요",
            "last_ai_response": "상황을 파악했습니다. 예방 방법을 알려드릴게요.",
            "expected": "컨텍스트 불일치 → Gemini 필요"
        },
        {
            "user_input": "예방 설정이 뭐예요",
            "last_ai_response": "예방 설정 해보실까요?",
            "expected": "설명 요청 → Gemini 필요"
        },
        {
            "user_input": "132번이 어디예요",
            "last_ai_response": "궁금한 게 있으면 132번으로 전화하세요.",
            "expected": "구체적 정보 요청 → Gemini 필요"
        },
        {
            "user_input": "네 받아볼래요",
            "last_ai_response": "무료 상담 받아보실래요?",
            "expected": "단순 답변 → 룰 기반 충분"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        decision = decision_engine.should_use_gemini(
            case["user_input"], 
            [], 
            case["last_ai_response"]
        )
        
        print(f"\n=== 테스트 {i} ===")
        print(f"입력: {case['user_input']}")
        print(f"예상: {case['expected']}")
        print(f"판단: {'Gemini 필요' if decision['use_gemini'] else '룰 기반 충분'}")
        print(f"신뢰도: {decision['confidence']:.2f}")
        print(f"이유: {', '.join(decision['reasons'])}")

if __name__ == "__main__":
    analyze_conversation_log()