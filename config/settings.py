import os
from pathlib import Path

# .env 파일 로드 추가
try:
    from dotenv import load_dotenv
    # 프로젝트 루트의 .env 파일 로드
    BASE_DIR = Path(__file__).resolve().parent.parent
    dotenv_path = BASE_DIR / '.env'
    load_dotenv(dotenv_path)
    print(f"✅ .env 파일 로드됨: {dotenv_path}")
except ImportError:
    print("⚠️ python-dotenv가 설치되지 않음")
except Exception as e:
    print(f"⚠️ .env 로드 실패: {e}")

# 프로젝트 루트 디렉토리
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    """음성 친화적 애플리케이션 설정"""
    
    # STT 설정 (ReturnZero)
    RETURNZERO_CLIENT_ID = os.getenv("RETURNZERO_CLIENT_ID", "")
    RETURNZERO_CLIENT_SECRET = os.getenv("RETURNZERO_CLIENT_SECRET", "")
    
    # TTS 설정 (ElevenLabs) - 음성 최적화
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
    
    # 하드코딩으로 강제 설정 (환경변수 무시)
    TTS_VOICE_ID = "uyVNoMrnUku1dZyVEXwD"
    TTS_MODEL = "eleven_flash_v2_5"  # 빠른 응답용 모델
    TTS_OPTIMIZE_LATENCY = 1
    
    # 음성 친화적 TTS 설정
    TTS_OUTPUT_FORMAT = "mp3_22050_32"  # 빠른 처리용 낮은 품질
    TTS_MAX_SENTENCE_LENGTH = 50        # 문장당 최대 길이
    TTS_SPEED_OPTIMIZATION = True       # 속도 최적화 모드

   # Gemini AI 설정
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()
    GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "5"))  # 5초로 단축
    
    # AI 응답 설정 / 문장 최대 길이 줄이기 / api 호출 비용 감소를 위해서
    USE_AI_ASSISTANT = os.getenv("USE_AI_ASSISTANT", "True").lower() == "true"
    AI_RESPONSE_MAX_LENGTH = int(os.getenv("AI_RESPONSE_MAX_LENGTH", "100"))  # 300 → 100자

    AI_SENTENCE_MAX_LENGTH = 70         # 문장 최대 길이
    AI_RESPONSE_MAX_SECONDS = 8         # TTS 최대 8초 / 일레븐랩스 호출 : 비용 많이 들어가니까 왠만하면 길이 제한 반드시 걸어놓을 것
    
    # 음성 친화적 대화 설정
    VOICE_FRIENDLY_MODE = True          # 음성 친화적 모드
    ONE_ACTION_PER_TURN = True          # 한 턴에 하나의 액션만
    IMMEDIATE_HELP_PRIORITY = True      # 즉시 도움 우선
    
    # 오디오 설정
    SAMPLE_RATE = 16000
    CHUNK_SIZE = int(SAMPLE_RATE / 10)  # 100ms
    CHANNELS = 1
    FORMAT = "paInt16"
    
    # 시스템 설정
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # 상담 설정 - 사용자가 따라갈 수 있도록 조정
    MAX_SILENCE_DURATION = 8.0          # 8초 무음 시 응답 (여유있게)
    MAX_CONVERSATION_TURNS = 12         # 최대 12턴으로 증가
    SESSION_TIMEOUT = 900               # 15분으로 설정
    
    # 침묵 감지 설정 - 더 여유있게
    SILENCE_DETECTION_ENABLED = True
    SILENCE_TIMEOUT = 8.0               # 8초 (사용자가 생각할 시간)
    SKIP_FIRST_INTERACTION = True
    
    # STT 품질 설정
    STT_MIN_TEXT_LENGTH = 3             # 최소 3글자 이상만 처리
    STT_CONFIDENCE_THRESHOLD = 0.7      # 신뢰도 70% 이상만 처리
    
    # 응급 상황 설정
    EMERGENCY_RESPONSE_PRIORITY = True  # 응급 상황 우선 처리
    EMERGENCY_CONTACT_QUICK_ACCESS = True  # 긴급 연락처 빠른 접근
    
    # 실질적 도움 우선순위 설정
    PRACTICAL_HELP_KEYWORDS = [
        "mSAFER", "보이스피싱제로", "132번", "1811-0041",
        "PASS앱", "명의도용", "생활비지원", "무료상담"
    ]
    HYBRID_MODE_ENABLED = True
    GEMINI_CONFIDENCE_THRESHOLD = 0.5    # 50% 이상일 때만 Gemini 사용
    GEMINI_TIMEOUT_HYBRID = 5.0          # 하이브리드용 짧은 타임아웃
    HYBRID_DEBUG = True                  # 하이브리드 디버그 모드

    # 하이브리드 임계값들
    CONTEXT_MISMATCH_THRESHOLD = 0.7     # 컨텍스트 불일치 임계값
    EXPLANATION_REQUEST_THRESHOLD = 0.5   # 설명 요청 임계값
    DISSATISFACTION_THRESHOLD = 0.5      # 불만족 감지 임계값


    # 음성 응답 템플릿 (실제 도움되는 것들)
    EMERGENCY_ACTIONS = [
        {
            "condition": "명의도용_차단",
            "question": "패스(PASS) 어플을 혹시 설치하신 상태인가요?",
            "action": "PASS 앱에서 전체 메뉴, 명의도용방지서비스 누르세요.",
            "phone": None
        },
        {
            "condition": "생활비_지원",
            "question": "중위소득 백퍼센트(100%) 이하인 경우, 생활비 지원도 가능한데 알아보시겠어요?",
            "action": "공이 육칠삼삼 일공육칠(02-6733-1067)번으로 전화하시면 신청할 수 있어요. 기준에 따라 최대 300만원까지 가능해요.",
            "phone": "02-6733-1067"
        },
        {
            "condition": "무료_상담",
            "question": "법률 무료 상담 받아보시겠어요?",
            "action": "132번으로 전화하시면 무료로 상담받을 수 있어요.",
            "phone": "132"
        }
    ]
    
    # 연락처 정보 (음성으로 전달하기 쉬운 것들)
    EMERGENCY_CONTACTS = {
        "보이스피싱제로": {
            "phone": "1811-0041",
            "description": "생활비 지원",
            "voice_friendly": "일팔일일 공공사일"
        },
        "무료법률상담": {
            "phone": "132",
            "description": "무료 상담",
            "voice_friendly": "일삼이"
        },
        "경찰신고": {
            "phone": "112",
            "description": "긴급신고",
            "voice_friendly": "일일이"
        }
    }
    
    # 웹사이트 정보 (음성으로는 제공 안 함)
    WEBSITE_INFO = {
        "mSAFER": "msafer.or.kr",
        "보이스피싱제로": "voicephisingzero.co.kr",
        "계좌확인": "payinfo.or.kr",
        "개인정보보호": "pd.fss.or.kr"
    }

settings = Settings()

# 음성 친화적 설정 검증
def validate_voice_settings():
    """음성 친화적 설정 검증"""
    
    issues = []
    
    # 응답 길이 체크
    if settings.AI_RESPONSE_MAX_LENGTH > 100:
        issues.append("⚠️ 응답 길이가 너무 김 (음성으로 100자 이상은 부담)")
    
    # TTS 시간 체크
    if settings.AI_RESPONSE_MAX_SECONDS > 10:
        issues.append("⚠️ TTS 시간이 너무 김 (10초 이상은 답답함)")
    
    # 침묵 타임아웃 체크
    if settings.SILENCE_TIMEOUT > 6:
        issues.append("⚠️ 침묵 타임아웃이 너무 김 (사용자가 기다리기 어려움)")
    
    if issues:
        print("🔧 음성 친화적 설정 이슈:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("✅ 음성 친화적 설정 검증 완료")

# 설정 검증 실행
if __name__ == "__main__":
    validate_voice_settings()
    
    print(f"📊 현재 설정:")
    print(f"   응답 최대 길이: {settings.AI_RESPONSE_MAX_LENGTH}자")
    print(f"   TTS 최대 시간: {settings.AI_RESPONSE_MAX_SECONDS}초")
    print(f"   침묵 타임아웃: {settings.SILENCE_TIMEOUT}초")
    print(f"   최대 대화 턴: {settings.MAX_CONVERSATION_TURNS}턴")
    print(f"   음성 친화적 모드: {settings.VOICE_FRIENDLY_MODE}")