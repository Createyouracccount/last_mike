import configparser
import logging
import os
import queue
import sys
import time
from pathlib import Path
import threading

import grpc
import pyaudio
from requests import Session

API_BASE = "https://openapi.vito.ai"
GRPC_SERVER_URL = "grpc-openapi.vito.ai:443"

VOICE_PHISHING_KEYWORDS = [
    # 전화번호 (한글 발음)
    "일삼이", "일팔일일", "일일이", "일삼삼이",
    
    # 핵심 용어
    "보이스피싱", "피싱", "명의도용", "계좌이체", "지급정지",
    "사기신고", "신고", "송금", "악성앱", "원격제어",
    
    # 기관명
    "금융감독원", "보이스피싱제로", "대한법률구조공단",
    
    # 서비스 (한글만)
    "엠세이퍼", "페이인포", "패스앱",
    
    # 금액/피해 관련
    "만원", "백만원", "천만원", "개인정보", "비밀번호",
    "환급", "지원금", "신청", "피해신고", "상담"
]

SAMPLE_RATE = 6000

# 프로토콜 버퍼 import 수정
try:
    # 현재 디렉토리에서 import 시도
    import vito_stt_client_pb2 as pb
    import vito_stt_client_pb2_grpc as pb_grpc
except ImportError:
    try:
        # services 디렉토리에서 import 시도
        from services import vito_stt_client_pb2 as pb
        from services import vito_stt_client_pb2_grpc as pb_grpc
    except ImportError:
        try:
            # 상대 경로로 import 시도
            from . import vito_stt_client_pb2 as pb
            from . import vito_stt_client_pb2_grpc as pb_grpc
        except ImportError:
            # 절대 경로로 마지막 시도
            sys.path.append(str(Path(__file__).parent))
            import vito_stt_client_pb2 as pb
            import vito_stt_client_pb2_grpc as pb_grpc

API_BASE = "https://openapi.vito.ai"
GRPC_SERVER_URL = "grpc-openapi.vito.ai:443"

SAMPLE_RATE = 16000
FORMAT = pyaudio.paInt16
CHANNELS = 1 if sys.platform == "darwin" else 2
RECORD_SECONDS = 10
# CHUNK = int(SAMPLE_RATE / 10)  # 100ms chunk
CHUNK = 400
ENCODING = pb.DecoderConfig.AudioEncoding.LINEAR16
# ENCODING = pb.DecoderConfig.AudioEncoding.OGG_OPUS

def get_config(keywords=None):
    """
    keywords를 받아서, config를 동적으로 생성하는 함수
    """
    return pb.DecoderConfig(
        sample_rate=SAMPLE_RATE,
        encoding=ENCODING,
        use_itn=True,
        use_disfluency_filter=False,
        use_profanity_filter=False,
        keywords=keywords,
    )


class MicrophoneStream:
    """
    Ref[1]: https://cloud.google.com/speech-to-text/docs/transcribe-streaming-audio

    Recording Stream을 생성하고 오디오 청크를 생성하는 제너레이터를 반환하는 클래스.
    """

    def __init__(
        self: object,
        rate: int = SAMPLE_RATE,
        chunk: int = CHUNK,
        channels: int = CHANNELS,
        format=FORMAT,
    ) -> None:
        self._rate = rate
        self._chunk = chunk
        self._channels = channels
        self._format = format

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self._rate,
            input=True,
            frames_per_buffer=self._chunk,
            stream_callback=self._fill_buffer,
        )

        self.closed = False

    def terminate(
        self: object,
    ) -> None:
        """
        Stream을 닫고, 제너레이터를 종료하는 함수
        """
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(
        self: object,
        in_data: object,
        frame_count: int,
        time_info: object,
        status_flags: object,
    ) -> object:
        """
        오디오 Stream으로부터 데이터를 수집하고 버퍼에 저장하는 콜백 함수.

        Args:
            in_data: 바이트 오브젝트로 된 오디오 데이터
            frame_count: 프레임 카운트
            time_info: 시간 정보
            status_flags: 상태 플래그

        Returns:
            바이트 오브젝트로 된 오디오 데이터
        """
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self: object) -> object:
        """
        Stream으로부터 오디오 청크를 생성하는 Generator.

        Args:
            self: The MicrophoneStream object

        Returns:
            오디오 청크를 생성하는 Generator
        """
        while not self.closed:
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b"".join(data)


class RTZROpenAPIClient:
    def __init__(self, client_id, client_secret):
        super().__init__()
        self._logger = logging.getLogger(__name__)
        self.client_id = client_id
        self.client_secret = client_secret

        self._sess = Session()
        self._token = None

    def reset_stream(self):
        self.stream = MicrophoneStream(SAMPLE_RATE, CHUNK, CHANNELS, FORMAT)

    @property
    def token(self):
        """
        Access Token을 서버에 요청해서 얻어오는 프로퍼티.
        """
        if self._token is None or self._token["expire_at"] < time.time():
            resp = self._sess.post(
                API_BASE + "/v1/authenticate",
                data={"client_id": self.client_id, "client_secret": self.client_secret},
            )
            resp.raise_for_status()
            self._token = resp.json()
        return self._token["access_token"]

    def print_transcript(self, start_time, transcript, is_final=False):
        clear_line_escape = "\033[K"  # clear line Escape Sequence
        if not is_final:
            end_time_str = "~"
            end_chr = "\r"
        else:
            end_time_str = f"~ {(start_time + transcript.duration / 1000):.2f}"
            end_chr = None
        print(f"{clear_line_escape}{start_time:.2f} {end_time_str} : {transcript.alternatives[0].text}", end=end_chr)

    def transcribe_streaming_grpc(self):
        """
        grpc를 이용해서 스트리밍 STT 수행 하는 메소드
        """
        base = GRPC_SERVER_URL
        with grpc.secure_channel(base, credentials=grpc.ssl_channel_credentials()) as channel:
            stub = pb_grpc.OnlineDecoderStub(channel)
            cred = grpc.access_token_call_credentials(self.token)

            def req_iterator(keywords):
                yield pb.DecoderRequest(streaming_config=get_config(keywords))

                self.reset_stream()
                for chunk in self.stream.generator():
                    yield pb.DecoderRequest(audio_content=chunk)

            keyword_idx = False
            keywords = {
                True : VOICE_PHISHING_KEYWORDS,
                False : VOICE_PHISHING_KEYWORDS,
            }

            global_st_time = time.time()
            while True:
                keyword_idx = not keyword_idx

                req_iter = req_iterator(keywords=keywords[keyword_idx])
                resp_iter = stub.Decode(req_iter, credentials=cred)
                session_st_time = time.time() - global_st_time
                for resp in resp_iter:
                    resp: pb.DecoderResponse
                    for res in resp.results:
                        if res.is_final:
                            self.stream.terminate()
                        self.print_transcript(session_st_time, res, is_final=res.is_final)

    def __del__(self):
        if hasattr(self, 'stream'):
            self.stream.terminate()

    def prepare_audio_for_streaming(self, audio_file_data: bytes) -> bytes:
        """오디오를 스트리밍에 적합한 형태로 변환"""
        
        try:
            from pydub import AudioSegment
            from io import BytesIO
            
            print(f"🔄 [오디오 변환] 시작: {len(audio_file_data)} bytes")
            
            # 메모리에서 오디오 로드
            audio_io = BytesIO(audio_file_data)
            
            # 포맷 자동 감지하여 로드
            try:
                audio = AudioSegment.from_file(audio_io, format="webm")
            except:
                try:
                    audio_io.seek(0)
                    audio = AudioSegment.from_file(audio_io, format="mp4")
                except:
                    audio_io.seek(0)
                    audio = AudioSegment.from_file(audio_io)
            
            # RTZR STT 요구사항에 맞춰 변환
            # "Audio file must be a 16-bit signed little-endian encoded with a sample rate of 16000"
            audio = audio.set_frame_rate(SAMPLE_RATE)  # 16kHz
            audio = audio.set_channels(1)              # Mono
            audio = audio.set_sample_width(2)          # 16bit
            
            # Raw PCM 데이터 반환
            pcm_data = audio.raw_data
            
            print(f"🔄 [오디오 변환] {len(audio_file_data)} bytes → {len(pcm_data)} bytes PCM")
            print(f"🎵 [오디오 변환] {audio.frame_rate}Hz, {audio.channels}ch, {audio.sample_width*8}bit")
            
            return pcm_data
            
        except Exception as e:
            print(f"❌ [오디오 변환] 실패: {e}")
            return audio_file_data  # 원본 데이터 반환
    
    def transcribe_file_streaming(self, pcm_data: bytes) -> str:
        """파일 데이터를 실시간 스트리밍으로 처리"""
        
        import threading
        import queue
        import time
        
        print(f"🚀 [파일 스트리밍] 시작: {len(pcm_data)} bytes PCM")
        
        # 결과 수집
        result_queue = queue.Queue()
        collected_texts = []
        processing_complete = threading.Event()
        
        def transcript_handler(start_time, transcript, is_final=False):
            """실시간 결과 수집 (수정된 버전)"""
            if transcript and transcript.alternatives:
                text = transcript.alternatives[0].text.strip()
                if text and len(text) > 1:
                    print(f"📝 [파일 스트리밍] 수신: '{text}' (최종: {is_final})")
                    
                    # 🔥 핵심 수정: 최종 결과와 중간 결과 모두 수집
                    if is_final:
                        collected_texts.append(text)
                        result_queue.put(('final', text))
                        print(f"✅ [파일 스트리밍] 최종 텍스트 수집: '{text}'")
                    else:
                        # 중간 결과도 백업으로 저장 (최종 결과가 없을 경우 사용)
                        if text not in collected_texts:  # 중복 방지
                            result_queue.put(('interim', text))
                            print(f"🔄 [파일 스트리밍] 중간 텍스트 백업: '{text}'")
        
        # 기존 콜백을 우리 콜백으로 완전히 교체
        original_callback = getattr(self, 'print_transcript', None)
        # 🔥 핵심: 콜백을 직접 호출하도록 수정
        def response_processor(resp_iter):
            """응답 처리기"""
            for resp in resp_iter:
                if resp.error:
                    print(f"❌ [gRPC 파일] gRPC 오류: {resp.error}")
                    break
                
                # 각 결과 처리
                for res in resp.results:
                    # 우리 transcript_handler 직접 호출
                    transcript_handler(0, res, is_final=res.is_final)
            
            # 처리 완료 신호
            processing_complete.set()

        try:
            # gRPC 스트리밍 실행 (수정된 버전)
            success = self._execute_file_streaming_fixed(pcm_data, response_processor)
            
            if success:
                # 처리 완료 대기 (최대 10초)
                if processing_complete.wait(timeout=10.0):
                    if collected_texts:
                        final_result = " ".join(collected_texts)
                        print(f"✅ [파일 스트리밍] 최종 결과: '{final_result}'")
                        return final_result
                    else:
                        # 최종 결과가 없으면 중간 결과라도 사용
                        interim_texts = []
                        while not result_queue.empty():
                            try:
                                msg_type, text = result_queue.get_nowait()
                                if text not in interim_texts:
                                    interim_texts.append(text)
                            except queue.Empty:
                                break
                        
                        if interim_texts:
                            fallback_result = " ".join(interim_texts)
                            print(f"🔄 [파일 스트리밍] 중간 결과 사용: '{fallback_result}'")
                            return fallback_result
                        else:
                            print("⚠️ [파일 스트리밍] 텍스트 결과 없음")
                else:
                    print("⏰ [파일 스트리밍] 처리 시간 초과")
            
            return ""
            
        except Exception as e:
            print(f"❌ [파일 스트리밍] 전체 오류: {e}")
            return ""
        finally:
            # 콜백 복원
            if original_callback:
                self.print_transcript = original_callback
    
    def _execute_file_streaming_fixed(self, pcm_data: bytes, response_processor) -> bool:
        """수정된 gRPC 파일 스트리밍 실행"""
        
        try:
            print(f"📡 [gRPC 파일] PCM 데이터: {len(pcm_data)} bytes")
            
            # gRPC 연결
            base = GRPC_SERVER_URL
            with grpc.secure_channel(base, credentials=grpc.ssl_channel_credentials()) as channel:
                stub = pb_grpc.OnlineDecoderStub(channel)
                cred = grpc.access_token_call_credentials(self.token)
                
                def file_req_iterator():
                    """파일 기반 요청 이터레이터"""
                    
                    # 1. 설정 전송
                    config = get_config(VOICE_PHISHING_KEYWORDS)
                    yield pb.DecoderRequest(streaming_config=config)
                    print("📋 [gRPC 파일] 설정 전송 완료")
                    
                    # 2. PCM 데이터를 청크로 분할 전송
                    chunk_duration_ms = 20  # 100ms 청크
                    bytes_per_sample = 2    # 16bit
                    chunk_size = int((SAMPLE_RATE * chunk_duration_ms / 1000) * bytes_per_sample)
                    
                    total_chunks = len(pcm_data) // chunk_size + (1 if len(pcm_data) % chunk_size else 0)
                    print(f"📡 [gRPC 파일] {total_chunks}개 청크로 실시간 전송 (청크당 {chunk_duration_ms}ms)")
                    
                    for i, start in enumerate(range(0, len(pcm_data), chunk_size)):
                        chunk = pcm_data[start:start + chunk_size]
                        if chunk:
                            yield pb.DecoderRequest(audio_content=chunk)
                            
                            # 실시간 시뮬레이션
                            time.sleep(chunk_duration_ms / 1000.0)
                            
                            # 진행 상황 로그
                            if (i + 1) % 10 == 0 or i == total_chunks - 1:
                                progress = (i + 1) / total_chunks * 100
                                print(f"📡 [gRPC 파일] 진행률: {progress:.1f}% ({i+1}/{total_chunks})")
                
                # 3. gRPC 스트리밍 실행
                print("🔄 [gRPC 파일] 스트리밍 시작")
                
                req_iter = file_req_iterator()
                resp_iter = stub.Decode(req_iter, credentials=cred)
                
                # 4. 응답 처리 (수정된 방식)
                response_processor(resp_iter)
                
                return True
                
        except Exception as e:
            print(f"❌ [gRPC 파일] 실행 오류: {e}")
            return False