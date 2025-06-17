#!/usr/bin/env python3
"""
음성 친화적 보이스피싱 상담 시스템
- 3초 이내 빠른 응답
- 80자 이내 간결한 답변
- 실질적 도움 우선
- 즉시 실행 가능한 조치 안내
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
from services.conversation_manager import VoiceFriendlyConversationManager, ConversationState

# 음성 친화적 로깅 설정
def setup_voice_friendly_logging():
    """간단하고 빠른 로깅 설정"""
    
    log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    
    # 간단한 포매터
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 콘솔 핸들러만 (성능 우선)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    # 외부 라이브러리 로그 최소화
    logging.getLogger('elevenlabs').setLevel(logging.ERROR)
    logging.getLogger('grpc').setLevel(logging.ERROR)
    logging.getLogger('pyaudio').setLevel(logging.ERROR)

setup_voice_friendly_logging()
logger = logging.getLogger(__name__)

class VoiceFriendlyPhishingApp:
    """음성 친화적 보이스피싱 상담 애플리케이션"""
    
    def __init__(self):
        self.conversation_manager = None
        self.is_running = False
        self.start_time = None
        
        # 간단한 시스템 모니터링
        self.process = psutil.Process()
        self.initial_memory = self.process.memory_info().rss
        
        # 음성 친화적 통계
        self.stats = {
            'start_time': None,
            'total_runtime': 0,
            'peak_memory_usage': 0,
            'total_conversations': 0,
            'fast_responses': 0,
            'emergency_handled': 0
        }
        
        # 설정 검증 (빠른 검증)
        self._quick_validate_config()
    
    def _quick_validate_config(self):
        """빠른 설정 검증"""
        
        # 필수 API 키만 확인
        if not settings.RETURNZERO_CLIENT_ID or not settings.RETURNZERO_CLIENT_SECRET:
            logger.error("❌ ReturnZero API 키가 설정되지 않았습니다.")
            sys.exit(1)
        
        if not settings.ELEVENLABS_API_KEY:
            logger.warning("⚠️ ElevenLabs API 키가 없습니다. 텍스트 모드로 진행됩니다.")
        
        # 음성 친화적 설정 확인
        if settings.AI_RESPONSE_MAX_LENGTH > 100:
            logger.warning(f"⚠️ 응답 길이가 깁니다: {settings.AI_RESPONSE_MAX_LENGTH}자")
        
        if settings.SILENCE_TIMEOUT > 5:
            logger.warning(f"⚠️ 침묵 타임아웃이 깁니다: {settings.SILENCE_TIMEOUT}초")
        
        logger.info("✅ 음성 친화적 설정 검증 완료")
    
    async def initialize(self):
        """빠른 애플리케이션 초기화"""
        
        logger.info("=" * 50)
        logger.info("🎙️ 음성 친화적 보이스피싱 상담 시스템")
        logger.info("=" * 50)
        
        self.start_time = datetime.now()
        self.stats['start_time'] = self.start_time
        
        try:
            # 메모리 사용량 체크
            initial_memory_mb = self.initial_memory / 1024 / 1024
            logger.info(f"🧠 초기 메모리: {initial_memory_mb:.1f} MB")
            
            # 대화 매니저 빠른 생성
            self.conversation_manager = VoiceFriendlyConversationManager(
                client_id=settings.RETURNZERO_CLIENT_ID,
                client_secret=settings.RETURNZERO_CLIENT_SECRET
            )
            
            # 콜백 설정
            self.conversation_manager.set_callbacks(
                on_user_speech=self._on_user_speech,
                on_ai_response=self._on_ai_response,
                on_state_change=self._on_state_change
            )
            
            # 초기화 시간 측정
            init_time = (datetime.now() - self.start_time).total_seconds()
            logger.info(f"✅ 빠른 초기화 완료 ({init_time:.2f}초)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 초기화 실패: {e}")
            return False
    
    async def run(self):
        """음성 친화적 메인 실행"""
        
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
            
            # 간단한 모니터링과 대화 실행
            tasks = await self._create_simple_tasks()
            
            # 모든 태스크 실행
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except KeyboardInterrupt:
            logger.info("\n🛑 사용자에 의한 종료")
        except Exception as e:
            logger.error(f"❌ 실행 중 오류: {e}")
        finally:
            await self.cleanup()
    
    async def _create_simple_tasks(self):
        """간단한 태스크들 생성"""
        
        tasks = []
        
        # 간단한 모니터링 (30초마다)
        tasks.append(asyncio.create_task(
            self._simple_monitoring(), 
            name="SimpleMonitor"
        ))
        
        # 메인 대화 태스크
        tasks.append(asyncio.create_task(
            self.conversation_manager.start_conversation(),
            name="VoiceFriendlyConversation"
        ))
        
        return tasks
    
    def _setup_signal_handlers(self):
        """간단한 시그널 핸들러"""
        
        def signal_handler(signum, frame):
            logger.info(f"\n📶 종료 신호 수신")
            import os
            os._exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
    
    def _setup_debug_commands(self):
        """간단한 디버그 명령어"""
        
        def debug_worker():
            while self.is_running:
                try:
                    cmd = input().strip().lower()
                    
                    if cmd == 'stats':
                        # 간단한 통계 출력
                        if self.conversation_manager:
                            status = self.conversation_manager.get_conversation_status()
                            print("\n📊 현재 상태:")
                            print(f"   상태: {status['state']}")
                            print(f"   턴 수: {status['total_turns']}")
                            print(f"   평균 응답시간: {status['avg_response_time']:.3f}초")
                            print(f"   빠른 응답률: {status['fast_response_rate']}")
                            print()
                    
                    elif cmd == 'audio':
                        # 오디오 상태
                        if self.conversation_manager:
                            audio_status = self.conversation_manager.get_audio_status()
                            print("\n🎤 오디오 상태:")
                            for key, value in audio_status.items():
                                print(f"   {key}: {value}")
                            print()

                    elif cmd == 'hybrid':
                        # 하이브리드 엔진 성능 확인
                        if hasattr(self.conversation_manager.ai_brain, 'decision_engine'):
                            stats = self.conversation_manager.ai_brain.decision_engine.get_performance_stats()
                            print("\n🤖 하이브리드 엔진 통계:")
                            for key, value in stats.items():
                                print(f"   {key}: {value}")
                    
                    elif cmd == 'help':
                        print("\n💡 명령어:")
                        print("   stats - 대화 통계")
                        print("   audio - 오디오 상태")
                        print("   help  - 도움말")
                        print()
                    
                except (EOFError, KeyboardInterrupt):
                    break
                except Exception:
                    pass
        
        debug_thread = threading.Thread(target=debug_worker, daemon=True)
        debug_thread.start()
        print("\n💡 디버그 모드: 'stats', 'audio', 'help' 명령어 사용 가능")
    
    async def _simple_monitoring(self):
        """간단한 시스템 모니터링"""
        
        while self.is_running:
            try:
                # 메모리 체크 (30초마다)
                memory_info = self.process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                
                # 최대 메모리 업데이트
                if memory_mb > self.stats['peak_memory_usage']:
                    self.stats['peak_memory_usage'] = memory_mb
                
                # 메모리 경고 (200MB 초과)
                if memory_mb > 200:
                    logger.warning(f"⚠️ 높은 메모리 사용량: {memory_mb:.1f}MB")
                    
                    # 간단한 메모리 정리
                    gc.collect()
                
                await asyncio.sleep(30)  # 30초마다
                
            except Exception as e:
                logger.error(f"모니터링 오류: {e}")
                await asyncio.sleep(60)
    
    def _on_user_speech(self, text: str):
        """사용자 음성 콜백 (간결한 출력)"""
        
        # 간결한 출력 (30자로 제한)
        display_text = text[:30] + "..." if len(text) > 30 else text
        print(f"\n👤 사용자: {display_text}")
        
        # 상세 로그는 디버그 모드에서만
        if settings.DEBUG:
            logger.debug(f"사용자 입력 전체: {text}")
    
    def _on_ai_response(self, response: str):
        """AI 응답 콜백 (간결한 출력)"""
        
        # 간결한 출력 (50자로 제한)
        display_response = response[:50] + "..." if len(response) > 50 else response
        print(f"\n🤖 상담원: {display_response}")
        
        # 응급 상황 체크
        if any(word in response for word in ['긴급', '급해', '즉시', '일삼이']):
            self.stats['emergency_handled'] += 1
        
        # 상세 로그는 디버그 모드에서만
        if settings.DEBUG:
            logger.debug(f"AI 응답 전체: {response}")
    
    def _on_state_change(self, old_state: ConversationState, new_state: ConversationState):
        """상태 변경 콜백 (간단한 표시)"""
        
        # 상태 아이콘
        state_icons = {
            ConversationState.IDLE: "💤",
            ConversationState.LISTENING: "👂", 
            ConversationState.PROCESSING: "🧠",
            ConversationState.SPEAKING: "🗣️",
            ConversationState.ERROR: "❌"
        }
        
        old_icon = state_icons.get(old_state, "❓")
        new_icon = state_icons.get(new_state, "❓")
        
        # 간단한 상태 표시 (디버그 모드에서만)
        if settings.DEBUG:
            print(f"{old_icon} → {new_icon}")
        
        logger.debug(f"상태 변경: {old_state.value} → {new_state.value}")
    
    async def cleanup(self):
        """빠른 리소스 정리"""
        
        logger.info("🧹 음성 친화적 앱 종료 중...")
        
        try:
            self.is_running = False
            
            # 대화 매니저 정리
            if self.conversation_manager:
                await self.conversation_manager.cleanup()
            
            # 최종 통계 출력
            self._print_final_stats()
            
            # 간단한 메모리 정리
            gc.collect()
            
            logger.info("✅ 정리 완료")
            
        except Exception as e:
            logger.error(f"정리 중 오류: {e}")
    
    def _print_final_stats(self):
        """최종 통계 출력 (간결하게)"""
        
        if not self.start_time:
            return
        
        total_runtime = (datetime.now() - self.start_time).total_seconds()
        final_memory = self.process.memory_info().rss / 1024 / 1024
        
        logger.info("📈 === 최종 통계 ===")
        logger.info(f"   실행 시간: {total_runtime/60:.1f}분")
        logger.info(f"   최대 메모리: {self.stats['peak_memory_usage']:.1f}MB")
        logger.info(f"   최종 메모리: {final_memory:.1f}MB")
        
        if self.conversation_manager:
            conv_status = self.conversation_manager.get_conversation_status()
            logger.info(f"   대화 턴: {conv_status.get('total_turns', 0)}")
            logger.info(f"   평균 응답시간: {conv_status.get('avg_response_time', 0):.3f}초")
            logger.info(f"   빠른 응답률: {conv_status.get('fast_response_rate', '0%')}")
            logger.info(f"   응급 처리: {self.stats['emergency_handled']}회")
        
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
        # 성능 최적화된 이벤트 루프 실행
        if hasattr(asyncio, 'WindowsProactorEventLoopPolicy'):
            # Windows 최적화
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