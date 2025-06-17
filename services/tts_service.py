import asyncio
import io
import logging
import time
import hashlib
import re
from typing import AsyncGenerator, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from elevenlabs import ElevenLabs, AsyncElevenLabs
from config.settings import settings

logger = logging.getLogger(__name__)

class VoiceFriendlyTTSService:
    """
    음성 친화적 TTS 서비스
    - 응답 길이 대폭 단축 (최대 80자)
    - 즉시 재생 우선 (3초 이내)
    - 전화번호 음성 친화적 변환
    - 웹사이트 주소 음성 제외
    - 한 문장씩 처리
    """
    
    def __init__(self):
        # API 키 확인
        if not settings.ELEVENLABS_API_KEY:
            logger.warning("ElevenLabs API key not found. TTS will be disabled.")
            self.client = None
            self.async_client = None
            self.is_enabled = False
        else:
            self.client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
            self.async_client = AsyncElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
            self.is_enabled = True
        
        # 음성 친화적 설정 (속도 우선)
        self.voice_config = {
            'voice_id': settings.TTS_VOICE_ID,
            'model': settings.TTS_MODEL,
            'output_format': 'mp3_22050_32',  # 빠른 처리용
            'optimize_latency': 3             # 최대 지연 최적화
        }
        
        # 성능 우선 설정
        self.performance_config = {
            'max_text_length': 80,      # 최대 80자
            'max_sentence_length': 50,  # 문장당 50자
            'timeout': 3.0,             # 3초 타임아웃
            'max_retries': 1,           # 재시도 1회만
            'emergency_timeout': 1.5    # 긴급시 1.5초
        }
        
        # 간단한 캐시 (최근 10개만)
        self.simple_cache = {}
        self.cache_max_size = 10
        
        # 성능 통계
        self.stats = {
            'total_requests': 0,
            'fast_responses': 0,  # 3초 이내 응답
            'timeouts': 0,
            'avg_response_time': 0.0
        }
        
        # 음성 친화적 변환 규칙
        self.voice_conversion_rules = {
            # 전화번호 변환
            'phone_patterns': [
                (r'1811-0041', '일팔일일의 공공사일'),
                (r'132', '일삼이'),
                (r'112', '일일이'),
                (r'1588-\d{4}', lambda m: self._convert_phone_number(m.group(0))),
                (r'1599-\d{4}', lambda m: self._convert_phone_number(m.group(0)))
            ],
            
            # 웹사이트 제거 (음성으로 말하기 어려움)
            'website_patterns': [
                (r'www\.[^\s]+', '웹사이트'),
                (r'https?://[^\s]+', '웹사이트'),
                (r'[a-zA-Z0-9-]+\.(?:co\.kr|or\.kr|com)', '웹사이트')
            ],
            
            # 특수문자 음성 친화적 변환
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
        """음성 친화적 TTS 스트리밍"""
        
        if not self.is_enabled:
            logger.error("TTS 서비스가 비활성화됨")
            yield b''
            return
        
        start_time = time.time()
        self.stats['total_requests'] += 1
        
        try:
            # 1. 텍스트 음성 친화적 변환
            voice_friendly_text = self._make_voice_friendly(text)
            
            # 2. 길이 체크 및 단축
            if len(voice_friendly_text) > self.performance_config['max_text_length']:
                voice_friendly_text = self._smart_truncate(voice_friendly_text)
            
            # 3. 빠른 TTS 처리
            audio_data = await self._fast_tts_processing(voice_friendly_text)
            
            if audio_data:
                # 4. 즉시 스트리밍
                async for chunk in self._immediate_stream(audio_data):
                    yield chunk
                
                # 성능 통계
                response_time = time.time() - start_time
                if response_time <= 3.0:
                    self.stats['fast_responses'] += 1
                
                self._update_response_time(response_time)
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
            if callable(replacement):
                processed = re.sub(pattern, replacement, processed)
            else:
                processed = re.sub(pattern, replacement, processed)
        
        # 3. 웹사이트 주소 제거/단순화
        for pattern, replacement in self.voice_conversion_rules['website_patterns']:
            processed = re.sub(pattern, replacement, processed)
        
        # 4. 불필요한 구두점 정리
        processed = re.sub(r'\s+', ' ', processed)  # 연속 공백 제거
        processed = re.sub(r'[•▪▫]', '', processed)  # 불릿 포인트 제거
        
        # 5. 문장 끝 정리
        if not processed.endswith('.') and not processed.endswith('요') and not processed.endswith('다'):
            processed += '.'
        
        return processed.strip()
    
    def _convert_phone_number(self, phone: str) -> str:
        """전화번호를 음성 친화적으로 변환"""
        
        # 1588-1234 → 일오팔팔의 일이삼사
        number_map = {
            '0': '공', '1': '일', '2': '이', '3': '삼', '4': '사',
            '5': '오', '6': '육', '7': '칠', '8': '팔', '9': '구'
        }
        
        parts = phone.split('-')
        if len(parts) == 2:
            first_part = ''.join(number_map.get(d, d) for d in parts[0])
            second_part = ''.join(number_map.get(d, d) for d in parts[1])
            return f"{first_part}의 {second_part}"
        else:
            return ''.join(number_map.get(d, d) for d in phone.replace('-', ''))
    
    def _smart_truncate(self, text: str) -> str:
        """스마트한 텍스트 단축"""
        
        max_length = self.performance_config['max_text_length']
        
        if len(text) <= max_length:
            return text
        
        # 1. 문장 단위로 자르기
        sentences = text.split('.')
        result = []
        current_length = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if current_length + len(sentence) <= max_length - 3:  # '...' 여유분
                result.append(sentence)
                current_length += len(sentence)
            else:
                break
        
        if result:
            return '. '.join(result) + '.'
        else:
            # 첫 문장이 너무 길면 강제로 자르기
            return text[:max_length-3] + '...'
    
    async def _fast_tts_processing(self, text: str) -> bytes:
        """빠른 TTS 처리"""
        
        # 캐시 확인
        cache_key = self._generate_simple_cache_key(text)
        if cache_key in self.simple_cache:
            return self.simple_cache[cache_key]
        
        def sync_fast_tts():
            """동기 TTS 호출 (속도 최적화)"""
            try:
                # stream 방식으로 빠른 처리
                audio_stream = self.client.text_to_speech.stream(
                    text=text,
                    voice_id=self.voice_config['voice_id'],
                    model_id=self.voice_config['model'],
                    output_format=self.voice_config['output_format']
                )
                
                chunks = []
                for chunk in audio_stream:
                    if isinstance(chunk, bytes):
                        chunks.append(chunk)
                
                return b''.join(chunks)
                
            except Exception as e:
                logger.warning(f"빠른 TTS 실패: {e}")
                return b''
        
        try:
            # 긴급 타임아웃 적용
            timeout = (self.performance_config['emergency_timeout'] 
                      if '긴급' in text or '급해' in text 
                      else self.performance_config['timeout'])
            
            audio_data = await asyncio.wait_for(
                asyncio.to_thread(sync_fast_tts),
                timeout=timeout
            )
            
            # 간단한 캐시 저장
            self._save_to_simple_cache(cache_key, audio_data)
            
            return audio_data
            
        except asyncio.TimeoutError:
            logger.warning(f"TTS 타임아웃: {text[:30]}...")
            return b''
    
    async def _immediate_stream(self, audio_data: bytes) -> AsyncGenerator[bytes, None]:
        """즉시 스트리밍 (지연 최소화)"""
        
        if not audio_data:
            yield b''
            return
        
        # 작은 청크로 빠른 스트리밍
        chunk_size = 2048  # 작은 청크
        
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            if chunk:
                yield chunk
                # 지연 최소화
                await asyncio.sleep(0.001)
    
    def _generate_simple_cache_key(self, text: str) -> str:
        """간단한 캐시 키 생성"""
        return hashlib.md5(text.encode()).hexdigest()[:8]
    
    def _save_to_simple_cache(self, key: str, data: bytes):
        """간단한 캐시 저장"""
        
        # 캐시 크기 제한
        if len(self.simple_cache) >= self.cache_max_size:
            # 가장 오래된 항목 하나 제거
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
            return False
        
        try:
            test_audio = await asyncio.wait_for(
                self.text_to_speech_file("테스트"),
                timeout=2.0  # 2초로 단축
            )
            
            success = len(test_audio) > 0
            if success:
                logger.info("✅ 음성 친화적 TTS 테스트 성공")
            else:
                logger.warning("❌ TTS 테스트 실패")
            return success
            
        except asyncio.TimeoutError:
            logger.error("TTS 테스트 타임아웃")
            return False
        except Exception as e:
            logger.error(f"TTS 테스트 실패: {e}")
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
    
    def optimize_for_emergency(self):
        """응급 상황용 최적화"""
        
        self.performance_config.update({
            'max_text_length': 50,    # 더욱 단축
            'timeout': 2.0,           # 더욱 빠르게
            'emergency_timeout': 1.5  # 응급시 1.5초
        })
        
        self.voice_config['output_format'] = 'mp3_22050_32'  # 최저 품질, 최고 속도
        logger.info("🚨 응급 상황용 TTS 최적화 완료")
    
    def cleanup(self):
        """간단한 정리"""
        
        try:
            logger.info("🧹 음성 친화적 TTS 정리 중...")
            
            # 캐시 정리
            self.simple_cache.clear()
            
            # 최종 통계
            stats = self.get_performance_stats()
            logger.info("📊 TTS 최종 통계:")
            logger.info(f"   총 요청: {stats['total_requests']}")
            logger.info(f"   빠른 응답률: {stats['fast_response_rate']}")
            logger.info(f"   타임아웃률: {stats['timeout_rate']}")
            logger.info(f"   평균 응답시간: {stats['avg_response_time']}")
            
            logger.info("✅ 음성 친화적 TTS 정리 완료")
            
        except Exception as e:
            logger.error(f"TTS 정리 오류: {e}")


# 하위 호환성을 위한 별칭 및 전역 인스턴스
TTSService = VoiceFriendlyTTSService
OptimizedTTSService = VoiceFriendlyTTSService
tts_service = VoiceFriendlyTTSService()