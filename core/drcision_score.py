"""
개선된 신뢰도 계산 방법들
현재 max() 방식의 한계를 보완하는 여러 접근법
"""

import math
from typing import List, Dict, Tuple

class ImprovedConfidenceCalculator:
    """개선된 신뢰도 계산기"""
    
    def __init__(self):
        # 각 점수의 중요도 가중치
        self.weights = {
            "context_score": 0.3,      # 컨텍스트 불일치는 매우 중요
            "explanation_score": 0.25,  # 설명 요청도 중요
            "dissatisfaction_score": 0.2, # 불만족은 조금 덜 중요
            "repetition_score": 0.15,   # 반복은 보조 지표
            "complexity_score": 0.1     # 복잡성은 참고용
        }
    
    def calculate_confidence_v1_weighted_sum(self, scores: Dict[str, float]) -> float:
        """방법 1: 가중합 방식"""
        weighted_sum = sum(
            scores.get(key.replace("_score", "") + "_score", 0) * weight 
            for key, weight in self.weights.items()
        )
        return min(weighted_sum, 1.0)
    
    def calculate_confidence_v2_multiple_signals(self, scores: Dict[str, float]) -> float:
        """방법 2: 다중 신호 보너스 방식"""
        base_score = max(scores.values())
        
        # 0.3 이상인 신호의 개수
        active_signals = sum(1 for score in scores.values() if score >= 0.3)
        
        # 다중 신호 보너스 (최대 +0.3)
        bonus = min(0.3, (active_signals - 1) * 0.1)
        
        return min(base_score + bonus, 1.0)
    
    def calculate_confidence_v3_bayesian_like(self, scores: Dict[str, float]) -> float:
        """방법 3: 베이지안 스타일 (독립 사건 가정)"""
        # 각 점수를 "Gemini가 필요할 확률"로 해석
        # P(not_needed) = (1-p1) * (1-p2) * ... * (1-pn)
        # P(needed) = 1 - P(not_needed)
        
        prob_not_needed = 1.0
        for score in scores.values():
            prob_not_needed *= (1 - score)
        
        return 1.0 - prob_not_needed
    
    def calculate_confidence_v4_threshold_based(self, scores: Dict[str, float]) -> float:
        """방법 4: 임계값 기반 조합"""
        high_scores = [score for score in scores.values() if score >= 0.6]
        medium_scores = [score for score in scores.values() if 0.3 <= score < 0.6]
        
        if high_scores:
            # 높은 점수가 있으면 그것을 기준으로
            base = max(high_scores)
            # 추가 신호들로 보정
            bonus = len(medium_scores) * 0.05
            return min(base + bonus, 1.0)
        elif len(medium_scores) >= 2:
            # 중간 점수가 2개 이상이면 합산
            return min(sum(medium_scores) * 0.7, 1.0)
        else:
            # 약한 신호들만 있으면 최댓값
            return max(scores.values()) if scores.values() else 0.0
    
    def calculate_confidence_v5_smart_combination(self, scores: Dict[str, float]) -> float:
        """방법 5: 스마트 조합 (추천)"""
        context_score = scores.get("context_score", 0)
        explanation_score = scores.get("explanation_score", 0)
        dissatisfaction_score = scores.get("dissatisfaction_score", 0)
        repetition_score = scores.get("repetition_score", 0)
        complexity_score = scores.get("complexity_score", 0)
        
        # 1. 강한 신호 우선 (컨텍스트 불일치, 설명 요청)
        strong_signal = max(context_score, explanation_score)
        
        # 2. 보조 신호들 (불만족, 반복, 복잡성)
        support_signals = [dissatisfaction_score, repetition_score, complexity_score]
        support_score = sum(s for s in support_signals if s >= 0.3) * 0.3
        
        # 3. 최종 계산
        if strong_signal >= 0.7:
            # 강한 신호가 있으면 보조 신호로 약간 보정
            return min(strong_signal + support_score * 0.2, 1.0)
        elif strong_signal >= 0.4:
            # 중간 강도 신호면 보조 신호 중요하게 반영
            return min(strong_signal + support_score * 0.5, 1.0)
        else:
            # 약한 신호들만 있으면 합산하되 더 보수적으로
            total = strong_signal + support_score
            return min(total * 0.8, 1.0)

def compare_methods():
    """다양한 상황에서 각 방법 비교"""
    
    calculator = ImprovedConfidenceCalculator()
    
    test_cases = [
        {
            "name": "강한 컨텍스트 불일치만",
            "scores": {
                "context_score": 0.8,
                "explanation_score": 0.0,
                "dissatisfaction_score": 0.0,
                "repetition_score": 0.0,
                "complexity_score": 0.0
            }
        },
        {
            "name": "여러 약한 신호들",
            "scores": {
                "context_score": 0.3,
                "explanation_score": 0.4,
                "dissatisfaction_score": 0.3,
                "repetition_score": 0.3,
                "complexity_score": 0.2
            }
        },
        {
            "name": "설명 요청 + 불만족",
            "scores": {
                "context_score": 0.0,
                "explanation_score": 0.6,
                "dissatisfaction_score": 0.5,
                "repetition_score": 0.0,
                "complexity_score": 0.0
            }
        },
        {
            "name": "모든 신호 중간 정도",
            "scores": {
                "context_score": 0.5,
                "explanation_score": 0.4,
                "dissatisfaction_score": 0.4,
                "repetition_score": 0.3,
                "complexity_score": 0.3
            }
        }
    ]
    
    print("=" * 80)
    print("신뢰도 계산 방법 비교")
    print("=" * 80)
    
    for case in test_cases:
        print(f"\n📋 {case['name']}")
        print(f"   입력: {case['scores']}")
        
        # 현재 방법 (max)
        current = max(case['scores'].values())
        
        # 새로운 방법들
        v1 = calculator.calculate_confidence_v1_weighted_sum(case['scores'])
        v2 = calculator.calculate_confidence_v2_multiple_signals(case['scores'])
        v3 = calculator.calculate_confidence_v3_bayesian_like(case['scores'])
        v4 = calculator.calculate_confidence_v4_threshold_based(case['scores'])
        v5 = calculator.calculate_confidence_v5_smart_combination(case['scores'])
        
        print(f"   현재(max):     {current:.3f}")
        print(f"   가중합:        {v1:.3f}")
        print(f"   다중신호:      {v2:.3f}")
        print(f"   베이지안:      {v3:.3f}")
        print(f"   임계값기반:    {v4:.3f}")
        print(f"   스마트조합:    {v5:.3f}")

def practical_implementation():
    """실제 구현에 사용할 수 있는 개선된 버전"""
    
    def calculate_improved_confidence(self, context_score, explanation_score, 
                                    dissatisfaction_score, repetition_score, 
                                    complexity_score) -> dict:
        """개선된 신뢰도 계산 (HybridDecisionEngine에 통합할 코드)"""
        
        scores = {
            "context_score": context_score,
            "explanation_score": explanation_score,
            "dissatisfaction_score": dissatisfaction_score,
            "repetition_score": repetition_score,
            "complexity_score": complexity_score
        }
        
        # 방법 5: 스마트 조합 사용
        strong_signal = max(context_score, explanation_score)
        support_signals = [dissatisfaction_score, repetition_score, complexity_score]
        support_score = sum(s for s in support_signals if s >= 0.3) * 0.3
        
        if strong_signal >= 0.7:
            confidence = min(strong_signal + support_score * 0.2, 1.0)
            reasoning = "강한 신호 감지"
        elif strong_signal >= 0.4:
            confidence = min(strong_signal + support_score * 0.5, 1.0)
            reasoning = "중간 신호 + 보조 신호"
        else:
            total = strong_signal + support_score
            confidence = min(total * 0.8, 1.0)
            reasoning = "약한 신호들 조합"
        
        # 추가 정보 제공
        active_signals = sum(1 for score in scores.values() if score >= 0.3)
        
        return {
            "confidence": confidence,
            "reasoning": reasoning,
            "active_signals": active_signals,
            "primary_signal": max(scores, key=scores.get),
            "signal_details": scores
        }
    
    print("\n" + "=" * 60)
    print("실제 구현 예시")
    print("=" * 60)
    print(calculate_improved_confidence.__doc__)
    print("\n실제 코드:")
    print('# HybridDecisionEngine.should_use_gemini() 메서드에서:')
    print('result = self.calculate_improved_confidence(')
    print('    context_score, explanation_score,')
    print('    dissatisfaction_score, repetition_score, complexity_score')
    print(')')
    print('decision["confidence"] = result["confidence"]')
    print('decision["reasoning"] = result["reasoning"]')

if __name__ == "__main__":
    compare_methods()
    practical_implementation()