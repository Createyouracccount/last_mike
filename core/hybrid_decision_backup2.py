"""
음성 친화적 하이브리드 의사결정 엔진
언제 Gemini를 사용할지 판단하는 모듈 - 리팩토링 버전
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class HybridDecisionEngine:
    """
    언제 Gemini를 쓸지 판단하는 엔진 - 음성 대화 최적화
    - 3초 이내 응답 목표에 맞춰 Gemini 사용 최소화
    - 음성 입력 특성 반영 (짧고 불완전한 입력)
    - 리팩토링된 graph.py와 완벽 호환
    """
    
    def __init__(self, debug: bool = True):
        self.debug = debug
        
        # 🎙️ 음성 입력 특성 반영
        self.voice_patterns = {
            "short_responses": ["네", "예", "아니", "싫어", "안해", "응", "어", "음"],
            "incomplete_speech": ["어", "음", "그", "이", "아"],
            "repeated_words": []  # 동적으로 추가됨
        }
        
        # 룰 기반으로 처리 가능한 패턴들 (확장)
        self.rule_patterns = {
            "emergency_keywords": ["돈", "송금", "보냈", "이체", "급해", "사기", "당했", "피해", "도둑"],
            "help_requests": ["도와", "도움", "알려", "방법", "해야", "어떻게"],
            "yes_no": ["네", "예", "아니", "싫어", "안해", "응", "좋아", "맞아"],
            "simple_questions": ["뭐예요", "어디예요", "언제", "얼마", "누구"],
            "contact_requests": ["132", "1811", "번호", "연락", "전화"]
        }
        
        # 🔧 음성 친화적 임계값 (기존보다 더 보수적)
        self.thresholds = {
            "context_mismatch": 0.8,      # 0.7 → 0.8 (더 확실할 때만)
            "explanation_needed": 0.7,    # 0.5 → 0.7 (명확한 질문만)
            "dissatisfaction": 0.7,       # 0.5 → 0.7 (강한 불만만)
            "repetition": 0.6,            # 0.4 → 0.6 (명확한 반복만)
            "complexity": 0.8             # 0.5 → 0.8 (매우 복잡한 경우만)
        }
        
        # Gemini가 필요한 상황들 (음성 맞춤)
        self.gemini_triggers = {
            "context_mismatch": [
                "말고", "아니라", "다른거", "또 다른", "추가로", "그리고",
                "구체적으로", "자세히", "더 자세히"
            ],
            "explanation_needed": [
                "뭐예요", "무엇", "어떤", "설명해", "의미", "뜻이",
                "어디예요", "누구예요", "언제예요", "왜", "어떻게",
                "몰라서", "모르겠어서", "이해가 안돼서"
            ],
            "dissatisfaction": [
                "아니 그런게", "정말 도움 안", "진짜 모르겠", "제대로 알려",
                "이해 못하겠", "헷갈려서", "더 쉽게", "간단하게",
                "별로 도움", "그런게 아니라"
            ],
            "complex_situation": [
                "그런데 또", "하지만 추가로", "그리고 만약에", "복잡한 상황",
                "여러 가지", "동시에", "한번에"
            ]
        }
        
        # 성능 모니터링
        self.stats = {
            "total_decisions": 0,
            "gemini_calls": 0,
            "rule_based_calls": 0,
            "avg_decision_time": 0.0
        }
        
        if self.debug:
            print("✅ 음성 친화적 하이브리드 엔진 초기화")
    
    def should_use_gemini(self, user_input: str, conversation_history: List[Dict], 
                         last_ai_response: str = None) -> Dict[str, Any]:
        """
        Gemini 사용 여부 및 이유 판단 - 음성 최적화
        
        Returns:
            dict: {
                "use_gemini": bool,
                "confidence": float,
                "reasons": List[str],
                "fallback_rule": str
            }
        """
        
        import time
        start_time = time.time()
        
        self.stats["total_decisions"] += 1
        
        decision = {
            "use_gemini": False,
            "confidence": 0.0,
            "reasons": [],
            "fallback_rule": None
        }
        
        # 🎙️ 음성 입력 전처리
        processed_input = self._preprocess_voice_input(user_input)
        
        if self.debug:
            print(f"🔍 하이브리드 판단: '{processed_input}'")
        
        # 🚫 음성 특성상 즉시 룰 기반 처리해야 하는 경우들
        if self._should_use_rules_immediately(processed_input):
            decision["fallback_rule"] = self._suggest_rule_fallback(processed_input)
            decision["confidence"] = 0.1  # 매우 낮은 신뢰도
            
            if self.debug:
                print(f"⚡ 즉시 룰 기반: {decision['fallback_rule']}")
            
            self.stats["rule_based_calls"] += 1
            self._update_decision_time(start_time)
            return decision
        
        # 🔍 Gemini 필요성 분석
        scores = {}
        
        # 1. 컨텍스트 불일치 감지
        scores["context"] = self._detect_context_mismatch(processed_input, last_ai_response)
        if scores["context"] > self.thresholds["context_mismatch"]:
            decision["use_gemini"] = True
            decision["reasons"].append(f"컨텍스트 불일치 ({scores['context']:.2f})")
        
        # 2. 설명 요청 감지
        scores["explanation"] = self._detect_explanation_request(processed_input)
        if scores["explanation"] > self.thresholds["explanation_needed"]:
            decision["use_gemini"] = True
            decision["reasons"].append(f"설명 요청 ({scores['explanation']:.2f})")
        
        # 3. 사용자 불만족 감지
        scores["dissatisfaction"] = self._detect_dissatisfaction(processed_input, conversation_history)
        if scores["dissatisfaction"] > self.thresholds["dissatisfaction"]:
            decision["use_gemini"] = True
            decision["reasons"].append(f"사용자 불만족 ({scores['dissatisfaction']:.2f})")
        
        # 4. 반복 질문 감지
        scores["repetition"] = self._detect_repetition(processed_input, conversation_history)
        if scores["repetition"] > self.thresholds["repetition"]:
            decision["use_gemini"] = True
            decision["reasons"].append(f"반복 질문 ({scores['repetition']:.2f})")
        
        # 5. 복잡한 상황 감지
        scores["complexity"] = self._detect_complexity(processed_input)
        if scores["complexity"] > self.thresholds["complexity"]:
            decision["use_gemini"] = True
            decision["reasons"].append(f"복잡한 상황 ({scores['complexity']:.2f})")
        
        # 최종 신뢰도 계산
        decision["confidence"] = max(scores.values()) if scores else 0.0
        
        # 룰 기반 폴백 준비
        if not decision["use_gemini"]:
            decision["fallback_rule"] = self._suggest_rule_fallback(processed_input)
            self.stats["rule_based_calls"] += 1
        else:
            self.stats["gemini_calls"] += 1
        
        if self.debug:
            action = "Gemini 호출" if decision["use_gemini"] else "룰 기반"
            print(f"🎯 결정: {action} (신뢰도: {decision['confidence']:.2f})")
            if decision["reasons"]:
                print(f"   이유: {', '.join(decision['reasons'])}")
        
        self._update_decision_time(start_time)
        return decision
    
    def _preprocess_voice_input(self, user_input: str) -> str:
        """음성 입력 전처리"""
        if not user_input:
            return ""
        
        # 기본 정리
        processed = user_input.strip().lower()
        
        # 음성 인식 오류 교정 (간단한 것들)
        corrections = {
            "일삼이": "132",
            "일팔일일": "1811",
            "보이스비싱": "보이스피싱",
            "예방설정": "예방 설정"
        }
        
        for wrong, correct in corrections.items():
            processed = processed.replace(wrong, correct)
        
        return processed
    
    def _should_use_rules_immediately(self, user_input: str) -> bool:
        """음성 특성상 즉시 룰 기반 처리해야 하는 경우"""
        
        # 1. 매우 짧은 응답 (5자 이하)
        if len(user_input) <= 5:
            return True
        
        # 2. 단순 yes/no 응답
        if user_input in self.voice_patterns["short_responses"]:
            return True
        
        # 3. 불완전한 음성 입력
        if user_input in self.voice_patterns["incomplete_speech"]:
            return True
        
        # 4. 명확한 긴급 상황
        emergency_words = ["급해", "당했어", "돈 보냈어", "사기"]
        if any(word in user_input for word in emergency_words):
            return True
        
        # 5. 명확한 연락처 요청
        if any(word in user_input for word in ["132번", "1811번", "전화번호"]):
            return True
        
        return False
    
    def _detect_context_mismatch(self, user_input: str, last_ai_response: str) -> float:
        """컨텍스트 불일치 감지 - 음성 버전"""
        
        if not last_ai_response:
            return 0.0
        
        score = 0.0
        
        # 명확한 반박 표현만 감지
        strong_contradictions = ["말고", "아니라", "다른거로", "그런게 아니라"]
        for phrase in strong_contradictions:
            if phrase in user_input:
                score += 0.4
        
        # AI가 질문했는데 완전히 다른 답변
        if "?" in last_ai_response:
            expected_answers = ["네", "예", "아니", "싫어", "안해", "좋아"]
            if not any(answer in user_input for answer in expected_answers):
                if len(user_input) > 10:  # 긴 답변인 경우만
                    score += 0.3
        
        # 예방 vs 사후 대처 같은 명확한 대조
        if "예방" in last_ai_response and "예방 말고" in user_input:
            score += 0.5
        
        return min(score, 1.0)
    
    def _detect_explanation_request(self, user_input: str) -> float:
        """설명 요청 감지 - 더 엄격하게"""
        
        score = 0.0
        
        # 명확한 질문 패턴만
        clear_questions = [
            "뭐예요", "무엇인가요", "어떤 건가요", "설명해주세요",
            "어디예요", "누구예요", "언제예요", "왜 그런가요",
            "어떻게 하는 건가요", "무슨 뜻인가요"
        ]
        
        for question in clear_questions:
            if question in user_input:
                score += 0.5
        
        # "132번이 뭐예요?" 같은 구체적 질문
        if any(num in user_input for num in ["132", "1811"]) and "뭐" in user_input:
            score += 0.4
        
        # "어떻게 해야" + 구체적 행동
        if "어떻게 해야" in user_input and len(user_input) > 15:
            score += 0.3
        
        return min(score, 1.0)
    
    def _detect_dissatisfaction(self, user_input: str, conversation_history: List[Dict]) -> float:
        """사용자 불만족 감지 - 강한 불만만"""
        
        score = 0.0
        
        # 강한 불만족 표현만
        strong_dissatisfaction = [
            "정말 도움 안", "진짜 모르겠", "이해 못하겠",
            "별로 도움", "그런게 아니라", "제대로 알려"
        ]
        
        for phrase in strong_dissatisfaction:
            if phrase in user_input:
                score += 0.4
        
        # 연속된 "아니" 또는 "다시"
        repeated_no = ["아니 아니", "다시 다시", "아니 그런게"]
        for phrase in repeated_no:
            if phrase in user_input:
                score += 0.5
        
        return min(score, 1.0)
    
    def _detect_repetition(self, user_input: str, conversation_history: List[Dict]) -> float:
        """반복 질문 감지 - 명확한 반복만"""
        
        if len(conversation_history) < 4:  # 2 → 4 (더 긴 히스토리 필요)
            return 0.0
        
        score = 0.0
        
        # 최근 사용자 메시지들
        recent_user_messages = [
            msg.get("content", "").lower() 
            for msg in conversation_history[-4:] 
            if msg.get("role") == "user"
        ]
        
        # 동일한 핵심 키워드 3번 이상 반복
        key_words = ["132", "1811", "설정", "예방", "방법"]
        for word in key_words:
            if word in user_input:
                count = sum(1 for msg in recent_user_messages if word in msg)
                if count >= 3:
                    score += 0.4
        
        return min(score, 1.0)
    
    def _detect_complexity(self, user_input: str) -> float:
        """복잡한 상황 감지 - 매우 복잡한 경우만"""
        
        score = 0.0
        
        # 매우 긴 문장 (70자 이상)
        if len(user_input) > 70:
            score += 0.3
        
        # 복잡성 연결어 (강한 것들만)
        strong_complexity = ["그런데 또", "하지만 추가로", "그리고 만약에"]
        for phrase in strong_complexity:
            if phrase in user_input:
                score += 0.4
        
        # 다중 질문
        question_count = user_input.count("?") + user_input.count("까요")
        if question_count >= 2:
            score += 0.3
        
        return min(score, 1.0)
    
    def _suggest_rule_fallback(self, user_input: str) -> str:
        """룰 기반 폴백 제안 - 음성 최적화"""
        
        # 긴급 키워드 우선
        if any(word in user_input for word in ["돈", "송금", "급해", "사기", "당했"]):
            return "emergency_response"
        
        # 연락처 문의
        if any(word in user_input for word in ["132", "1811", "번호", "연락", "전화"]):
            return "contact_info"
        
        # 도움 요청
        if any(word in user_input for word in ["도와", "도움", "알려", "방법"]):
            return "help_guidance"
        
        # 단순 응답
        if user_input in self.voice_patterns["short_responses"]:
            return "simple_response"
        
        return "general_guidance"
    
    def _update_decision_time(self, start_time: float):
        """의사결정 시간 업데이트"""
        import time
        decision_time = time.time() - start_time
        
        current_avg = self.stats["avg_decision_time"]
        total_decisions = self.stats["total_decisions"]
        
        self.stats["avg_decision_time"] = (
            (current_avg * (total_decisions - 1) + decision_time) / total_decisions
        )
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 조회"""
        
        total = self.stats["total_decisions"]
        if total == 0:
            return self.stats
        
        gemini_rate = (self.stats["gemini_calls"] / total) * 100
        rule_rate = (self.stats["rule_based_calls"] / total) * 100
        
        return {
            **self.stats,
            "gemini_usage_rate": f"{gemini_rate:.1f}%",
            "rule_usage_rate": f"{rule_rate:.1f}%",
            "avg_decision_time_ms": f"{self.stats['avg_decision_time'] * 1000:.1f}ms"
        }

# 테스트 및 디버깅용
def test_voice_scenarios():
    """음성 시나리오 테스트"""
    
    engine = HybridDecisionEngine(debug=True)
    
    test_cases = [
        # 즉시 룰 기반 처리되어야 하는 경우들
        ("네", "단순 응답"),
        ("응", "단순 응답"),
        ("돈 보냈어요", "긴급 상황"),
        ("132번", "연락처 요청"),
        
        # Gemini 필요한 경우들
        ("예방방법 말고 사후 대처 방법", "컨텍스트 불일치"),
        ("132번이 정확히 뭐예요?", "설명 요청"),
        ("정말 도움 안되네요 다른 방법", "강한 불만족"),
        
        # 룰 기반으로 충분한 경우들  
        ("도와주세요", "일반 도움 요청"),
        ("방법 알려주세요", "일반 도움 요청"),
        ("안해요", "단순 거부")
    ]
    
    print("🧪 음성 시나리오 테스트")
    print("=" * 50)
    
    for user_input, expected in test_cases:
        decision = engine.should_use_gemini(user_input, [])
        
        result = "Gemini" if decision["use_gemini"] else "룰 기반"
        
        print(f"입력: '{user_input}'")
        print(f"예상: {expected}")
        print(f"결과: {result} (신뢰도: {decision['confidence']:.2f})")
        if decision["reasons"]:
            print(f"이유: {', '.join(decision['reasons'])}")
        print("-" * 30)
    
    # 성능 통계
    print("\n📊 성능 통계:")
    stats = engine.get_performance_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    test_voice_scenarios()