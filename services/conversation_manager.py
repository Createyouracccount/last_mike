"""
수정된 Conversation Manager - 올바른 LangGraph 노드 실행
"""

import asyncio
import logging
import threading
import time
import queue
from datetime import datetime
from typing import Optional, Dict, Any, Callable, Protocol
from enum import Enum

from services.stream_stt import RTZROpenAPIClient
from core.graph import VoiceFriendlyPhishingGraph
from services.tts_service import tts_service
from services.audio_manager import audio_manager
from config.settings import settings

logger = logging.getLogger(__name__)

class ConversationState(Enum):
    """대화 상태"""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"

class FixedVoiceFriendlyConversationManager:
    """
    수정된 음성 대화 매니저 - 올바른 LangGraph 노드 실행
    """
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        
        # 🔥 핵심: AI 두뇌를 올바르게 사용
        self.ai_brain = VoiceFriendlyPhishingGraph(debug=settings.DEBUG)
        self.tts_service = tts_service
        self.audio_manager = audio_manager
        
        # STT 컴포넌트
        self.stt_client = None
        self.stt_queue = queue.Queue(maxsize=5)
        self.stt_thread: Optional[threading.Thread] = None

        # 상태 관리
        self.state = ConversationState.IDLE
        self.is_running = False
        self.is_processing = False
        self.initialization_complete = False
        self.error_count = 0

        # 🔥 핵심: LangGraph 상태 관리
        self.current_graph_state = None
        self.session_id = None

        # 콜백 관리
        self.callbacks: Dict[str, Optional[Callable]] = {
            'on_user_speech': None,
            'on_ai_response': None,
            'on_state_change': None,
            'on_error': None
        }
        
        # 성능 통계
        self.stats = {
            'conversation_start_time': None,
            'initialization_attempts': 0,
            'total_pipeline_runs': 0,
            'avg_pipeline_time': 0.0,
            'stt_errors': 0,
            'ai_errors': 0,
            'tts_errors': 0,
        }
        
        logger.info("✅ 수정된 대화 매니저 초기화 완료")

    async def initialize(self) -> bool:
        """개선된 파이프라인 초기화"""
        self.stats['initialization_attempts'] += 1
        logger.info(f"🎬 음성 대화 파이프라인 초기화 (시도 {self.stats['initialization_attempts']})...")
        
        try:
            # 1. 오디오 매니저 초기화
            logger.info("🔊 오디오 매니저 초기화 중...")
            if not self.audio_manager.initialize_output():
                logger.error("❌ 오디오 파이프라인 실패")
                return False
            logger.info("✅ 오디오 파이프라인 준비")
            
            # 2. STT 클라이언트 생성
            logger.info("🎤 STT 클라이언트 생성 중...")
            self.stt_client = RTZROpenAPIClient(self.client_id, self.client_secret)
            logger.info("✅ STT 클라이언트 준비")
            
            # 🔥 핵심 수정: LangGraph 세션 시작
            logger.info("🧠 LangGraph 세션 시작 중...")
            self.session_id = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.current_graph_state = await self.ai_brain.start_conversation(self.session_id)
            logger.info(f"✅ LangGraph 세션 시작: {self.session_id}")
            
            # 4. 초기 인사 (LangGraph에서 생성된 메시지 사용)
            await self._deliver_langgraph_greeting()
            
            self.initialization_complete = True
            self.stats['conversation_start_time'] = datetime.now()
            self._set_state(ConversationState.LISTENING)
            
            logger.info("🎉 파이프라인 초기화 완료!")
            return True
            
        except Exception as e:
            logger.error(f"❌ 파이프라인 초기화 실패: {e}")
            return False

    async def _deliver_langgraph_greeting(self):
        """LangGraph에서 생성된 초기 인사 전달"""
        try:
            # LangGraph 상태에서 마지막 AI 메시지 가져오기
            if self.current_graph_state and self.current_graph_state.get("messages"):
                messages = self.current_graph_state["messages"]
                for msg in reversed(messages):
                    if msg.get("role") == "assistant":
                        greeting_text = msg.get("content", "")
                        if greeting_text:
                            await self._safe_tts_delivery(greeting_text)
                            logger.info("✅ LangGraph 초기 인사 전달 완료")
                            return
            
            # 폴백: 기본 인사
            fallback_greeting = "안녕하세요. 보이스피싱 상담센터입니다. 1번 또는 2번을 선택해주세요."
            await self._safe_tts_delivery(fallback_greeting)
            logger.warning("⚠️ LangGraph 인사 없음 - 폴백 사용")
            
        except Exception as e:
            logger.error(f"초기 인사 전달 실패: {e}")

    async def start_conversation(self):
        """대화 시작"""
        if not await self.initialize():
            logger.error("❌ 파이프라인 시작 실패")
            return
        
        self.is_running = True
        logger.info("🎙️ 음성 대화 시작")
        
        try:
            # STT 입력 시작
            self._start_stt_input_safe()
            
            # 메인 루프
            await self._safe_main_loop()
            
        except KeyboardInterrupt:
            logger.info("사용자 종료")
        except Exception as e:
            logger.error(f"대화 실행 오류: {e}")
        finally:
            await self.cleanup()

    def _start_stt_input_safe(self):
        """안전한 STT 입력 시작"""
        def stt_worker():
            retry_count = 0
            max_retries = 3
            
            while self.is_running and retry_count < max_retries:
                try:
                    logger.info(f"🎤 STT 스트림 시작 시도 {retry_count + 1}/{max_retries}")
                    
                    if self.stt_client:
                        self.stt_client.reset_stream()
                    
                    def transcript_handler(start_time, transcript, is_final=False):
                        if is_final and transcript.alternatives:
                            text = transcript.alternatives[0].text.strip()
                            if text and len(text) > 1:
                                self._safe_add_to_queue(text)
                                logger.debug(f"🎤 STT 입력: {text}")
                    
                    self.stt_client.print_transcript = transcript_handler
                    self.stt_client.transcribe_streaming_grpc()
                    
                    logger.info("✅ STT 스트림 성공적으로 시작됨")
                    break
                    
                except Exception as e:
                    retry_count += 1
                    self.stats['stt_errors'] += 1
                    logger.error(f"STT 스트림 오류 (시도 {retry_count}): {e}")
                    
                    if retry_count < max_retries:
                        logger.info(f"🔄 {retry_count + 1}초 후 STT 재시도...")
                        time.sleep(retry_count + 1)
                    else:
                        logger.error("❌ STT 스트림 최대 재시도 횟수 초과")
                        break
        
        self.stt_thread = threading.Thread(
            target=stt_worker, 
            daemon=True, 
            name="STT-Worker"
        )
        self.stt_thread.start()
        logger.info("🎤 STT 워커 스레드 시작됨")

    def _safe_add_to_queue(self, text: str):
        """안전한 큐 추가"""
        try:
            if not self.stt_queue.full():
                self.stt_queue.put_nowait(text)
            else:
                try:
                    self.stt_queue.get_nowait()
                    self.stt_queue.put_nowait(text)
                except queue.Empty:
                    pass
        except Exception as e:
            logger.warning(f"큐 추가 오류: {e}")

    async def _safe_main_loop(self):
        """안전한 메인 루프"""
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        logger.info("🔄 메인 처리 루프 시작")
        
        while self.is_running:
            try:
                # STT 입력 확인
                user_input = self._get_stt_input()
                
                if user_input and not self.is_processing:
                    logger.info(f"👤 사용자 입력 감지: {user_input}")
                    # 🔥 핵심: LangGraph 노드 시스템 사용
                    await self._process_through_langgraph(user_input)
                
                # 대화 완료 확인
                if self._check_conversation_complete():
                    logger.info("✅ 대화 완료 신호 감지")
                    break
                
                await asyncio.sleep(0.1)
                consecutive_errors = 0
                        
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"메인 루프 오류 ({consecutive_errors}/{max_consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("❌ 메인 루프 연속 오류 한계 초과")
                    break
                
                await asyncio.sleep(min(consecutive_errors * 0.5, 3.0))

    def _get_stt_input(self) -> Optional[str]:
        """STT 큐에서 입력 가져오기"""
        try:
            return self.stt_queue.get_nowait()
        except queue.Empty:
            return None

    async def _process_through_langgraph(self, user_input: str):
        """🔥 핵심: LangGraph 노드 시스템을 통한 처리"""
        self.is_processing = True
        self._set_state(ConversationState.PROCESSING)
        
        start_time = time.time()
        
        try:
            # 사용자 입력 콜백
            if self.callbacks['on_user_speech']:
                try:
                    self.callbacks['on_user_speech'](user_input)
                except Exception as e:
                    logger.warning(f"사용자 입력 콜백 오류: {e}")
            
            # 🔥 핵심: LangGraph의 continue_conversation 사용
            logger.info("🧠 LangGraph 노드 시스템으로 처리 중...")
            
            self.current_graph_state = await self.ai_brain.continue_conversation(
                self.current_graph_state, 
                user_input
            )
            
            # 🔥 핵심: LangGraph 상태에서 AI 응답 추출
            ai_response = self._extract_latest_ai_response()
            
            if ai_response:
                logger.info(f"🤖 LangGraph AI 응답: {ai_response}")
                
                # AI 응답 콜백
                if self.callbacks['on_ai_response']:
                    try:
                        self.callbacks['on_ai_response'](ai_response)
                    except Exception as e:
                        logger.warning(f"AI 응답 콜백 오류: {e}")
                
                # TTS 처리
                await self._safe_tts_delivery(ai_response)
            else:
                logger.warning("LangGraph에서 AI 응답을 생성하지 못함")
            
            # 통계 업데이트
            processing_time = time.time() - start_time
            self._update_pipeline_stats(processing_time)
            
        except Exception as e:
            logger.error(f"LangGraph 처리 오류: {e}")
            await self._handle_processing_error(e)
        finally:
            self.is_processing = False
            self._set_state(ConversationState.LISTENING)

    def _extract_latest_ai_response(self) -> Optional[str]:
        """LangGraph 상태에서 최신 AI 응답 추출"""
        try:
            if not self.current_graph_state or not self.current_graph_state.get("messages"):
                return None
            
            messages = self.current_graph_state["messages"]
            
            # 마지막 AI 메시지 찾기
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    content = msg.get("content", "").strip()
                    if content:
                        return content
            
            return None
            
        except Exception as e:
            logger.error(f"AI 응답 추출 오류: {e}")
            return None

    async def _safe_tts_delivery(self, response_text: str):
        """안전한 TTS 전달"""
        self._set_state(ConversationState.SPEAKING)
        
        try:
            if not self.tts_service.is_enabled:
                print(f"🤖 {response_text}")
                return
            
            try:
                audio_stream = self.tts_service.text_to_speech_stream(response_text)
                await self.audio_manager.play_audio_stream(audio_stream)
                
            except Exception as tts_error:
                logger.error(f"TTS 처리 오류: {tts_error}")
                print(f"🤖 {response_text}")
                self.stats['tts_errors'] += 1
                
        except Exception as e:
            logger.error(f"TTS 전달 오류: {e}")
            print(f"🤖 {response_text}")

    def _check_conversation_complete(self) -> bool:
        """대화 완료 여부 확인"""
        try:
            # 🔥 핵심: LangGraph AI 두뇌의 완료 여부 확인
            return self.ai_brain.is_conversation_complete()
        except Exception as e:
            logger.debug(f"대화 완료 확인 오류 (무시됨): {e}")
            return False

    async def _handle_processing_error(self, error: Exception):
        """처리 오류 핸들링"""
        self.error_count += 1
        
        if self.callbacks['on_error']:
            try:
                self.callbacks['on_error'](error)
            except Exception:
                pass
        
        fallback_response = "일시적 문제가 발생했습니다. 132번으로 연락주세요."
        await self._safe_tts_delivery(fallback_response)

    def _update_pipeline_stats(self, processing_time: float):
        """파이프라인 통계 업데이트"""
        self.stats['total_pipeline_runs'] += 1
        
        current_avg = self.stats['avg_pipeline_time']
        total_runs = self.stats['total_pipeline_runs']
        self.stats['avg_pipeline_time'] = (
            (current_avg * (total_runs - 1) + processing_time) / total_runs
        )

    def _set_state(self, new_state: ConversationState):
        """상태 변경"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            
            if self.callbacks['on_state_change']:
                try:
                    self.callbacks['on_state_change'](old_state, new_state)
                except Exception as e:
                    logger.warning(f"상태 변경 콜백 오류: {e}")

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
        """대화 상태 조회"""
        elapsed_time = 0
        if self.stats['conversation_start_time']:
            elapsed_time = (datetime.now() - self.stats['conversation_start_time']).total_seconds()
        
        return {
            "state": self.state.value,
            "is_running": self.is_running,
            "is_processing": self.is_processing,
            "initialization_complete": self.initialization_complete,
            "elapsed_time": elapsed_time,
            "total_turns": self.stats['total_pipeline_runs'],
            "avg_response_time": self.stats['avg_pipeline_time'],
            "error_count": self.error_count,
            "stt_errors": self.stats['stt_errors'],
            "ai_errors": self.stats['ai_errors'],
            "tts_errors": self.stats['tts_errors'],
            "current_graph_state": self.current_graph_state.get("current_step") if self.current_graph_state else None,
            "session_id": self.session_id
        }

    def get_audio_status(self) -> dict:
        """오디오 상태"""
        try:
            return self.audio_manager.get_performance_stats()
        except Exception as e:
            logger.warning(f"오디오 상태 조회 오류: {e}")
            return {'error': str(e), 'is_available': False}

    async def cleanup(self):
        """파이프라인 정리"""
        logger.info("🧹 파이프라인 정리 중...")
        
        try:
            self.is_running = False
            self.is_processing = False
            
            # STT 스레드 정리
            if self.stt_thread and self.stt_thread.is_alive():
                logger.info("🎤 STT 스레드 종료 대기...")
                self.stt_thread.join(timeout=3)
            
            # STT 클라이언트 정리
            if self.stt_client and hasattr(self.stt_client, 'stream'):
                try:
                    self.stt_client.stream.terminate()
                except Exception as e:
                    logger.debug(f"STT 스트림 종료 오류 (무시됨): {e}")
            
            # 큐 정리
            while not self.stt_queue.empty():
                try:
                    self.stt_queue.get_nowait()
                except queue.Empty:
                    break
            
            # 오디오 매니저 정리
            try:
                self.audio_manager.cleanup()
            except Exception as e:
                logger.warning(f"오디오 정리 오류: {e}")
            
            # 🔥 핵심: LangGraph AI 정리
            try:
                if self.ai_brain:
                    await self.ai_brain.cleanup()
            except Exception as e:
                logger.warning(f"LangGraph 정리 오류: {e}")
            
            # 최종 통계
            self._print_final_stats()
            
            logger.info("✅ 파이프라인 정리 완료")
            
        except Exception as e:
            logger.error(f"정리 오류: {e}")

    def _print_final_stats(self):
        """최종 통계 출력"""
        if self.stats['conversation_start_time']:
            total_time = (datetime.now() - self.stats['conversation_start_time']).total_seconds()
            
            logger.info("📊 최종 파이프라인 통계:")
            logger.info(f"   총 시간: {total_time:.1f}초")
            logger.info(f"   총 파이프라인 실행: {self.stats['total_pipeline_runs']}")
            logger.info(f"   평균 처리 시간: {self.stats['avg_pipeline_time']:.3f}초")
            logger.info(f"   초기화 시도: {self.stats['initialization_attempts']}")
            logger.info(f"   STT 오류: {self.stats['stt_errors']}")
            logger.info(f"   AI 오류: {self.stats['ai_errors']}")
            logger.info(f"   TTS 오류: {self.stats['tts_errors']}")


# 하위 호환성
VoiceFriendlyConversationManager = FixedVoiceFriendlyConversationManager
ConversationManager = FixedVoiceFriendlyConversationManager