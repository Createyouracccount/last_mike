#!/usr/bin/env python3
"""
음성 친화적 보이스피싱 상담 시스템 - 디버깅 강화 버전
"""

import asyncio
import logging
import signal
import sys
import psutil
import gc
import threading
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 패스에 추가
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings

# 음성 친화적 로깅 설정
def setup_voice_friendly_logging():
    """간단하고 빠른 로깅 설정"""
    
    log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    
    # 간단한 포매터
    formatter = logging.Formatter(
        '%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    root_logger.addHandler(console_handler)
    
    # 외부 라이브러리 로그 최소화
    logging.getLogger('elevenlabs').setLevel(logging.ERROR)
    logging.getLogger('grpc').setLevel(logging.ERROR)
    logging.getLogger('pyaudio').setLevel(logging.ERROR)
    logging.getLogger('google').setLevel(logging.ERROR)

setup_voice_friendly_logging()
logger = logging.getLogger(__name__)

class VoiceFriendlyPhishingApp:
    """음성 친화적 보이스피싱 상담 애플리케이션 - 디버깅 강화"""
    
    def __init__(self):
        self.conversation_manager = None
        self.is_running = False
        self.start_time = None
        
        # 시스템 모니터링
        self.process = psutil.Process()
        self.initial_memory = self.process.memory_info().rss
        
        # 통계
        self.stats = {
            'start_time': None,
            'initialization_success': False,
            'components_status': {},
            'errors_encountered': []
        }

    async def run_diagnostics(self):
        """시스템 진단 실행"""
        
        print("🔍 === 시스템 진단 시작 ===")
        print()
        
        # 1. 환경 설정 확인
        print("📋 환경 설정 확인:")
        print(f"   DEBUG 모드: {'✅' if settings.DEBUG else '❌'}")
        print(f"   LOG_LEVEL: {settings.LOG_LEVEL}")
        print()
        
        # 2. API 키 확인
        print("🔑 API 키 확인:")
        api_keys = {
            'ReturnZero ID': settings.RETURNZERO_CLIENT_ID,
            'ReturnZero Secret': settings.RETURNZERO_CLIENT_SECRET,
            'ElevenLabs': settings.ELEVENLABS_API_KEY,
            'Gemini': settings.GEMINI_API_KEY
        }
        
        for name, key in api_keys.items():
            status = "✅" if key else "❌"
            masked_key = f"{key[:8]}..." if key and len(key) > 8 else "없음"
            print(f"   {name}: {status} ({masked_key})")
        print()
        
        # 3. 라이브러리 가용성 확인
        print("📚 라이브러리 확인:")
        libraries = [
            ('pyaudio', 'pyaudio'),
            ('grpc', 'grpc'),
            ('elevenlabs', 'elevenlabs'),
            ('google.generativeai', 'google.generativeai'),
            ('pydub', 'pydub')
        ]
        
        for lib_name, import_name in libraries:
            try:
                __import__(import_name)
                print(f"   {lib_name}: ✅")
            except ImportError as e:
                print(f"   {lib_name}: ❌ ({e})")
        print()
        
        # 4. 컴포넌트별 테스트
        await self._test_components()
        
        print("🔍 === 시스템 진단 완료 ===")
        print()

    async def _test_components(self):
        """컴포넌트별 개별 테스트"""
        
        print("🧪 컴포넌트 테스트:")
        
        # TTS 서비스 테스트
        try:
            from services.tts_service import tts_service
            print("   TTS 서비스 로드: ✅")
            
            if tts_service.is_enabled:
                print("   TTS 활성화: ✅")
                # 연결 테스트
                test_result = await asyncio.wait_for(
                    tts_service.test_connection(), 
                    timeout=10.0
                )
                print(f"   TTS 연결 테스트: {'✅' if test_result else '❌'}")
            else:
                print("   TTS 활성화: ❌ (API 키 없음)")
                
        except Exception as e:
            print(f"   TTS 서비스: ❌ ({e})")
        
        # AI 두뇌 테스트
        try:
            from core.graph import VoiceFriendlyPhishingGraph
            print("   AI 그래프 로드: ✅")
            
            ai_brain = VoiceFriendlyPhishingGraph(debug=True)
            print("   AI 두뇌 생성: ✅")
            
            # 간단한 테스트
            test_response = await asyncio.wait_for(
                ai_brain.process_user_input("테스트"),
                timeout=10.0
            )
            if test_response:
                print(f"   AI 응답 테스트: ✅ ({test_response[:30]}...)")
            else:
                print("   AI 응답 테스트: ❌ (빈 응답)")
                
        except Exception as e:
            print(f"   AI 두뇌: ❌ ({e})")
        
        # 오디오 매니저 테스트
        try:
            from services.audio_manager import audio_manager
            print("   오디오 매니저 로드: ✅")
            
            init_result = audio_manager.initialize_output()
            print(f"   오디오 초기화: {'✅' if init_result else '❌'}")
            
        except Exception as e:
            print(f"   오디오 매니저: ❌ ({e})")
        
        # STT 클라이언트 테스트
        try:
            from services.stream_stt import RTZROpenAPIClient
            print("   STT 클라이언트 로드: ✅")
            
            if settings.RETURNZERO_CLIENT_ID and settings.RETURNZERO_CLIENT_SECRET:
                stt_client = RTZROpenAPIClient(
                    settings.RETURNZERO_CLIENT_ID, 
                    settings.RETURNZERO_CLIENT_SECRET
                )
                print("   STT 클라이언트 생성: ✅")
            else:
                print("   STT 클라이언트 생성: ❌ (API 키 없음)")
                
        except Exception as e:
            print(f"   STT 클라이언트: ❌ ({e})")
        
        print()

    async def initialize(self):
        """애플리케이션 초기화"""
        
        logger.info("=" * 50)
        logger.info("🎙️ 음성 친화적 보이스피싱 상담 시스템")
        logger.info("=" * 50)
        
        self.start_time = datetime.now()
        self.stats['start_time'] = self.start_time
        
        try:
            # 메모리 사용량 체크
            initial_memory_mb = self.initial_memory / 1024 / 1024
            logger.info(f"🧠 초기 메모리: {initial_memory_mb:.1f} MB")
            
            # 대화 매니저 생성
            logger.info("🎬 대화 매니저 생성 중...")
            
            from services.conversation_manager import VoiceFriendlyConversationManager
            
            self.conversation_manager = VoiceFriendlyConversationManager(
                client_id=settings.RETURNZERO_CLIENT_ID,
                client_secret=settings.RETURNZERO_CLIENT_SECRET
            )
            
            logger.info("✅ 대화 매니저 생성 완료")
            
            # 콜백 설정
            self.conversation_manager.set_callbacks(
                on_user_speech=self._on_user_speech,
                on_ai_response=self._on_ai_response,
                on_state_change=self._on_state_change,
                on_error=self._on_error
            )
            
            # 초기화 시간 측정
            init_time = (datetime.now() - self.start_time).total_seconds()
            logger.info(f"✅ 초기화 완료 ({init_time:.2f}초)")
            
            self.stats['initialization_success'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ 초기화 실패: {e}")
            self.stats['errors_encountered'].append(f"초기화: {e}")
            return False

    async def run(self):
        """메인 실행"""
        
        # 진단 실행 (디버그 모드에서)
        if settings.DEBUG:
            await self.run_diagnostics()
        
        # 초기화
        if not await self.initialize():
            logger.error("❌ 애플리케이션 시작 실패")
            return
        
        self.is_running = True
        
        try:
            logger.info("🚀 음성 친화적 상담 시스템 시작")
            logger.info("💡 종료하려면 Ctrl+C를 누르세요")
            logger.info("-" * 50)
            
            # 시그널 핸들러 설정
            self._setup_signal_handlers()
            
            # 디버그 명령어 (선택적)
            if settings.DEBUG:
                self._setup_debug_commands()
            
            # 메인 대화 시작
            await self.conversation_manager.start_conversation()
            
        except KeyboardInterrupt:
            logger.info("\n🛑 사용자에 의한 종료")
        except Exception as e:
            logger.error(f"❌ 실행 중 오류: {e}")
            self.stats['errors_encountered'].append(f"실행: {e}")
        finally:
            await self.cleanup()

    def _setup_signal_handlers(self):
        """시그널 핸들러 설정"""
        
        def signal_handler(signum, frame):
            logger.info(f"\n📶 종료 신호 수신 (신호: {signum})")
            asyncio.create_task(self.cleanup())
            import os
            os._exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)

    def _setup_debug_commands(self):
        """디버그 명령어 설정"""
        
        def debug_worker():
            print("\n💡 디버그 모드 활성화")
            print("   명령어: 'stats', 'audio', 'ai', 'memory', 'help', 'quit'")
            print()
            
            while self.is_running:
                try:
                    cmd = input("debug> ").strip().lower()
                    
                    if cmd == 'quit' or cmd == 'exit':
                        logger.info("디버그 명령으로 종료")
                        self.is_running = False
                        break
                    
                    elif cmd == 'stats':
                        self._show_conversation_stats()
                    
                    elif cmd == 'audio':
                        self._show_audio_stats()
                    
                    elif cmd == 'ai':
                        self._show_ai_stats()
                    
                    elif cmd == 'memory':
                        self._show_memory_stats()
                    
                    elif cmd == 'help':
                        print("\n💡 사용 가능한 명령어:")
                        print("   stats  - 대화 통계")
                        print("   audio  - 오디오 상태")
                        print("   ai     - AI 상태")
                        print("   memory - 메모리 상태")
                        print("   help   - 도움말")
                        print("   quit   - 종료")
                        print()
                    
                    elif cmd:
                        print(f"알 수 없는 명령어: {cmd}")
                        print("'help'를 입력하여 사용 가능한 명령어를 확인하세요.")
                    
                except (EOFError, KeyboardInterrupt):
                    break
                except Exception as e:
                    logger.debug(f"디버그 명령 오류: {e}")
        
        debug_thread = threading.Thread(target=debug_worker, daemon=True, name="DebugConsole")
        debug_thread.start()

    def _show_conversation_stats(self):
        """대화 통계 표시"""
        if not self.conversation_manager:
            print("   대화 매니저가 초기화되지 않음")
            return
        
        try:
            status = self.conversation_manager.get_conversation_status()
            print("\n📊 대화 통계:")
            print(f"   상태: {status.get('state', 'unknown')}")
            print(f"   실행 중: {status.get('is_running', False)}")
            print(f"   처리 중: {status.get('is_processing', False)}")
            print(f"   총 턴: {status.get('total_turns', 0)}")
            print(f"   평균 응답시간: {status.get('avg_response_time', 0):.3f}초")
            print(f"   오류 수: {status.get('error_count', 0)}")
            print()
        except Exception as e:
            print(f"   통계 조회 오류: {e}")

    def _show_audio_stats(self):
        """오디오 통계 표시"""
        if not self.conversation_manager:
            print("   대화 매니저가 초기화되지 않음")
            return
        
        try:
            audio_status = self.conversation_manager.get_audio_status()
            print("\n🎤 오디오 상태:")
            for key, value in audio_status.items():
                print(f"   {key}: {value}")
            print()
        except Exception as e:
            print(f"   오디오 상태 조회 오류: {e}")

    def _show_ai_stats(self):
        """AI 통계 표시"""
        if not self.conversation_manager or not self.conversation_manager.ai_brain:
            print("   AI 두뇌가 초기화되지 않음")
            return
        
        try:
            # AI 상태 조회
            if hasattr(self.conversation_manager.ai_brain, 'current_state'):
                current_state = self.conversation_manager.ai_brain.current_state
                if current_state:
                    summary = self.conversation_manager.ai_brain.get_conversation_summary(current_state)
                    print("\n🤖 AI 상태:")
                    for key, value in summary.items():
                        print(f"   {key}: {value}")
                else:
                    print("\n🤖 AI 상태: 대화 상태 없음")
            else:
                print("\n🤖 AI 상태: 상태 추적 불가")
            
            # 하이브리드 엔진 통계 (있는 경우)
            if hasattr(self.conversation_manager.ai_brain, 'decision_engine') and self.conversation_manager.ai_brain.decision_engine:
                hybrid_stats = self.conversation_manager.ai_brain.decision_engine.get_performance_stats()
                print("\n🔀 하이브리드 엔진:")
                for key, value in hybrid_stats.items():
                    print(f"   {key}: {value}")
            
            print()
        except Exception as e:
            print(f"   AI 상태 조회 오류: {e}")

    def _show_memory_stats(self):
        """메모리 통계 표시"""
        try:
            current_memory = self.process.memory_info().rss / 1024 / 1024
            memory_increase = current_memory - (self.initial_memory / 1024 / 1024)
            
            print("\n🧠 메모리 상태:")
            print(f"   초기 메모리: {self.initial_memory / 1024 / 1024:.1f} MB")
            print(f"   현재 메모리: {current_memory:.1f} MB")
            print(f"   증가량: {memory_increase:+.1f} MB")
            print(f"   CPU 사용률: {self.process.cpu_percent():.1f}%")
            print()
        except Exception as e:
            print(f"   메모리 상태 조회 오류: {e}")

    def _on_user_speech(self, text: str):
        """사용자 음성 콜백"""
        display_text = text[:50] + "..." if len(text) > 50 else text
        print(f"\n👤 사용자: {display_text}")

    def _on_ai_response(self, response: str):
        """AI 응답 콜백"""
        display_response = response[:80] + "..." if len(response) > 80 else response
        print(f"\n🤖 상담원: {display_response}")

    def _on_state_change(self, old_state, new_state):
        """상태 변경 콜백"""
        if settings.DEBUG:
            state_icons = {
                "idle": "💤",
                "listening": "👂", 
                "processing": "🧠",
                "speaking": "🗣️",
                "error": "❌"
            }
            
            old_icon = state_icons.get(old_state.value if hasattr(old_state, 'value') else str(old_state), "❓")
            new_icon = state_icons.get(new_state.value if hasattr(new_state, 'value') else str(new_state), "❓")
            
            print(f"[{old_icon} → {new_icon}]", end=" ")

    def _on_error(self, error: Exception):
        """오류 콜백"""
        logger.error(f"시스템 오류: {error}")
        self.stats['errors_encountered'].append(str(error))

    async def cleanup(self):
        """리소스 정리"""
        logger.info("🧹 애플리케이션 종료 중...")
        
        try:
            self.is_running = False
            
            # 대화 매니저 정리
            if self.conversation_manager:
                await self.conversation_manager.cleanup()
            
            # 최종 통계 출력
            self._print_final_stats()
            
            # 메모리 정리
            gc.collect()
            
            logger.info("✅ 정리 완료")
            
        except Exception as e:
            logger.error(f"정리 중 오류: {e}")

    def _print_final_stats(self):
        """최종 통계 출력"""
        if not self.start_time:
            return
        
        total_runtime = (datetime.now() - self.start_time).total_seconds()
        final_memory = self.process.memory_info().rss / 1024 / 1024
        
        logger.info("📈 === 최종 통계 ===")
        logger.info(f"   실행 시간: {total_runtime/60:.1f}분")
        logger.info(f"   최종 메모리: {final_memory:.1f}MB")
        logger.info(f"   초기화 성공: {'✅' if self.stats['initialization_success'] else '❌'}")
        
        if self.stats['errors_encountered']:
            logger.info("   발생한 오류:")
            for error in self.stats['errors_encountered'][-5:]:  # 최근 5개만
                logger.info(f"     - {error}")
        
        if self.conversation_manager:
            try:
                conv_status = self.conversation_manager.get_conversation_status()
                logger.info(f"   대화 턴: {conv_status.get('total_turns', 0)}")
                logger.info(f"   평균 응답시간: {conv_status.get('avg_response_time', 0):.3f}초")
            except Exception:
                pass
        
        logger.info("=" * 20)

async def main():
    """메인 함수"""
    
    # 이벤트 루프 최적화
    loop = asyncio.get_running_loop()
    loop.set_debug(settings.DEBUG)
    
    # 애플리케이션 실행
    app = VoiceFriendlyPhishingApp()
    await app.run()

if __name__ == "__main__":
    try:
        # Windows 최적화
        if hasattr(asyncio, 'WindowsProactorEventLoopPolicy'):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        # 시작 메시지
        print("🎙️ 음성 친화적 보이스피싱 상담 시스템")
        print("⚡ 3초 이내 빠른 응답, 80자 이내 간결한 답변")
        print("🆘 실질적 도움 우선: mSAFER, 보이스피싱제로, 132번")
        print()
        
        asyncio.run(main())
        
    except KeyboardInterrupt:
        print("\n👋 안전하게 종료되었습니다.")
    except Exception as e:
        logger.error(f"치명적 오류: {e}")
        sys.exit(1)