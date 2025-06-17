import asyncio
import logging
import pyaudio
import threading
import queue
import io
import time
from typing import Optional, Callable, AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from config.settings import settings

logger = logging.getLogger(__name__)

class HighPerformanceAudioManager:
    """
    고성능 오디오 매니저
    - 지연 시간 최소화
    - 메모리 효율성 개선
    - 동시 처리 최적화
    - 품질 적응형 처리
    """
    
    def __init__(self):
        self.pyaudio = pyaudio.PyAudio()
        self.output_stream = None
        
        # 재생 상태 관리
        self.is_playing = False
        self.is_initialized = False
        
        # 큐 시스템
        self.play_queue = queue.Queue(maxsize=5)  # 큐 크기 제한
        self.priority_queue = queue.PriorityQueue(maxsize=3)  # 우선순위 큐
        
        # 스레드 풀 (성능 최적화)
        self.thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="audio")
        self.play_thread = None
        
        # 성능 통계
        self.stats = {
            'total_played': 0,
            'avg_latency': 0.0,
            'conversion_time': 0.0,
            'queue_overflows': 0
        }
        
        # 오디오 설정 최적화
        self.audio_config = {
            'format': pyaudio.paInt16,
            'channels': 1,
            'rate': 44100,
            'chunk_size': 1024,
            'buffer_size': 4  # 버퍼 크기 최소화
        }
        
        # 변환 캐시 (메모리 효율성)
        self.conversion_cache = {}
        self.max_cache_size = 10
        
    def initialize_output(self) -> bool:
        """고성능 오디오 출력 초기화"""
        
        try:
            # 최적화된 출력 스트림
            self.output_stream = self.pyaudio.open(
                format=self.audio_config['format'],
                channels=self.audio_config['channels'],
                rate=self.audio_config['rate'],
                output=True,
                frames_per_buffer=self.audio_config['chunk_size'],
                stream_callback=None,  # 콜백 없이 직접 제어
                start=False  # 수동 시작
            )
            
            # 재생 워커 스레드 시작
            self.play_thread = threading.Thread(
                target=self._optimized_audio_worker, 
                daemon=True,
                name="AudioWorker"
            )
            self.play_thread.start()
            
            self.is_initialized = True
            logger.info("✅ 고성능 오디오 출력 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ 오디오 출력 초기화 실패: {e}")
            return False
    
    def _optimized_audio_worker(self):
        """최적화된 오디오 재생 워커"""
        
        while True:
            try:
                # 우선순위 큐 먼저 확인
                try:
                    priority, audio_data = self.priority_queue.get(timeout=0.1)
                    self._play_audio_direct(audio_data)
                    self.priority_queue.task_done()
                    continue
                except queue.Empty:
                    pass
                
                # 일반 큐 처리
                try:
                    audio_data = self.play_queue.get(timeout=0.5)
                    if audio_data is None:  # 종료 신호
                        break
                    
                    self._play_audio_direct(audio_data)
                    self.play_queue.task_done()
                    
                except queue.Empty:
                    continue
                    
            except Exception as e:
                logger.error(f"오디오 워커 오류: {e}")
                time.sleep(0.1)
    
    def _play_audio_direct(self, audio_data: bytes):
        """직접 오디오 재생 (최적화)"""
        
        start_time = time.time()
        self.is_playing = True
        
        try:
            # MP3 -> PCM 변환 (캐시 활용)
            pcm_data = self._convert_mp3_to_pcm_cached(audio_data)
            
            if pcm_data and self.output_stream:
                # 스트림 시작 (필요시)
                if not self.output_stream.is_active():
                    self.output_stream.start_stream()
                
                # 청크 단위로 재생 (지연 최소화)
                chunk_size = self.audio_config['chunk_size'] * 2  # 16bit = 2bytes
                
                for i in range(0, len(pcm_data), chunk_size):
                    chunk = pcm_data[i:i + chunk_size]
                    if chunk:
                        self.output_stream.write(chunk, exception_on_underflow=False)
                
                # 재생 완료 대기
                self.output_stream.stop_stream()
            
            # 통계 업데이트
            latency = time.time() - start_time
            self._update_stats(latency)
            
        except Exception as e:
            logger.error(f"직접 재생 오류: {e}")
        finally:
            self.is_playing = False
    
    def _convert_mp3_to_pcm_cached(self, mp3_data: bytes) -> bytes:
        """캐시된 MP3 -> PCM 변환"""
        
        # 캐시 키 생성 (데이터 해시)
        cache_key = hash(mp3_data) % 10000
        
        # 캐시 확인
        if cache_key in self.conversion_cache:
            return self.conversion_cache[cache_key]
        
        # 변환 수행
        start_time = time.time()
        pcm_data = self._convert_mp3_to_pcm_fast(mp3_data)
        conversion_time = time.time() - start_time
        
        # 캐시 저장 (크기 제한)
        if len(self.conversion_cache) < self.max_cache_size:
            self.conversion_cache[cache_key] = pcm_data
        
        # 통계 업데이트
        self.stats['conversion_time'] = (self.stats['conversion_time'] + conversion_time) / 2
        
        return pcm_data
    
    def _convert_mp3_to_pcm_fast(self, mp3_data: bytes) -> bytes:
        """고속 MP3 -> PCM 변환"""
        
        try:
            from pydub import AudioSegment
            
            # MP3 로드 (메모리 효율적)
            audio = AudioSegment.from_mp3(io.BytesIO(mp3_data))
            
            # 오디오 설정에 맞춰 변환
            audio = audio.set_frame_rate(self.audio_config['rate'])
            audio = audio.set_channels(self.audio_config['channels'])
            audio = audio.set_sample_width(2)  # 16bit
            
            return audio.raw_data
            
        except Exception as e:
            logger.error(f"MP3 변환 오류: {e}")
            return b""
    
    async def play_audio_stream(self, audio_stream: AsyncGenerator[bytes, None]):
        """스트리밍 오디오 재생 (최적화)"""
        
        try:
            # 스트림 데이터 수집 (비동기)
            audio_chunks = []
            chunk_count = 0
            max_chunks = 100  # 메모리 제한
            
            async for chunk in audio_stream:
                if chunk:
                    audio_chunks.append(chunk)
                    chunk_count += 1
                    
                    # 메모리 사용량 제한
                    if chunk_count >= max_chunks:
                        logger.warning("오디오 스트림 크기 제한 도달")
                        break
            
            if audio_chunks:
                # 청크 합성
                combined_audio = b"".join(audio_chunks)
                
                # 우선순위 재생 (긴급 메시지)
                if self._is_urgent_message(combined_audio):
                    await self._play_with_priority(combined_audio)
                else:
                    await self._play_normal(combined_audio)
                    
        except Exception as e:
            logger.error(f"스트림 재생 오류: {e}")
    
    def _is_urgent_message(self, audio_data: bytes) -> bool:
        """긴급 메시지 여부 판단 (크기 기반)"""
        # 짧은 메시지는 긴급으로 간주
        return len(audio_data) < 50000  # 50KB 미만
    
    async def _play_with_priority(self, audio_data: bytes):
        """우선순위 재생"""
        
        try:
            if not self.priority_queue.full():
                # 우선순위 0 (가장 높음)
                self.priority_queue.put_nowait((0, audio_data))
                
                # 재생 완료 대기 (비동기)
                await asyncio.to_thread(self.priority_queue.join)
            else:
                logger.warning("우선순위 큐 가득참")
                # 일반 큐로 폴백
                await self._play_normal(audio_data)
                
        except Exception as e:
            logger.error(f"우선순위 재생 오류: {e}")
    
    async def _play_normal(self, audio_data: bytes):
        """일반 재생"""
        
        try:
            if not self.play_queue.full():
                self.play_queue.put_nowait(audio_data)
                
                # 재생 완료 대기 (비동기)
                await asyncio.to_thread(self.play_queue.join)
            else:
                # 큐 오버플로우 처리
                self.stats['queue_overflows'] += 1
                logger.warning(f"오디오 큐 오버플로우 #{self.stats['queue_overflows']}")
                
                # 오래된 항목 제거 후 추가
                try:
                    self.play_queue.get_nowait()
                    self.play_queue.task_done()
                    self.play_queue.put_nowait(audio_data)
                except queue.Empty:
                    pass
                    
        except Exception as e:
            logger.error(f"일반 재생 오류: {e}")
    
    def play_audio_data(self, audio_data: bytes, priority: bool = False):
        """오디오 데이터 재생 (동기)"""
        
        try:
            if priority:
                asyncio.create_task(self._play_with_priority(audio_data))
            else:
                asyncio.create_task(self._play_normal(audio_data))
        except Exception as e:
            logger.error(f"오디오 재생 요청 오류: {e}")
    
    def is_audio_playing(self) -> bool:
        """재생 상태 확인"""
        return (self.is_playing or 
                not self.play_queue.empty() or 
                not self.priority_queue.empty())
    
    def stop_audio(self):
        """오디오 재생 중지"""
        
        try:
            # 모든 큐 비우기
            self._clear_all_queues()
            
            # 스트림 중지
            if self.output_stream and self.output_stream.is_active():
                self.output_stream.stop_stream()
            
            self.is_playing = False
            logger.info("🔇 오디오 재생 중지")
            
        except Exception as e:
            logger.error(f"오디오 중지 오류: {e}")
    
    def _clear_all_queues(self):
        """모든 큐 정리"""
        
        # 일반 큐 정리
        while not self.play_queue.empty():
            try:
                self.play_queue.get_nowait()
                self.play_queue.task_done()
            except queue.Empty:
                break
        
        # 우선순위 큐 정리
        while not self.priority_queue.empty():
            try:
                self.priority_queue.get_nowait()
                self.priority_queue.task_done()
            except queue.Empty:
                break
    
    def _update_stats(self, latency: float):
        """통계 업데이트"""
        
        self.stats['total_played'] += 1
        
        # 평균 지연시간 계산
        current_avg = self.stats['avg_latency']
        total_count = self.stats['total_played']
        self.stats['avg_latency'] = (current_avg * (total_count - 1) + latency) / total_count
    
    def get_performance_stats(self) -> dict:
        """성능 통계 조회"""
        
        return {
            **self.stats,
            'is_playing': self.is_playing,
            'queue_size': self.play_queue.qsize(),
            'priority_queue_size': self.priority_queue.qsize(),
            'cache_size': len(self.conversion_cache),
            'stream_active': self.output_stream.is_active() if self.output_stream else False
        }
    
    def optimize_for_speed(self):
        """속도 최적화 모드"""
        
        self.audio_config.update({
            'chunk_size': 512,  # 더 작은 청크
            'buffer_size': 2    # 더 작은 버퍼
        })
        
        self.max_cache_size = 20  # 더 큰 캐시
        logger.info("🚀 오디오 속도 최적화 모드 활성화")
    
    def optimize_for_quality(self):
        """품질 최적화 모드"""
        
        self.audio_config.update({
            'chunk_size': 2048,  # 더 큰 청크
            'buffer_size': 8     # 더 큰 버퍼
        })
        
        self.max_cache_size = 5  # 메모리 절약
        logger.info("🎵 오디오 품질 최적화 모드 활성화")
    
    def cleanup(self):
        """최적화된 리소스 정리"""
        
        try:
            logger.info("🧹 고성능 오디오 매니저 정리 중...")
            
            # 재생 중지
            self.stop_audio()
            
            # 워커 스레드 종료
            if self.play_thread and self.play_thread.is_alive():
                self.play_queue.put(None)  # 종료 신호
                self.play_thread.join(timeout=2)
            
            # 스레드 풀 종료
            if self.thread_pool:
                self.thread_pool.shutdown(wait=True) # ,timeout=3 제거
            
            # 스트림 정리
            if self.output_stream:
                if self.output_stream.is_active():
                    self.output_stream.stop_stream()
                self.output_stream.close()
            
            # PyAudio 종료
            if self.pyaudio:
                self.pyaudio.terminate()
            
            # 캐시 정리
            self.conversion_cache.clear()
            
            # 성능 통계 출력
            self._print_final_stats()
            
            logger.info("✅ 고성능 오디오 매니저 정리 완료")
            
        except Exception as e:
            logger.error(f"오디오 매니저 정리 오류: {e}")
    
    def _print_final_stats(self):
        """최종 성능 통계 출력"""
        
        stats = self.get_performance_stats()
        
        logger.info("📊 오디오 성능 통계:")
        logger.info(f"   총 재생 횟수: {stats['total_played']}")
        logger.info(f"   평균 지연시간: {stats['avg_latency']:.3f}초")
        logger.info(f"   평균 변환시간: {stats['conversion_time']:.3f}초")
        logger.info(f"   큐 오버플로우: {stats['queue_overflows']}")
        logger.info(f"   캐시 효율성: {stats['cache_size']}/{self.max_cache_size}")


# 하위 호환성을 위한 별칭 및 전역 인스턴스
AudioManager = HighPerformanceAudioManager
audio_manager = HighPerformanceAudioManager()