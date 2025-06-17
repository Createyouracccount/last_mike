from typing import TypedDict, List, Optional, Dict, Any, Annotated
from datetime import datetime
from enum import Enum
import operator

class DamageType(Enum):
    """피해 유형 - 환급 절차별 분류"""
    ACCOUNT_TRANSFER = "계좌이체"      # 일반 계좌이체 피해
    CARD_PAYMENT = "카드결제"         # 카드 결제 피해  
    APP_CONTROL = "앱조작"           # 악성앱을 통한 피해
    CASH_DELIVERY = "현금전달"        # 대면 현금 편취
    LOAN_FRAUD = "대출사기"          # 대출 관련 사기
    INVESTMENT_FRAUD = "투자사기"     # 투자 관련 사기

class RecoveryStage(Enum):
    """환급 진행 단계"""
    INITIAL_REPORT = "initial_report"         # 초기 신고
    PAYMENT_STOP = "payment_stop"             # 지급정지
    EVIDENCE_COLLECTION = "evidence_collection" # 증거 수집
    BANK_APPLICATION = "bank_application"     # 은행 신청
    AGENCY_REVIEW = "agency_review"          # 기관 심사
    BOND_ELIMINATION = "bond_elimination"     # 채권소멸
    REFUND_PROCESS = "refund_process"        # 환급 처리
    FOLLOW_UP = "follow_up"                  # 사후 관리

class VictimRecoveryState(TypedDict):
    """피해자 상태 - 실제 환급 절차 중심"""
    
    # 기본 정보
    session_id: str
    current_stage: str
    recovery_stage: str
    
    # LangGraph 표준 - 메시지 누적
    messages: Annotated[List[Dict[str, Any]], operator.add]
    
    # 피해 정보
    damage_type: Optional[str]
    damage_amount: Optional[int]
    damage_confirmed: bool
    damage_date: Optional[datetime]
    scammer_account: Optional[str]  # 사기범 계좌번호
    
    # 은행 정보
    victim_bank: Optional[str]      # 피해자 은행
    scammer_bank: Optional[str]     # 사기범 계좌 은행
    transfer_method: Optional[str]   # 이체 방법
    
    # 진행 상황
    payment_stopped: bool           # 지급정지 완료 여부
    police_reported: bool           # 경찰 신고 완료
    bank_applied: bool             # 은행 신청 완료
    documents_submitted: bool       # 서류 제출 완료
    
    # 필요 서류
    required_documents: List[str]
    submitted_documents: List[str]
    pending_documents: List[str]
    
    # 시간 추적
    damage_occurred_at: Optional[datetime]
    report_deadline: Optional[datetime]  # 신고 마감일 (3일)
    
    # 연락처 정보
    emergency_contacts: Dict[str, str]
    bank_contacts: Dict[str, str]
    
    # 진행률
    recovery_progress: float        # 0.0 ~ 1.0
    estimated_recovery_amount: Optional[int]
    recovery_probability: float     # 환급 가능성
    
    # 음성 대화 관련
    conversation_turns: int
    audio_quality: float
    
    # 긴급도
    urgency_level: int             # 1-10
    
    # 추가 피해 방지
    additional_security_needed: bool
    security_measures_taken: List[str]

def create_initial_recovery_state(session_id: str) -> VictimRecoveryState:
    """초기 피해자 상태 생성"""
    
    current_time = datetime.now()
    
    return VictimRecoveryState(
        # 기본 정보
        session_id=session_id,
        current_stage="greeting",
        recovery_stage=RecoveryStage.INITIAL_REPORT.value,
        
        # 메시지
        messages=[],
        
        # 피해 정보
        damage_type=None,
        damage_amount=None,
        damage_confirmed=False,
        damage_date=None,
        scammer_account=None,
        
        # 은행 정보
        victim_bank=None,
        scammer_bank=None,
        transfer_method=None,
        
        # 진행 상황
        payment_stopped=False,
        police_reported=False,
        bank_applied=False,
        documents_submitted=False,
        
        # 서류
        required_documents=[],
        submitted_documents=[],
        pending_documents=[],
        
        # 시간
        damage_occurred_at=None,
        report_deadline=None,
        
        # 연락처
        emergency_contacts={
            "경찰": "112",
            "금융감독원": "1332",
            "통합신고센터": "1566-1188"
        },
        bank_contacts={},
        
        # 진행률
        recovery_progress=0.0,
        estimated_recovery_amount=None,
        recovery_probability=0.0,
        
        # 음성
        conversation_turns=0,
        audio_quality=0.0,
        
        # 긴급도
        urgency_level=5,
        
        # 보안
        additional_security_needed=False,
        security_measures_taken=[]
    )