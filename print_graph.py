#!/usr/bin/env python3
"""
보이스피싱 상담 시스템 LangGraph 시각화 도구
현재 구현된 StructuredVoicePhishingGraph를 시각화
"""

import os
import sys
from datetime import datetime
from typing import Literal, Dict, Any

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 필요한 패키지 임포트
try:
    from langgraph.graph import StateGraph, START, END
    print("✅ LangGraph 임포트 성공")
except ImportError:
    print("❌ LangGraph가 설치되어 있지 않습니다.")
    print("설치 명령: pip install langgraph")
    sys.exit(1)

# 프로젝트 모듈 임포트
try:
    from core.state import VictimRecoveryState, create_initial_recovery_state
    print("✅ 프로젝트 상태 모듈 임포트 성공")
except ImportError:
    print("⚠️ 프로젝트 상태 모듈 임포트 실패 - 기본 상태 사용")
    from typing import TypedDict, List
    
    class VictimRecoveryState(TypedDict):
        session_id: str
        messages: List[Dict[str, Any]]
        current_step: str
        urgency_level: int
        conversation_turns: int

class VoicePhishingGraphVisualizer:
    """보이스피싱 상담 시스템 시각화 도구"""
    
    def __init__(self):
        self.graph = self._build_actual_graph()
        print("✅ 보이스피싱 상담 그래프 시각화 도구 초기화 완료")
    
    def _build_actual_graph(self) -> StateGraph:
        """실제 구현된 그래프 구조 재현"""
        
        workflow = StateGraph(VictimRecoveryState)
        
        # 실제 노드들 추가 (우리가 구현한 것과 동일)
        workflow.add_node("greeting", self._greeting_node)
        workflow.add_node("initial_assessment", self._initial_assessment_node)
        workflow.add_node("collect_info", self._collect_info_node)
        workflow.add_node("emergency_action", self._emergency_action_node)
        workflow.add_node("complete", self._complete_node)
        
        # 실제 엣지 구조
        workflow.add_edge(START, "greeting")
        
        workflow.add_conditional_edges(
            "greeting",
            self._route_after_greeting,
            {
                "initial_assessment": "initial_assessment",
            }
        )
        
        workflow.add_conditional_edges(
            "initial_assessment", 
            self._route_after_initial,
            {
                "collect_info": "collect_info",
                "complete": "complete"
            }
        )
        
        workflow.add_conditional_edges(
            "collect_info",
            self._route_after_collect,
            {
                "collect_info": "collect_info",  # 다음 질문으로
                "emergency_action": "emergency_action",
                "complete": "complete"
            }
        )
        
        workflow.add_conditional_edges(
            "emergency_action",
            self._route_after_emergency,
            {
                "complete": "complete"
            }
        )
        
        workflow.add_edge("complete", END)
        
        return workflow.compile()
    
    # 더미 노드 함수들 (시각화용)
    def _greeting_node(self, state: VictimRecoveryState) -> VictimRecoveryState:
        state["current_step"] = "greeting_complete"
        return state
    
    def _initial_assessment_node(self, state: VictimRecoveryState) -> VictimRecoveryState:
        state["current_step"] = "assessment_complete"
        state["urgency_level"] = 5
        return state
    
    def _collect_info_node(self, state: VictimRecoveryState) -> VictimRecoveryState:
        state["current_step"] = "collecting_info"
        return state
    
    def _emergency_action_node(self, state: VictimRecoveryState) -> VictimRecoveryState:
        state["current_step"] = "emergency_complete"
        return state
    
    def _complete_node(self, state: VictimRecoveryState) -> VictimRecoveryState:
        state["current_step"] = "consultation_complete"
        return state
    
    # 라우팅 함수들 (실제 로직 반영)
    def _route_after_greeting(self, state: VictimRecoveryState) -> Literal["initial_assessment"]:
        return "initial_assessment"
    
    def _route_after_initial(self, state: VictimRecoveryState) -> Literal["collect_info", "complete"]:
        return "collect_info"
    
    def _route_after_collect(self, state: VictimRecoveryState) -> Literal["collect_info", "emergency_action", "complete"]:
        urgency = state.get("urgency_level", 3)
        if urgency >= 8:
            return "emergency_action"
        elif state.get("conversation_turns", 0) >= 5:
            return "complete"
        else:
            return "collect_info"
    
    def _route_after_emergency(self, state: VictimRecoveryState) -> Literal["complete"]:
        return "complete"
    
    def generate_detailed_mermaid(self, output_path: str = "voice_phishing_detailed.mmd"):
        """상세한 Mermaid 다이어그램 생성"""
        
        mermaid_code = """
graph TD
    START([🚀 상담 시작<br/>Session Start]) --> GREETING[👋 인사 노드<br/>Greeting Node<br/><br/>• 초기 인사말<br/>• 상담 접수<br/>• 질문 인덱스 초기화]
    
    GREETING --> INITIAL_ASSESSMENT[🔍 초기 평가 노드<br/>Initial Assessment<br/><br/>• 스마트 긴급도 판단<br/>• 키워드 분석<br/>• 맥락 기반 점수 계산]
    
    INITIAL_ASSESSMENT --> COLLECT_INFO[📝 정보 수집 노드<br/>Collect Info<br/><br/>• 구조화된 질문 진행<br/>• 답변 파싱 및 저장<br/>• 확인 메시지 생성]
    
    COLLECT_INFO --> COLLECT_DECISION{질문 완료?<br/>All Questions Done?}
    
    COLLECT_DECISION -->|미완료<br/>More Questions| COLLECT_INFO
    COLLECT_DECISION -->|완료 & 긴급도 ≥ 8<br/>Done & High Urgency| EMERGENCY_ACTION[🚨 긴급 조치 노드<br/>Emergency Action<br/><br/>• 즉시 조치사항 안내<br/>• 112/1332 신고 안내<br/>• 지급정지 신청 가이드]
    COLLECT_DECISION -->|완료 & 일반<br/>Done & Normal| COMPLETE[✅ 완료 노드<br/>Complete<br/><br/>• 상담 요약 생성<br/>• 3일 규칙 안내<br/>• 세션 정리]
    
    EMERGENCY_ACTION --> COMPLETE
    COMPLETE --> END([🏁 상담 종료<br/>Session End])
    
    %% 스타일링
    classDef startEnd fill:#e8f5e8,stroke:#2e7d32,stroke-width:3px,color:#000
    classDef process fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#000
    classDef decision fill:#fff3e0,stroke:#ef6c00,stroke-width:2px,color:#000
    classDef emergency fill:#ffebee,stroke:#c62828,stroke-width:3px,color:#000
    classDef complete fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#000
    
    class START,END startEnd
    class GREETING,INITIAL_ASSESSMENT,COLLECT_INFO process
    class COLLECT_DECISION decision
    class EMERGENCY_ACTION emergency
    class COMPLETE complete
    
    %% 질문 플로우 상세
    subgraph QUESTIONS [" 📋 구조화된 질문 플로우 "]
        Q1[❓ 피해자 본인인가?<br/>Victim Confirmation]
        Q2[💰 송금 금액은?<br/>Loss Amount]
        Q3[⏰ 송금 시간은?<br/>Time Context]
        Q4[🏦 지급정지 신청했나?<br/>Payment Stop]
        Q5[🚔 경찰 신고했나?<br/>Police Report]
        
        Q1 --> Q2 --> Q3 --> Q4 --> Q5
    end
    
    COLLECT_INFO -.->|순차 진행| QUESTIONS
    
    %% 긴급도 판정 상세
    subgraph URGENCY [" ⚡ 스마트 긴급도 판정 "]
        U1[🔍 패턴 매칭<br/>Pattern Matching]
        U2[📊 키워드 점수<br/>Keyword Scoring]
        U3[🧠 맥락 분석<br/>Context Analysis]
        U4[📈 최종 점수<br/>Final Score 1-10]
        
        U1 --> U2 --> U3 --> U4
    end
    
    INITIAL_ASSESSMENT -.->|알고리즘| URGENCY
    
    %% 응급 조치 상세
    subgraph EMERGENCY_DETAILS [" 🚨 긴급 조치사항 "]
        E1[📞 112/1332 신고]
        E2[🏦 지급정지 신청]
        E3[📱 휴대폰 보안]
        E4[⏰ 3일 규칙 안내]
        
        E1 --> E2 --> E3 --> E4
    end
    
    EMERGENCY_ACTION -.->|안내 내용| EMERGENCY_DETAILS
    
    style QUESTIONS fill:#f9f9f9,stroke:#666,stroke-dasharray: 5 5
    style URGENCY fill:#f0f4ff,stroke:#666,stroke-dasharray: 5 5
    style EMERGENCY_DETAILS fill:#fff0f0,stroke:#666,stroke-dasharray: 5 5
        """
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(mermaid_code.strip())
            
            print(f"✅ 상세 Mermaid 다이어그램 생성: {output_path}")
            return mermaid_code.strip()
            
        except Exception as e:
            print(f"❌ Mermaid 생성 실패: {e}")
            return None
    
    def generate_simple_mermaid(self, output_path: str = "voice_phishing_simple.mmd"):
        """간단한 Mermaid 다이어그램 생성"""
        
        mermaid_code = """
graph LR
    A[🚀 시작] --> B[👋 인사]
    B --> C[🔍 평가]
    C --> D[📝 정보수집]
    D --> E{완료?}
    E -->|No| D
    E -->|Yes + 긴급| F[🚨 긴급조치]
    E -->|Yes + 일반| G[✅ 완료]
    F --> G
    G --> H[🏁 종료]
    
    style A fill:#e8f5e8
    style H fill:#e8f5e8
    style F fill:#ffebee
    style G fill:#f3e5f5
        """
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(mermaid_code.strip())
            
            print(f"✅ 간단 Mermaid 다이어그램 생성: {output_path}")
            return mermaid_code.strip()
            
        except Exception as e:
            print(f"❌ 간단 Mermaid 생성 실패: {e}")
            return None
    
    def generate_ascii_flowchart(self):
        """실제 구현 기반 ASCII 플로우차트"""
        
        ascii_art = """
╔═══════════════════════════════════════════════════════════════════════════════════╗
║                     🎯 보이스피싱 상담 시스템 플로우차트                            ║
║                        (실제 구현 기반 - 2025.06.16)                              ║
╚═══════════════════════════════════════════════════════════════════════════════════╝

                                ┌─────────────┐
                                │   🚀 START  │
                                │  상담 시작   │
                                └──────┬──────┘
                                       │
                                       ▼
                                ┌─────────────┐
                                │ 👋 GREETING │
                                │   인사 노드  │
                                │             │
                                │ • 초기 인사 │
                                │ • 상담 접수 │
                                │ • 세션 생성 │
                                └──────┬──────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │  🔍 INITIAL_ASSESS  │
                            │     초기 평가       │
                            │                     │
                            │ • 스마트 긴급도 판단 │
                            │ • 패턴 매칭 분석    │
                            │ • 맥락 기반 점수    │
                            │ • 점수: 1-10 산출   │
                            └──────────┬──────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │   📝 COLLECT_INFO   │
                            │     정보 수집       │
                            │                     │
                            │ • 구조화된 질문 진행 │
                            │ • 답변 파싱 & 저장  │
                            │ • 확인 메시지 생성   │
                            └──────────┬──────────┘
                                       │
                                       ▼
                         ┌─────────────────────────────┐
                         │        질문 완료?            │
                         │   (current_index >= 5)     │
                         └───────┬─────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
              [미완료 - 순환]            [완료 - 분기]
                    │                         │
                    │                ┌───────┴───────┐
                    │                │               │
                    │                ▼               ▼
                    │      ┌─────────────────┐ ┌─────────────┐
                    │      │  🚨 EMERGENCY   │ │ ✅ COMPLETE │
                    │      │   긴급 조치     │ │   완료 노드  │
                    │      │                 │ │             │
                    │      │ • 즉시조치안내  │ │ • 상담요약  │
                    │      │ • 112/1332신고  │ │ • 3일규칙   │
                    │      │ • 지급정지가이드│ │ • 세션정리  │
                    │      └─────────┬───────┘ └──────┬──────┘
                    │                │                │
                    └────────────────┼────────────────┘
                                     │
                                     ▼
                              ┌─────────────┐
                              │   🏁 END    │
                              │  상담 종료   │
                              └─────────────┘

╔═══════════════════════════════════════════════════════════════════════════════════╗
║                                 📊 시스템 정보                                    ║
╠═══════════════════════════════════════════════════════════════════════════════════╣
║                                                                                   ║
║ 🎯 구조화된 질문 순서 (5단계):                                                    ║
║   1️⃣ 피해자 본인 확인 - "피해자가 본인일까요?"                                    ║
║   2️⃣ 손실 금액 파악 - "송금한 돈이 얼마인가요?"                                   ║
║   3️⃣ 시간 맥락 수집 - "언제 송금하셨나요?"                                        ║
║   4️⃣ 지급정지 여부 - "계좌 지급정지 신청을 하셨나요?"                             ║
║   5️⃣ 경찰 신고 여부 - "경찰서에 신고하셨나요?"                                    ║
║                                                                                   ║
║ ⚡ 스마트 긴급도 판정 알고리즘:                                                   ║
║   • 고위험 패턴: "15억 송금했어요" → 긴급도 8+                                   ║
║   • 중위험 패턴: "사기 당한 것 같아요" → 긴급도 5-7                              ║
║   • 저위험 패턴: "돈 이름" → 긴급도 1-3                                         ║
║   • 맥락 고려: 질문형태(-2), 시간정보(+3), 부정어(-3)                           ║
║                                                                                   ║
║ 🚨 긴급 조치 기준:                                                               ║
║   • 긴급도 ≥ 8: 즉시 긴급조치 노드로 분기                                       ║
║   • 긴급도 < 8: 일반 완료 노드로 진행                                           ║
║                                                                                   ║
║ 🔄 순환 방지:                                                                    ║
║   • 질문 인덱스로 진행 상황 추적                                                 ║
║   • 최대 5개 질문 완료 시 자동 종료                                             ║
║   • Recursion Limit: 10회 제한                                                  ║
║                                                                                   ║
║ 📈 성능 최적화:                                                                  ║
║   • 답변 파싱: 정규식 + 키워드 매칭                                             ║
║   • 금액 처리: "15억" → "1,500,000,000원" 자동 변환                            ║
║   • 시간 처리: "25분 전에 다" → "25분 전" 정규화                                ║
║                                                                                   ║
╚═══════════════════════════════════════════════════════════════════════════════════╝
        """
        
        print(ascii_art)
    
    def generate_langgraph_native(self, output_path: str = "voice_phishing_native"):
        """LangGraph 내장 시각화 기능 사용"""
        
        try:
            # PNG 생성 시도
            png_path = f"{output_path}.png"
            self.graph.get_graph().draw_mermaid_png(output_file_path=png_path)
            print(f"✅ LangGraph 네이티브 PNG 생성: {png_path}")
            return True
            
        except Exception as e:
            print(f"❌ LangGraph 네이티브 PNG 생성 실패: {e}")
            
            try:
                # Mermaid 코드 생성 시도
                mmd_path = f"{output_path}.mmd"
                mermaid_code = self.graph.get_graph().draw_mermaid()
                
                with open(mmd_path, 'w', encoding='utf-8') as f:
                    f.write(mermaid_code)
                
                print(f"✅ LangGraph 네이티브 Mermaid 생성: {mmd_path}")
                return True
                
            except Exception as e2:
                print(f"❌ LangGraph 네이티브 Mermaid도 실패: {e2}")
                return False
    
    def print_graph_info(self):
        """실제 그래프 구조 정보 출력"""
        
        print("\n" + "="*70)
        print("📊 LangGraph 구조 분석 (실제 구현 기반)")
        print("="*70)
        
        try:
            graph_info = self.graph.get_graph()
            
            print(f"🏗️  노드 수: {len(graph_info.nodes)}")
            print(f"🔗 엣지 수: {len(graph_info.edges)}")
            
            print("\n📋 노드 목록 (실행 순서):")
            nodes = ["greeting", "initial_assessment", "collect_info", "emergency_action", "complete"]
            for i, node in enumerate(nodes, 1):
                print(f"   {i}. {node}")
            
            print(f"\n🔗 조건부 분기:")
            print("   • greeting → initial_assessment (무조건)")
            print("   • initial_assessment → collect_info (무조건)")
            print("   • collect_info → collect_info | emergency_action | complete (조건부)")
            print("   • emergency_action → complete (무조건)")
            
            print(f"\n⚡ 분기 조건:")
            print("   • 질문 미완료 → collect_info 순환")
            print("   • 질문 완료 + 긴급도 ≥ 8 → emergency_action")
            print("   • 질문 완료 + 긴급도 < 8 → complete")
                
        except Exception as e:
            print(f"❌ 그래프 정보 조회 실패: {e}")
    
    def print_implementation_stats(self):
        """구현 통계 정보"""
        
        print("\n" + "="*70)
        print("📈 구현 통계 정보")
        print("="*70)
        
        print("📝 질문 플로우:")
        questions = [
            "피해자 본인 확인",
            "손실 금액 파악", 
            "시간 맥락 수집",
            "지급정지 여부",
            "경찰 신고 여부"
        ]
        
        for i, q in enumerate(questions, 1):
            print(f"   {i}. {q}")
        
        print(f"\n🎯 핵심 기능:")
        print("   • 스마트 긴급도 판정 (1-10점)")
        print("   • 구조화된 정보 수집")
        print("   • 실시간 답변 파싱")
        print("   • 맞춤형 응급 조치 안내")
        
        print(f"\n⚡ 성능 최적화:")
        print("   • 정규식 기반 빠른 파싱")
        print("   • 키워드 매칭 알고리즘")
        print("   • 순환 방지 메커니즘")
        print("   • 타임아웃 처리")


def main():
    """메인 실행 함수"""
    
    print("🎨 보이스피싱 상담 시스템 LangGraph 시각화 도구")
    print("=" * 70)
    print("📅 생성일: 2025.06.16")
    print("🔧 버전: StructuredVoicePhishingGraph v1.0")
    print("=" * 70)
    
    # 시각화 도구 초기화
    visualizer = VoicePhishingGraphVisualizer()
    
    # 1. ASCII 플로우차트 출력
    print("\n1️⃣ ASCII 플로우차트 (실제 구현 기반):")
    visualizer.generate_ascii_flowchart()
    
    # 2. 그래프 구조 정보
    print("\n2️⃣ 그래프 구조 분석:")
    visualizer.print_graph_info()
    
    # 3. 구현 통계
    print("\n3️⃣ 구현 통계:")
    visualizer.print_implementation_stats()
    
    # 4. Mermaid 파일들 생성
    print("\n4️⃣ Mermaid 다이어그램 생성:")
    
    # 상세 버전
    visualizer.generate_detailed_mermaid("voice_phishing_detailed.mmd")
    
    # 간단 버전
    visualizer.generate_simple_mermaid("voice_phishing_simple.mmd")
    
    # 5. LangGraph 네이티브 시각화 시도
    print("\n5️⃣ LangGraph 네이티브 시각화:")
    visualizer.generate_langgraph_native("voice_phishing_langgraph")
    
    # 결과 요약
    print("\n" + "="*70)
    print("🎯 시각화 완료!")
    print("="*70)
    
    print("📁 생성된 파일들:")
    files = [
        "voice_phishing_detailed.mmd (상세 다이어그램)",
        "voice_phishing_simple.mmd (간단 다이어그램)", 
        "voice_phishing_langgraph.mmd (네이티브 생성)",
        "voice_phishing_langgraph.png (가능한 경우)"
    ]
    
    for file in files:
        print(f"   ✅ {file}")
    
    print(f"\n🌐 온라인 에디터:")
    print("   • https://mermaid.live/ (Mermaid 편집기)")
    print("   • https://app.diagrams.net/ (Draw.io)")
    
    print(f"\n📚 사용법:")
    print("   1. .mmd 파일을 Mermaid Live Editor에 복사")
    print("   2. PNG/SVG/PDF로 내보내기")
    print("   3. 문서나 프레젠테이션에 활용")
    print("   4. 팀 공유 및 시스템 설명 자료로 활용")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 시각화 도구를 종료합니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        print("💡 프로젝트 루트에서 실행해주세요.")