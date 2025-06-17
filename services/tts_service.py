import asyncio
import io
import logging
import time
import hashlib
import re
from typing import AsyncGenerator, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

try:
    from elevenlabs import ElevenLabs, AsyncElevenLabs
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    logging.warning("elevenlabs 패키지가 설치되지 않음. pip install elevenlabs")

from config.settings import settings

logger = logging.getLogger(__name__)

class VoiceFriendlyTTSService:
    """
    음성 친화적 TTS 서비스 - 수정된 안정 버전
    """
    
    def __init__(self):
        # API 키 및 라이브러리 확인
        if not ELEVENLABS_AVAILABLE:
            logger.warning("ElevenLabs 라이브러리 없음. TTS 비활성화.")
            self.client = None
            self.async_client = None
            self.is_enabled = False
        elif not settings.ELEVENLABS_API_KEY:
            logger.warning("ElevenLabs API key not found. TTS will be disabled.")
            self.client = None
            self.async_client = None
            self.is_enabled = False
        else:
            try:
                self.client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
                self.async_client = AsyncElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
                self.is_enabled = True
                logger.info("✅ ElevenLabs TTS 초기화 완료")
            except Exception as e:
                logger.error(f"ElevenLabs 초기화 실패: {e}")
                self.client = None
                self.async_client = None
                self.is_enabled = False
        
        # 음성 친화적 설정
        self.voice_config = {
            'voice_id': settings.TTS_VOICE_ID,
            'model': settings.TTS_MODEL,
            'output_format': 'mp3_22050_32',
            'optimize_latency': 3
        }
        
        # 성능 설정
        self.performance_config = {
            'max_text_length': 80,
            'max_sentence_length': 50,
            'timeout': 4.0,
            'max_retries': 1,
            'emergency_timeout': 2.0
        }
        
        # 간단한 캐시
        self.simple_cache = {}
        self.cache_max_size = 10
        
        # 통계
        self.stats = {
            'total_requests': 0,
            'fast_responses': 0,
            'timeouts': 0,
            'avg_response_time': 0.0
        }
        
        # 음성 변환 규칙
        self.voice_conversion_rules = {
            'phone_patterns': [
                (r'1811-0041', '일팔일일의 공공사일'),
                (r'132', '일삼이'),
                (r'112', '일일이'),
            ],
            'website_patterns': [
                (r'www\.[^\s]+', '웹사이트'),
                (r'https?://[^\s]+', '웹사이트'),
                (r'[a-zA-Z0-9-]+\.(?:co\.kr|or\.kr|com)', '웹사이트')
            ],
            'symbol_replacements': {
                '🚨': '긴급',
                '⚠️': '주의',
                '✅': '',
                '📞': '',
                '💰': '',
                '🔒': '',
                '1️⃣': '첫째',
                '2️⃣': '둘째',
                '3️⃣': '셋째',
                '4️⃣': '넷째'
            }
        }

    async def text_to_speech_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """음성 친화적 TTS 스트리밍 - 수정된 안정 버전"""
        
        if not self.is_enabled:
            logger.warning("TTS 서비스 비활성화됨")
            yield b''
            return
        
        start_time = time.time()
        self.stats['total_requests'] += 1
        
        try:
            # 1. 텍스트 음성 친화적 변환
            voice_friendly_text = self._make_voice_friendly(text)
            logger.debug(f"🔤 음성 친화적 변환: {voice_friendly_text}")
            
            # 2. 길이 체크 및 단축
            if len(voice_friendly_text) > self.performance_config['max_text_length']:
                voice_friendly_text = self._smart_truncate(voice_friendly_text)
                logger.debug(f"✂️ 텍스트 단축: {voice_friendly_text}")
            
            # 3. 빠른 TTS 처리
            audio_data = await self._fast_tts_processing(voice_friendly_text)
            
            if audio_data:
                # 4. 즉시 스트리밍
                logger.debug(f"🎵 오디오 스트리밍 시작 (크기: {len(audio_data)} bytes)")
                async for chunk in self._immediate_stream(audio_data):
                    yield chunk
                
                # 성능 통계
                response_time = time.time() - start_time
                if response_time <= 3.0:
                    self.stats['fast_responses'] += 1
                
                self._update_response_time(response_time)
                logger.debug(f"✅ TTS 완료 ({response_time:.2f}초)")
            else:
                logger.warning("TTS 처리 실패 - 빈 응답")
                yield b''
                
        except asyncio.TimeoutError:
            logger.warning("TTS 타임아웃 - 응답 생략")
            self.stats['timeouts'] += 1
            yield b''
        except Exception as e:
            logger.error(f"TTS 오류: {e}")
            yield b''

    def _make_voice_friendly(self, text: str) -> str:
        """텍스트를 음성 친화적으로 변환"""
        
        processed = text.strip()
        
        # 1. 특수문자 변환
        for symbol, replacement in self.voice_conversion_rules['symbol_replacements'].items():
            processed = processed.replace(symbol, replacement)
        
        # 2. 전화번호 음성 친화적 변환
        for pattern, replacement in self.voice_conversion_rules['phone_patterns']:
            processed = re.sub(pattern, replacement, processed)
        
        # 3. 웹사이트 주소 제거/단순화
        for pattern, replacement in self.voice_conversion_rules['website_patterns']:
            processed = re.sub(pattern, replacement, processed)
        
        # 4. 불필요한 구두점 정리
        processed = re.sub(r'\s+', ' ', processed)
        processed = re.sub(r'[•▪▫]', '', processed)
        
        # 5. 문장 끝 정리
        if not processed.endswith('.') and not processed.endswith('요') and not processed.endswith('다'):
            processed += '.'
        
        return processed.strip()

    def _smart_truncate(self, text: str) -> str:
        """스마트한 텍스트 단축"""
        
        max_length = self.performance_config['max_text_length']
        
        if len(text) <= max_length:
            return text
        
        # 문장 단위로 자르기
        sentences = text.split('.')
        result = []
        current_length = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if current_length + len(sentence) <= max_length - 3:
                result.append(sentence)
                current_length += len(sentence)
            else:
                break
        
        if result:
            return '. '.join(result) + '.'
        else:
            return text[:max_length-3] + '...'

    async def _fast_tts_processing(self, text: str) -> bytes:
        """빠른 TTS 처리 - 수정된 안정 버전"""
        
        # 캐시 확인
        cache_key = self._generate_simple_cache_key(text)
        if cache_key in self.simple_cache:
            logger.debug("📦 캐시에서 오디오 로드")
            return self.simple_cache[cache_key]
        
        def sync_tts_call():
            """동기 TTS 호출 - 수정된 안정 버전"""
            try:
                if not self.client:
                    logger.error("TTS 클라이언트가 초기화되지 않음")
                    return b''
                
                # ElevenLabs API 호출 방식 개선
                try:
                    # generate 메서드 사용 (더 안정적)
                    audio = self.client.generate(
                        text=text,
                        voice=self.voice_config['voice_id'],
                        model=self.voice_config['model'],
                        output_format=self.voice_config['output_format']
                    )
                    
                    # 오디오 데이터가 제너레이터인 경우 변환
                    if hasattr(audio, '__iter__') and not isinstance(audio, (bytes, str)):
                        chunks = []
                        for chunk in audio:
                            if isinstance(chunk, bytes):
                                chunks.append(chunk)
                        return b''.join(chunks)
                    elif isinstance(audio, bytes):
                        return audio
                    else:
                        logger.warning(f"예상치 못한 오디오 타입: {type(audio)}")
                        return b''
                        
                except AttributeError:
                    # generate 메서드가 없는 경우 text_to_speech 시도
                    logger.debug("generate 메서드 없음 - text_to_speech 시도")
                    audio = self.client.text_to_speech.convert(
                        text=text,
                        voice_id=self.voice_config['voice_id'],
                        model_id=self.voice_config['model'],
                        output_format=self.voice_config['output_format']
                    )
                    
                    if isinstance(audio, bytes):
                        return audio
                    else:
                        # 스트림인 경우 수집
                        chunks = []
                        for chunk in audio:
                            if isinstance(chunk, bytes):
                                chunks.append(chunk)
                        return b''.join(chunks)
                    
            except Exception as e:
                logger.error(f"TTS API 호출 실패: {e}")
                return b''
        
        try:
            # 긴급 타임아웃 적용
            timeout = (self.performance_config['emergency_timeout'] 
                      if any(word in text for word in ['긴급', '급해', '즉시']) 
                      else self.performance_config['timeout'])
            
            logger.debug(f"🎤 TTS 처리 시작 (타임아웃: {timeout}초)")
            
            audio_data = await asyncio.wait_for(
                asyncio.to_thread(sync_tts_call),
                timeout=timeout
            )
            
            # 캐시 저장
            if audio_data:
                self._save_to_simple_cache(cache_key, audio_data)
                logger.debug(f"💾 오디오 캐시 저장 (크기: {len(audio_data)} bytes)")
            
            return audio_data
            
        except asyncio.TimeoutError:
            logger.warning(f"TTS 타임아웃: {text[:30]}...")
            return b''
        except Exception as e:
            logger.error(f"TTS 처리 실패: {e}")
            return b''

    async def _immediate_stream(self, audio_data: bytes) -> AsyncGenerator[bytes, None]:
        """즉시 스트리밍"""
        
        if not audio_data:
            yield b''
            return
        
        # 작은 청크로 빠른 스트리밍
        chunk_size = 2048
        
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            if chunk:
                yield chunk
                await asyncio.sleep(0.001)

    def _generate_simple_cache_key(self, text: str) -> str:
        """간단한 캐시 키 생성"""
        return hashlib.md5(text.encode()).hexdigest()[:8]

    def _save_to_simple_cache(self, key: str, data: bytes):
        """간단한 캐시 저장"""
        
        if len(self.simple_cache) >= self.cache_max_size:
            oldest_key = next(iter(self.simple_cache))
            del self.simple_cache[oldest_key]
        
        self.simple_cache[key] = data

    def _update_response_time(self, response_time: float):
        """응답 시간 통계 업데이트"""
        
        current_avg = self.stats['avg_response_time']
        total_requests = self.stats['total_requests']
        
        self.stats['avg_response_time'] = (
            (current_avg * (total_requests - 1) + response_time) / total_requests
        )

    async def text_to_speech_file(self, text: str) -> bytes:
        """파일 방식 TTS (호환성용)"""
        
        audio_chunks = []
        async for chunk in self.text_to_speech_stream(text):
            if chunk:
                audio_chunks.append(chunk)
        
        return b''.join(audio_chunks)

    async def test_connection(self) -> bool:
        """빠른 연결 테스트"""
        
        if not self.is_enabled:
            logger.info("TTS 서비스가 비활성화되어 테스트 건너뜀")
            return False
        
        try:
            logger.info("🧪 TTS 연결 테스트 시작...")
            test_audio = await asyncio.wait_for(
                self.text_to_speech_file("테스트"),
                timeout=5.0
            )
            
            success = len(test_audio) > 0
            if success:
                logger.info("✅ TTS 테스트 성공")
            else:
                logger.warning("❌ TTS 테스트 실패 - 빈 응답")
            return success
            
        except asyncio.TimeoutError:
            logger.error("❌ TTS 테스트 타임아웃")
            return False
        except Exception as e:
            logger.error(f"❌ TTS 테스트 실패: {e}")
            return False

    def get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 조회"""
        
        total = self.stats['total_requests']
        fast_rate = (self.stats['fast_responses'] / total * 100) if total > 0 else 0
        timeout_rate = (self.stats['timeouts'] / total * 100) if total > 0 else 0
        
        return {
            'total_requests': total,
            'fast_response_rate': f"{fast_rate:.1f}%",
            'timeout_rate': f"{timeout_rate:.1f}%",
            'avg_response_time': f"{self.stats['avg_response_time']:.3f}초",
            'cache_size': len(self.simple_cache),
            'is_enabled': self.is_enabled
        }

    def cleanup(self):
        """간단한 정리"""
        
        try:
            logger.info("🧹 TTS 서비스 정리 중...")
            
            # 캐시 정리
            self.simple_cache.clear()
            
            # 최종 통계
            stats = self.get_performance_stats()
            logger.info("📊 TTS 최종 통계:")
            logger.info(f"   총 요청: {stats['total_requests']}")
            logger.info(f"   빠른 응답률: {stats['fast_response_rate']}")
            logger.info(f"   타임아웃률: {stats['timeout_rate']}")
            logger.info(f"   평균 응답시간: {stats['avg_response_time']}")
            
            logger.info("✅ TTS 서비스 정리 완료")
            
        except Exception as e:
            logger.error(f"TTS 정리 오류: {e}")

# 하위 호환성을 위한 별칭 및 전역 인스턴스
TTSService = VoiceFriendlyTTSService
tts_service = VoiceFriendlyTTSService()