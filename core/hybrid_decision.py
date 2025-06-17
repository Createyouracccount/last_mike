"""
간소화된 하이브리드 의사결정 엔진 - SOLID 원칙 적용
- 단일 책임: 언제 Gemini를 사용할지만 결정
- 개방-폐쇄: 새로운 판단 기준 추가 가능
- 의존 역전: 추상화된 인터페이스 사용
"""

import logging
from typing import List, Dict, Any, Protocol
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# ============================================================================
# 인터페이스 정의 (SOLID - 인터페이스 분리 원칙)
# ============================================================================

class IDecisionCriteria(Protocol):
    """의사결정 기준 인터페이스"""
    def evaluate(self, user_input: str, context: Dict[str, Any]) -> float:
        """기준 평가 (0.0 ~ 1.0)"""
        ...
    
    def get_reason(self) -> str:
        """판단 이유"""
        ...

class IDecisionEngine(Protocol):
    """의사결정 엔진 인터페이스"""
    def should_use_gemini(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Gemini 사용 여부 결정"""
        ...

# ============================================================================
# 구체적인 판단 기준들 (단일 책임 원칙)
# ============================================================================

# core/hybrid_decision.py 파일을 열고 아래 내용으로 교체하세요.

class ComplexityDetector:
    """복잡성 감지기 (개선 버전)"""
    
    def __init__(self):
        self.complexity_indicators = [
            "자세히", "구체적으로", "설명", "어떻게", "왜", "뭐예요",
            "어디예요", "누구예요", "언제예요", "무슨 뜻", "의미",
            "방법", "조치", "무엇을", "어떡하죠", "궁금"  # <-- 핵심 키워드 추가
        ]
    
    def evaluate(self, user_input: str, context: Dict[str, Any]) -> float:
        """복잡성 평가"""
        if not user_input:
            return 0.0
        
        user_lower = user_input.lower()
        score = 0.0
        
        # 질문 키워드 체크
        for indicator in self.complexity_indicators:
            if indicator in user_lower:
                score += 0.4  # 점수 상향
                break # 하나만 찾아도 충분히 복잡한 질문으로 간주
        
        # 문장 길이 체크 (15자 이상이면 질문일 가능성 높음)
        if len(user_input) > 15 and "?" in user_input or "요" in user_input:
            score += 0.2
        
        return min(score, 1.0)
    
    def get_reason(self) -> str:
        return "복잡한 질문 또는 설명 요청 감지"

class ContextMismatchDetector:
    """문맥 불일치 감지기 (개선 버전)"""
    
    def __init__(self):
        self.mismatch_indicators = [
            "말고", "아니라", "다른", "그런게 아니라", "추가로", "또"
        ]
    
    def evaluate(self, user_input: str, context: Dict[str, Any]) -> float:
        """문맥 불일치 평가"""
        if not user_input:
            return 0.0
        
        user_lower = user_input.lower()
        score = 0.0
        
        # 명시적 반박 표현
        for indicator in self.mismatch_indicators:
            if indicator in user_lower:
                score += 0.6 # 점수 대폭 상향
                break

        # AI가 이전에 했던 말을 사용자가 다시 질문하는 경우 (예: "112번이요" 했는데 다시 "112번이 뭐죠?")
        last_ai_response = context.get("last_ai_response", "")
        if last_ai_response:
            if "132" in last_ai_response and "132" in user_lower and len(user_lower) > 5:
                score += 0.5
            elif "1811" in last_ai_response and "1811" in user_lower and len(user_lower) > 10:
                score += 0.5

        return min(score, 1.0)
    
    def get_reason(self) -> str:
        return "문맥 불일치 또는 이전 답변에 대한 추가 질문 감지"

class DissatisfactionDetector:
    """불만족 감지기 (개선 버전)"""
    
    def __init__(self):
        self.dissatisfaction_indicators = [
            "이해 못하겠", "모르겠", "헷갈려", "어려워", "복잡해",
            "제대로", "정확히", "확실히", "더 쉽게", "간단하게",
            "상황을 묻지 말고", "자꾸 같은 말", "답변이 이상" # <-- 사용자 불만 직접 감지
        ]
    
    def evaluate(self, user_input: str, context: Dict[str, Any]) -> float:
        """불만족 평가"""
        if not user_input:
            return 0.0
        
        user_lower = user_input.lower()
        score = 0.0
        
        # 불만족 표현 체크
        for indicator in self.dissatisfaction_indicators:
            if indicator in user_lower:
                score += 0.7  # 점수 대폭 상향
                break
        
        return min(score, 1.0)
    
    def get_reason(self) -> str:
        return "사용자 불만족 또는 재설명 요청 감지"

class EmergencyDetector:
    """응급 상황 감지기"""
    
    def __init__(self):
        self.emergency_keywords = [
            "급해", "빨리", "즉시", "당장", "긴급", "위험", "큰일"
        ]
    
    def evaluate(self, user_input: str, context: Dict[str, Any]) -> float:
        """응급 상황 평가 (응급상황은 Gemini 사용 안함)"""
        if not user_input:
            return 0.0
        
        user_lower = user_input.lower()
        
        # 응급 키워드가 있으면 Gemini 사용하지 않음 (빠른 처리 우선)
        for keyword in self.emergency_keywords:
            if keyword in user_lower:
                return -1.0  # 음수로 Gemini 사용 방지
        
        return 0.0
    
    def get_reason(self) -> str:
        return "응급 상황 - 빠른 처리 우선"

# ============================================================================
# 간소화된 의사결정 엔진 (SOLID 원칙 적용)
# ============================================================================

class SimplifiedHybridDecisionEngine:
    """
    간소화된 하이브리드 의사결정 엔진
    - 명확한 기준으로 Gemini 사용 여부 결정
    - 음성 친화적 (빠른 응답 우선)
    - 확장 가능한 구조
    """
    
    def __init__(self, debug: bool = True):
        self.debug = debug
        
        # 판단 기준들 (의존성 주입 가능)
        self.detectors = {
            "complexity": ComplexityDetector(),
            "context_mismatch": ContextMismatchDetector(),
            "dissatisfaction": DissatisfactionDetector(),
            "emergency": EmergencyDetector()
        }
        
        # 임계값 설정 (음성 친화적으로 보수적)
        self.thresholds = {
            "gemini_use_threshold": 0.6,  # 60% 이상 확신할 때만 Gemini 사용
            "emergency_block_threshold": -0.5  # 응급상황 감지시 Gemini 차단
        }
        
        # 성능 통계
        self.stats = {
            "total_decisions": 0,
            "gemini_decisions": 0,
            "rule_decisions": 0,
            "emergency_blocks": 0
        }
        
        if self.debug:
            print("✅ 간소화된 하이브리드 의사결정 엔진 초기화")
    
    def should_use_gemini(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Gemini 사용 여부 결정
        
        Returns:
            dict: {
                "use_gemini": bool,
                "confidence": float,
                "reasons": List[str],
                "detector_scores": Dict[str, float]
            }
        """
        
        self.stats["total_decisions"] += 1
        
        if not context:
            context = {}
        
        decision = {
            "use_gemini": False,
            "confidence": 0.0,
            "reasons": [],
            "detector_scores": {}
        }
        
        # 1. 기본 입력 검증
        if not user_input or len(user_input.strip()) < 3:
            decision["reasons"].append("입력이 너무 짧음")
            self.stats["rule_decisions"] += 1
            return decision
        
        # 2. 각 감지기로 평가
        total_score = 0.0
        active_detectors = []
        
        for name, detector in self.detectors.items():
            score = detector.evaluate(user_input, context)
            decision["detector_scores"][name] = score
            
            if score > 0.3:  # 의미있는 점수만 고려
                total_score += score
                active_detectors.append((name, detector, score))
                
            elif score < 0:  # 응급상황 등 차단 조건
                decision["reasons"].append(detector.get_reason())
                self.stats["emergency_blocks"] += 1
                return decision
        
        # 3. 최종 판단
        decision["confidence"] = min(total_score, 1.0)
        
        if decision["confidence"] >= self.thresholds["gemini_use_threshold"]:
            decision["use_gemini"] = True
            decision["reasons"] = [detector.get_reason() for _, detector, _ in active_detectors]
            self.stats["gemini_decisions"] += 1
            
            if self.debug:
                print(f"🤖 Gemini 사용 결정: {decision['confidence']:.2f}")
                print(f"   이유: {', '.join(decision['reasons'])}")
        else:
            decision["use_gemini"] = False
            decision["reasons"] = ["룰 기반으로 충분히 처리 가능"]
            self.stats["rule_decisions"] += 1
            
            if self.debug:
                print(f"⚡ 룰 기반 사용: {decision['confidence']:.2f}")
        
        return decision
    
    def add_detector(self, name: str, detector) -> None:
        """새로운 감지기 추가 (개방-폐쇄 원칙)"""
        self.detectors[name] = detector
        if self.debug:
            print(f"✅ 새로운 감지기 추가: {name}")
    
    def update_threshold(self, threshold_name: str, value: float) -> None:
        """임계값 업데이트"""
        if threshold_name in self.thresholds:
            self.thresholds[threshold_name] = value
            if self.debug:
                print(f"🔧 임계값 업데이트: {threshold_name} = {value}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 조회"""
        total = self.stats["total_decisions"]
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            "gemini_usage_rate": f"{(self.stats['gemini_decisions'] / total) * 100:.1f}%",
            "rule_usage_rate": f"{(self.stats['rule_decisions'] / total) * 100:.1f}%",
            "emergency_block_rate": f"{(self.stats['emergency_blocks'] / total) * 100:.1f}%"
        }
    
    def reset_stats(self) -> None:
        """통계 초기화"""
        self.stats = {
            "total_decisions": 0,
            "gemini_decisions": 0,
            "rule_decisions": 0,
            "emergency_blocks": 0
        }
        if self.debug:
            print("📊 통계 초기화 완료")

# ============================================================================
# 테스트 및 검증
# ============================================================================

def test_decision_engine():
    """의사결정 엔진 테스트"""
    
    engine = SimplifiedHybridDecisionEngine(debug=True)
    
    test_cases = [
        # 룰 기반으로 충분한 경우들
        ("네", "단순 응답"),
        ("132번", "명확한 연락처 요청"),
        ("도와주세요", "일반적인 도움 요청"),
        ("급해요 돈 보냈어요", "응급상황 - 빠른 처리 필요"),
        
        # Gemini가 도움될 경우들
        ("132번이 정확히 뭐예요?", "구체적 설명 요청"),
        ("예방 방법 말고 다른 방법 있나요?", "문맥 불일치"),
        ("이해가 잘 안 돼요. 더 쉽게 설명해주세요.", "불만족 표현"),
        ("그런데 PASS 앱은 어떻게 설치하고 어떤 기능이 있나요?", "복잡한 질문"),
        
        # 경계 케이스들
        ("", "빈 입력"),
        ("음", "의미없는 짧은 입력"),
        ("132번 말고 다른 방법도 있나요?", "문맥 불일치 + 복잡성")
    ]
    
    print("🧪 간소화된 하이브리드 의사결정 엔진 테스트")
    print("=" * 60)
    
    for user_input, expected_type in test_cases:
        decision = engine.should_use_gemini(user_input, {"conversation_turns": 2})
        
        result = "🤖 Gemini" if decision["use_gemini"] else "⚡ 룰 기반"
        confidence = decision["confidence"]
        reasons = decision["reasons"]
        
        print(f"입력: '{user_input}'")
        print(f"예상: {expected_type}")
        print(f"결과: {result} (신뢰도: {confidence:.2f})")
        if reasons:
            print(f"이유: {', '.join(reasons)}")
        print("-" * 40)
    
    # 성능 통계 출력
    print("\n📊 성능 통계:")
    stats = engine.get_performance_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    test_decision_engine()