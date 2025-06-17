import asyncio
import logging
import threading
import time
import queue
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from enum import Enum

from services.stream_stt import RTZROpenAPIClient
from core.graph import VoiceFriendlyPhishingGraph
from services.tts_service import tts_service
from services.audio_manager import audio_manager
from config.settings import settings

logger = logging.getLogger(__name__)

class ConversationState(Enum):
    """오케스트레이터 상태 - 기술적 상태만"""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"

class VoiceFriendlyConversationManager:
    """
    음성 대화 오케스트레이터 - 완전 안전 버전
    - STT → AI → TTS 파이프라인 관리만 담당
    - AI 로직은 graph.py에 완전 위임
    - 단순한 중계자 역할
    - 무한루프 방지 및 에러 복구 강화
    """
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        
        # 🎯 핵심 컴포넌트들 (파이프라인)
        self.stt_client = None
        self.ai_brain = VoiceFriendlyPhishingGraph(debug=settings.DEBUG)  # AI 두뇌
        self.tts_service = tts_service
        self.audio_manager = audio_manager
        
        # 🎚️ 오케스트레이터 상태 (기술적 상태만)
        self.state = ConversationState.IDLE
        self.is_running = False
        self.is_processing = False
        
        # 📡 STT 큐 (입력 버퍼)
        self.stt_queue = queue.Queue(maxsize=5)
        
        # 🔒 안전장치들
        self.error_count = 0
        self.max_errors = 10
        self.last_error_time = None
        self.error_cooldown = 1.0  # 1초 쿨다운
        
        # 📊 성능 통계만
        self.stats = {
            'conversation_start_time': None,
            'total_pipeline_runs': 0,
            'avg_pipeline_time': 0.0,
            'stt_errors': 0,
            'tts_errors': 0,
            'ai_errors': 0,
            'loop_errors': 0
        }
        
        # 🔗 외부 알림용 콜백들
        self.callbacks = {
            'on_user_speech': None,
            'on_ai_response': None,
            'on_state_change': None,
            'on_error': None
        }
        
        # ⏱️ 성능 추적
        self.pipeline_times = []
        self.max_history = 10

    async def initialize(self) -> bool:
        """파이프라인 초기화"""
        logger.info("🎬 음성 대화 파이프라인 초기화...")
        
        try:
            # 1. STT 초기화
            self.stt_client = RTZROpenAPIClient(self.client_id, self.client_secret)
            logger.info("✅ STT 파이프라인 준비")
            
            # 2. 오디오 초기화
            if not self.audio_manager.initialize_output():
                logger.error("❌ 오디오 파이프라인 실패")
                return False
            logger.info("✅ 오디오 파이프라인 준비")
            
            # 3. AI 두뇌 시작 (안전하게)
            try:
                await self.ai_brain.start_conversation()
                logger.info("✅ AI 두뇌 준비")
            except Exception as e:
                logger.warning(f"⚠️ AI 두뇌 초기화 경고: {e} - 계속 진행")
            
            # 4. 초기 인사 (AI가 만든 것을 TTS로 전달만)
            await self._deliver_initial_greeting()
            
            self.stats['conversation_start_time'] = datetime.now()
            self._set_state(ConversationState.IDLE)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 파이프라인 초기화 실패: {e}")
            return False

    async def start_conversation(self):
        """대화 파이프라인 시작"""
        if not await self.initialize():
            logger.error("❌ 파이프라인 시작 실패")
            return
        
        self.is_running = True
        logger.info("🎙️ 음성 대화 파이프라인 시작")
        
        try:
            # STT 입력 시작
            self._start_stt_input()
            
            # 메인 파이프라인 루프 (안전 버전)
            await self._safe_pipeline_loop()
            
        except KeyboardInterrupt:
            logger.info("사용자 종료")
        except Exception as e:
            logger.error(f"파이프라인 오류: {e}")
        finally:
            await self.cleanup()

    def _start_stt_input(self):
        """STT 입력 스트림 시작"""
        def stt_worker():
            try:
                self.stt_client.reset_stream()
                
                def transcript_handler(start_time, transcript, is_final=False):
                    if is_final and transcript.alternatives:
                        text = transcript.alternatives[0].text.strip()
                        if text and len(text) > 1:
                            try:
                                # 큐 오버플로우 방지
                                if self.stt_queue.full():
                                    try:
                                        self.stt_queue.get_nowait()  # 오래된 것 제거
                                    except queue.Empty:
                                        pass
                                self.stt_queue.put_nowait(text)
                            except queue.Full:
                                self.stats['stt_errors'] += 1
                
                self.stt_client.print_transcript = transcript_handler
                
                while self.is_running:
                    try:
                        self.stt_client.transcribe_streaming_grpc()
                    except Exception as e:
                        if self.is_running:
                            logger.error(f"STT 입력 오류: {e}")
                            self.stats['stt_errors'] += 1
                        break
                    
            except Exception as e:
                if self.is_running:
                    logger.error(f"STT 워커 오류: {e}")
                    self.stats['stt_errors'] += 1
        
        stt_thread = threading.Thread(target=stt_worker, daemon=True)
        stt_thread.start()
        logger.info("🎤 STT 입력 스트림 시작")

    async def _safe_pipeline_loop(self):
        """안전한 메인 파이프라인 루프 - 무한루프 방지"""
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.is_running:
            try:
                # STT 입력 확인
                user_input = self._get_stt_input()
                
                if user_input and not self.is_processing:
                    # 🎯 핵심: 안전한 파이프라인 실행
                    await self._safe_run_pipeline(user_input)
                
                # AI가 대화 완료했는지 확인 (매우 안전하게)
                try:
                    if (hasattr(self.ai_brain, 'is_conversation_complete') and 
                        callable(getattr(self.ai_brain, 'is_conversation_complete', None))):
                        if self.ai_brain.is_conversation_complete():
                            logger.info("✅ AI가 대화 완료 신호")
                            break
                except AttributeError:
                    # 메서드가 없으면 무시하고 계속
                    pass
                except Exception as e:
                    # 다른 에러도 무시하고 계속
                    logger.debug(f"대화 완료 확인 오류 (무시됨): {e}")
                
                await asyncio.sleep(0.1)
                consecutive_errors = 0  # 성공하면 연속 에러 카운트 리셋
                        
            except Exception as e:
                consecutive_errors += 1
                self.stats['loop_errors'] += 1
                
                logger.error(f"파이프라인 루프 오류 ({consecutive_errors}/{max_consecutive_errors}): {e}")
                
                # 연속 에러가 너무 많으면 종료
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("❌ 파이프라인 연속 에러 한계 초과 - 안전 종료")
                    break
                
                # 에러 후 점진적 대기 (백오프)
                await asyncio.sleep(min(consecutive_errors * 0.5, 3.0))

    def _get_stt_input(self) -> Optional[str]:
        """STT 큐에서 입력 가져오기"""
        try:
            return self.stt_queue.get_nowait()
        except queue.Empty:
            return None

    async def _safe_run_pipeline(self, user_input: str):
        """
        안전한 핵심 파이프라인: STT → AI → TTS
        - 모든 단계에서 에러 복구
        - 타임아웃 및 폴백 처리
        """
        start_time = time.time()
        self.is_processing = True
        self._set_state(ConversationState.PROCESSING)
        
        logger.info(f"🎬 파이프라인 시작: {user_input}")
        
        # 사용자 입력 알림
        if self.callbacks['on_user_speech']:
            try:
                self.callbacks['on_user_speech'](user_input)
            except Exception as e:
                logger.warning(f"사용자 입력 콜백 오류: {e}")
        
        ai_response = None
        
        try:
            # 🧠 Step 1: AI 두뇌에 전달 (안전하게)
            ai_response = await self._safe_ai_processing(user_input)
            
            if not ai_response:
                ai_response = "132번으로 상담받으세요."
            
            logger.info(f"🧠 AI 응답: {ai_response}")
            
            # AI 응답 알림
            if self.callbacks['on_ai_response']:
                try:
                    self.callbacks['on_ai_response'](ai_response)
                except Exception as e:
                    logger.warning(f"AI 응답 콜백 오류: {e}")
            
            # 🔊 Step 2: TTS 전달 (안전하게)
            await self._safe_deliver_response(ai_response)
            
            # 성능 통계
            pipeline_time = time.time() - start_time
            self._update_pipeline_stats(pipeline_time)
            
        except Exception as e:
            logger.error(f"파이프라인 실행 오류: {e}")
            await self._handle_pipeline_error(e, ai_response or "132번으로 연락주세요.")
        finally:
            self.is_processing = False
            self._set_state(ConversationState.LISTENING)

    async def _safe_ai_processing(self, user_input: str) -> str:
        """안전한 AI 처리"""
        try:
            # 새로운 인터페이스 확인
            if (hasattr(self.ai_brain, 'process_user_input') and 
                callable(getattr(self.ai_brain, 'process_user_input', None))):
                
                # 새로운 인터페이스 사용
                ai_response = await asyncio.wait_for(
                    self.ai_brain.process_user_input(user_input),
                    timeout=5.0
                )
                return ai_response
                
            else:
                # 폴백: 기존 방식 시도
                logger.warning("⚠️ 새 인터페이스 없음 - 기존 방식 시도")
                
                # 기존 continue_conversation 시도
                if hasattr(self.ai_brain, 'continue_conversation'):
                    # 임시 상태 생성
                    temp_state = {
                        'messages': [],
                        'conversation_turns': 0,
                        'current_step': 'greeting_complete'
                    }
                    
                    result_state = await asyncio.wait_for(
                        self.ai_brain.continue_conversation(temp_state, user_input),
                        timeout=5.0
                    )
                    
                    # 응답 추출
                    if result_state and result_state.get('messages'):
                        last_msg = result_state['messages'][-1]
                        if last_msg.get('role') == 'assistant':
                            return last_msg.get('content', '132번으로 상담받으세요.')
                
                return "132번으로 상담받으세요."
                
        except asyncio.TimeoutError:
            logger.warning("⏰ AI 처리 시간 초과")
            self.stats['ai_errors'] += 1
            return "처리 시간이 초과되었습니다. 132번으로 연락주세요."
        except Exception as e:
            logger.error(f"AI 처리 오류: {e}")
            self.stats['ai_errors'] += 1
            return "일시적 문제가 발생했습니다. 132번으로 연락주세요."

    async def _deliver_initial_greeting(self):
        """초기 인사 전달 (AI가 만든 것을 TTS로)"""
        try:
            # AI에서 인사말 가져오기 (안전하게)
            greeting = None
            
            if (hasattr(self.ai_brain, 'get_initial_greeting') and 
                callable(getattr(self.ai_brain, 'get_initial_greeting', None))):
                greeting = self.ai_brain.get_initial_greeting()
            
            if not greeting:
                greeting = "상담센터입니다. 어떤 도움이 필요하신가요?"
            
            await self._safe_deliver_response(greeting)
            
        except Exception as e:
            logger.error(f"초기 인사 전달 실패: {e}")
            # 폴백 인사
            await self._safe_deliver_response("상담센터입니다. 어떤 도움이 필요하신가요?")

    async def _safe_deliver_response(self, response_text: str):
        """안전한 응답 전달 (TTS + 오디오) - TTS 오류 수정 버전"""
        self._set_state(ConversationState.SPEAKING)
        
        try:
            if not self.tts_service.is_enabled:
                # TTS 비활성화시 텍스트로
                print(f"🤖 {response_text}")
                return
            
            # TTS 변환 (수정된 방식)
            try:
                # text_to_speech_stream은 async generator를 반환함
                # await를 사용하지 말고 직접 호출
                audio_stream = self.tts_service.text_to_speech_stream(response_text)
                
                # 타임아웃 적용을 위해 asyncio.wait_for 사용
                audio_stream = await asyncio.wait_for(
                    audio_stream,
                    timeout=4.0
                )
                
            except asyncio.TimeoutError:
                logger.warning("⏰ TTS 시간 초과")
                print(f"🤖 {response_text}")
                self.stats['tts_errors'] += 1
                return
            except Exception as tts_error:
                logger.error(f"TTS 변환 오류: {tts_error}")
                
                # 🔧 대안: text_to_speech_file 메서드 시도
                try:
                    logger.info("🔄 TTS 대안 방법 시도...")
                    audio_data = await asyncio.wait_for(
                        self.tts_service.text_to_speech_file(response_text),
                        timeout=4.0
                    )
                    
                    if audio_data:
                        # bytes를 async generator로 변환
                        async def bytes_to_stream():
                            chunk_size = 1024
                            for i in range(0, len(audio_data), chunk_size):
                                yield audio_data[i:i + chunk_size]
                        
                        audio_stream = bytes_to_stream()
                    else:
                        print(f"🤖 {response_text}")
                        self.stats['tts_errors'] += 1
                        return
                        
                except Exception as fallback_error:
                    logger.error(f"TTS 대안 방법도 실패: {fallback_error}")
                    print(f"🤖 {response_text}")
                    self.stats['tts_errors'] += 1
                    return
            
            # 오디오 재생 (안전하게)
            if audio_stream:
                try:
                    await self.audio_manager.play_audio_stream(audio_stream)
                except Exception as audio_error:
                    logger.error(f"오디오 재생 오류: {audio_error}")
                    print(f"🤖 {response_text}")
            else:
                print(f"🤖 {response_text}")
                
        except Exception as e:
            logger.error(f"TTS 전달 오류: {e}")
            print(f"🤖 {response_text}")
            self.stats['tts_errors'] += 1

    async def _handle_pipeline_error(self, error: Exception, fallback_response: str = None):
        """파이프라인 오류 처리"""
        self.error_count += 1
        current_time = time.time()
        
        # 에러 쿨다운 체크
        if (self.last_error_time and 
            current_time - self.last_error_time < self.error_cooldown):
            return  # 너무 빈번한 에러는 무시
        
        self.last_error_time = current_time
        
        if self.callbacks['on_error']:
            try:
                self.callbacks['on_error'](error)
            except Exception:
                pass
        
        # 폴백 응답
        if not fallback_response:
            fallback_response = "일시적 문제가 발생했습니다. 132번으로 연락주세요."
        
        await self._safe_deliver_response(fallback_response)

    def _update_pipeline_stats(self, pipeline_time: float):
        """파이프라인 성능 통계 업데이트"""
        self.stats['total_pipeline_runs'] += 1
        
        self.pipeline_times.append(pipeline_time)
        if len(self.pipeline_times) > self.max_history:
            self.pipeline_times.pop(0)
        
        if self.pipeline_times:
            self.stats['avg_pipeline_time'] = sum(self.pipeline_times) / len(self.pipeline_times)

    def _set_state(self, new_state: ConversationState):
        """오케스트레이터 상태 변경"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            
            if self.callbacks['on_state_change']:
                try:
                    self.callbacks['on_state_change'](old_state, new_state)
                except Exception as e:
                    logger.warning(f"상태 변경 콜백 오류: {e}")

    async def stop_conversation(self):
        """파이프라인 중지"""
        logger.info("🛑 파이프라인 중지")
        self.is_running = False
        
        try:
            # AI가 만든 마무리 메시지 전달
            farewell = None
            if (hasattr(self.ai_brain, 'get_farewell_message') and 
                callable(getattr(self.ai_brain, 'get_farewell_message', None))):
                farewell = self.ai_brain.get_farewell_message()
            
            if not farewell:
                farewell = "상담이 완료되었습니다."
                
            await self._safe_deliver_response(farewell)
        except Exception as e:
            logger.error(f"마무리 메시지 오류: {e}")

    async def cleanup(self):
        """파이프라인 정리"""
        logger.info("🧹 파이프라인 정리 중...")
        
        try:
            self.is_running = False
            self.is_processing = False
            
            # STT 정리
            if self.stt_client and hasattr(self.stt_client, 'stream'):
                try:
                    self.stt_client.stream.terminate()
                except:
                    pass
            
            # 큐 정리
            while not self.stt_queue.empty():
                try:
                    self.stt_queue.get_nowait()
                except queue.Empty:
                    break
            
            # 오디오 정리
            try:
                self.audio_manager.cleanup()
            except Exception as e:
                logger.warning(f"오디오 정리 오류: {e}")
            
            # AI 정리
            try:
                if (hasattr(self.ai_brain, 'cleanup') and 
                    callable(getattr(self.ai_brain, 'cleanup', None))):
                    await self.ai_brain.cleanup()
            except Exception as e:
                logger.warning(f"AI 정리 오류: {e}")
            
            # 통계 출력
            self._print_pipeline_stats()
            
            logger.info("✅ 파이프라인 정리 완료")
            
        except Exception as e:
            logger.error(f"정리 오류: {e}")

    def _print_pipeline_stats(self):
        """파이프라인 통계 출력"""
        if self.stats['conversation_start_time']:
            total_time = (datetime.now() - self.stats['conversation_start_time']).total_seconds()
            
            logger.info("📊 파이프라인 통계:")
            logger.info(f"   총 시간: {total_time:.1f}초")
            logger.info(f"   총 파이프라인 실행: {self.stats['total_pipeline_runs']}")
            logger.info(f"   평균 파이프라인 시간: {self.stats['avg_pipeline_time']:.3f}초")
            logger.info(f"   STT 오류: {self.stats['stt_errors']}")
            logger.info(f"   AI 오류: {self.stats['ai_errors']}")
            logger.info(f"   TTS 오류: {self.stats['tts_errors']}")
            logger.info(f"   루프 오류: {self.stats['loop_errors']}")

    # 🔗 외부 인터페이스들 (기존 호환성 유지)
    def set_callbacks(self, 
                     on_user_speech: Optional[Callable] = None,
                     on_ai_response: Optional[Callable] = None, 
                     on_state_change: Optional[Callable] = None,
                     on_error: Optional[Callable] = None):
        """콜백 설정"""
        if on_user_speech:
            self.callbacks['on_user_speech'] = on_user_speech
        if on_ai_response:
            self.callbacks['on_ai_response'] = on_ai_response
        if on_state_change:
            self.callbacks['on_state_change'] = on_state_change
        if on_error:
            self.callbacks['on_error'] = on_error

    def get_conversation_status(self) -> Dict[str, Any]:
        """대화 상태 (AI 상태 + 파이프라인 상태)"""
        elapsed_time = 0
        if self.stats['conversation_start_time']:
            elapsed_time = (datetime.now() - self.stats['conversation_start_time']).total_seconds()
        
        # AI 상태 가져오기 (안전하게)
        ai_status = {}
        try:
            if (hasattr(self.ai_brain, 'get_conversation_summary') and 
                callable(getattr(self.ai_brain, 'get_conversation_summary', None))):
                if hasattr(self.ai_brain, 'current_state') and self.ai_brain.current_state:
                    ai_status = self.ai_brain.get_conversation_summary(self.ai_brain.current_state)
        except Exception as e:
            logger.debug(f"AI 상태 조회 오류 (무시됨): {e}")
        
        return {
            # 파이프라인 상태
            "pipeline_state": self.state.value,
            "is_running": self.is_running,
            "is_processing": self.is_processing,
            "elapsed_time": elapsed_time,
            "avg_pipeline_time": self.stats['avg_pipeline_time'],
            "total_pipeline_runs": self.stats['total_pipeline_runs'],
            "error_count": self.error_count,
            
            # AI 상태 (위임) - 안전하게
            **ai_status
        }

    def get_audio_status(self) -> dict:
        """오디오 상태"""
        try:
            return self.audio_manager.get_performance_stats()
        except Exception as e:
            logger.warning(f"오디오 상태 조회 오류: {e}")
            return {
                'error': str(e),
                'is_available': False
            }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 지표"""
        try:
            audio_performance = self.audio_manager.get_performance_stats()
        except Exception:
            audio_performance = {'error': 'unavailable'}
        
        try:
            tts_performance = self.tts_service.get_performance_stats()
        except Exception:
            tts_performance = {'error': 'unavailable'}
        
        try:
            ai_performance = {}
            if (hasattr(self.ai_brain, 'get_conversation_summary') and 
                hasattr(self.ai_brain, 'current_state') and 
                self.ai_brain.current_state):
                ai_performance = self.ai_brain.get_conversation_summary(self.ai_brain.current_state)
        except Exception:
            ai_performance = {'error': 'unavailable'}
        
        return {
            **self.stats,
            "current_queue_size": self.stt_queue.qsize(),
            "pipeline_time_history": self.pipeline_times.copy(),
            "audio_performance": audio_performance,
            "tts_performance": tts_performance,
            "ai_performance": ai_performance
        }

# 하위 호환성
ConversationManager = VoiceFriendlyConversationManager