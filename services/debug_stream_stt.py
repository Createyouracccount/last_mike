# 🔧 디버깅 및 테스트 환경 설정
# 경로: avoice/voice_core/services/debug_stream_stt.py (새 파일)

import configparser
import logging
import os
import queue
import sys
import time
from pathlib import Path
import threading
import json
from typing import Dict, Any, Optional

import grpc
import pyaudio
from requests import Session

import os
from pathlib import Path

# .env 파일 경로들 확인
env_paths = [
    Path("C:/Users/kimdu/Desktop/pishingcare_last/voice/voice_core/.env"),
    Path("C:/Users/kimdu/Desktop/pishingcare_last/.env"),
    Path(".env")
]

print("🔍 .env 파일 찾기:")
for path in env_paths:
    exists = path.exists()
    print(f"  {'✅' if exists else '❌'} {path}")

# 4. python-dotenv로 .env 로딩
try:
    from dotenv import load_dotenv
    
    # 모든 .env 파일 로딩 시도
    for path in env_paths:
        if path.exists():
            load_dotenv(path)
            print(f"✅ {path} 로딩 완료")
    
    # 환경변수 확인
    rtzr_id = os.getenv('RETURNZERO_CLIENT_ID')
    rtzr_secret = os.getenv('RETURNZERO_CLIENT_SECRET')
    vito_id = os.getenv('VITO_CLIENT_ID') 
    vito_secret = os.getenv('VITO_CLIENT_SECRET')
    
    print("\n🔑 환경변수 확인:")
    print(f"  RETURNZERO_CLIENT_ID: {'✅' if rtzr_id else '❌'}")
    print(f"  RETURNZERO_CLIENT_SECRET: {'✅' if rtzr_secret else '❌'}")
    print(f"  VITO_CLIENT_ID: {'✅' if vito_id else '❌'}")
    print(f"  VITO_CLIENT_SECRET: {'✅' if vito_secret else '❌'}")
    
except ImportError:
    print("❌ python-dotenv 패키지 필요: pip install python-dotenv")

# 기본 설정
API_BASE = "https://openapi.vito.ai"
GRPC_SERVER_URL = "grpc-openapi.vito.ai:443"
SAMPLE_RATE = 16000

# 🚀 테스트용 설정들
TEST_CONFIGS = {
    "original": {
        "encoding": "LINEAR16",
        "chunk_duration_ms": 100,
        "description": "기존 설정"
    },
    "optimized_opus": {
        "encoding": "OGG_OPUS", 
        "chunk_duration_ms": 20,
        "description": "OPUS + 20ms (최고 최적화)"
    },
    "safe_linear": {
        "encoding": "LINEAR16",
        "chunk_duration_ms": 20, 
        "description": "LINEAR16 + 20ms (안전한 최적화)"
    },
    "high_quality": {
        "encoding": "OGG_OPUS",
        "chunk_duration_ms": 50,
        "description": "OPUS + 50ms (품질 중시)"
    }
}


VOICE_PHISHING_KEYWORDS = [
    "일삼이", "일팔일일", "일일이", "일삼삼이",
    "보이스피싱", "피싱", "명의도용", "계좌이체", "지급정지",
    "사기신고", "신고", "송금", "악성앱", "원격제어",
    "금융감독원", "보이스피싱제로", "대한법률구조공단",
    "엠세이퍼", "페이인포", "패스앱",
    "만원", "백만원", "천만원", "개인정보", "비밀번호",
    "환급", "지원금", "신청", "피해신고", "상담"
]

# 프로토콜 버퍼 import
try:
    import vito_stt_client_pb2 as pb
    import vito_stt_client_pb2_grpc as pb_grpc
    print("✅ [디버그] 프로토콜 버퍼 import 성공")
except ImportError as e:
    print(f"❌ [디버그] 프로토콜 버퍼 import 실패: {e}")
    try:
        from services import vito_stt_client_pb2 as pb
        from services import vito_stt_client_pb2_grpc as pb_grpc
        print("✅ [디버그] services에서 import 성공")
    except ImportError:
        try:
            from . import vito_stt_client_pb2 as pb
            from . import vito_stt_client_pb2_grpc as pb_grpc
            print("✅ [디버그] 상대경로 import 성공")
        except ImportError:
            sys.path.append(str(Path(__file__).parent))
            import vito_stt_client_pb2 as pb
            import vito_stt_client_pb2_grpc as pb_grpc
            print("✅ [디버그] 절대경로 import 성공")

class DebugRTZRClient:
    """🔧 디버깅 기능이 포함된 RTZR 클라이언트"""
    
    def __init__(self, client_id: str, client_secret: str, debug_mode: bool = True):
        self._logger = logging.getLogger(__name__)
        self.client_id = client_id
        self.client_secret = client_secret
        self.debug_mode = debug_mode
        
        self._sess = Session()
        self._token = None
        
        # 🔧 디버깅 정보 수집
        self.debug_info = {
            "initialization_time": time.time(),
            "tests_performed": [],
            "performance_metrics": {},
            "errors": []
        }
        
        if debug_mode:
            print("🔧 [디버그] DebugRTZRClient 초기화 완료")
    
    def diagnose_environment(self) -> Dict[str, Any]:
        """🔍 현재 환경 진단"""
        
        print("🔍 [진단] 환경 진단 시작")
        diagnosis = {
            "timestamp": time.time(),
            "environment": {},
            "files": {},
            "imports": {},
            "network": {},
            "auth": {}
        }
        
        # 1. 환경 정보
        try:
            diagnosis["environment"] = {
                "python_version": sys.version,
                "platform": sys.platform,
                "working_directory": os.getcwd(),
                "path_exists": {
                    "current_file": __file__ if '__file__' in globals() else "N/A",
                    "services_dir": Path("avoice/voice_core/services").exists(),
                    "stream_stt": Path("avoice/voice_core/services/stream_stt.py").exists()
                }
            }
            print("✅ [진단] 환경 정보 수집 완료")
        except Exception as e:
            diagnosis["environment"]["error"] = str(e)
            print(f"❌ [진단] 환경 정보 수집 실패: {e}")
        
        # 2. 파일 존재 확인
        try:
            files_to_check = [
                "avoice/voice_core/services/stream_stt.py",
                "avoice/voice_core/services/vito_stt_client_pb2.py", 
                "avoice/voice_core/services/vito_stt_client_pb2_grpc.py",
                "avoice/voice_core/.env"
            ]
            
            diagnosis["files"] = {}
            for file_path in files_to_check:
                path_obj = Path(file_path)
                diagnosis["files"][file_path] = {
                    "exists": path_obj.exists(),
                    "size": path_obj.stat().st_size if path_obj.exists() else 0,
                    "modified": path_obj.stat().st_mtime if path_obj.exists() else 0
                }
            
            print("✅ [진단] 파일 존재 확인 완료")
        except Exception as e:
            diagnosis["files"]["error"] = str(e)
            print(f"❌ [진단] 파일 확인 실패: {e}")
        
        # 3. Import 테스트
        try:
            diagnosis["imports"] = {
                "pb_available": 'pb' in globals(),
                "pb_grpc_available": 'pb_grpc' in globals(),
                "encoding_options": []
            }
            
            if 'pb' in globals():
                # 사용 가능한 인코딩 옵션 확인
                try:
                    encoding_enum = pb.DecoderConfig.AudioEncoding
                    available_encodings = [name for name in dir(encoding_enum) 
                                         if not name.startswith('_')]
                    diagnosis["imports"]["encoding_options"] = available_encodings
                    print(f"✅ [진단] 사용 가능한 인코딩: {available_encodings}")
                except Exception as e:
                    diagnosis["imports"]["encoding_error"] = str(e)
            
            print("✅ [진단] Import 테스트 완료")
        except Exception as e:
            diagnosis["imports"]["error"] = str(e)
            print(f"❌ [진단] Import 테스트 실패: {e}")
        
        # 4. 인증 정보 확인
        try:
            diagnosis["auth"] = {
                "client_id_exists": bool(self.client_id),
                "client_secret_exists": bool(self.client_secret),
                "env_vars": {
                    "RETURNZERO_CLIENT_ID": bool(os.getenv('RETURNZERO_CLIENT_ID')),
                    "RETURNZERO_CLIENT_SECRET": bool(os.getenv('RETURNZERO_CLIENT_SECRET'))
                }
            }
            print("✅ [진단] 인증 정보 확인 완료")
        except Exception as e:
            diagnosis["auth"]["error"] = str(e)
            print(f"❌ [진단] 인증 정보 확인 실패: {e}")
        
        # 5. 네트워크 연결 테스트
        try:
            print("🌐 [진단] 네트워크 연결 테스트 중...")
            resp = self._sess.get(API_BASE + "/v1/health", timeout=5)
            diagnosis["network"] = {
                "api_reachable": resp.status_code == 200,
                "response_time": resp.elapsed.total_seconds(),
                "status_code": resp.status_code
            }
            print("✅ [진단] 네트워크 연결 테스트 완료")
        except Exception as e:
            diagnosis["network"] = {
                "api_reachable": False,
                "error": str(e)
            }
            print(f"❌ [진단] 네트워크 연결 실패: {e}")
        
        # 진단 결과 저장
        self.debug_info["diagnosis"] = diagnosis
        
        # 진단 리포트 출력
        self._print_diagnosis_report(diagnosis)
        
        return diagnosis
    
    def _print_diagnosis_report(self, diagnosis: Dict[str, Any]):
        """📋 진단 리포트 출력"""
        
        print("\n" + "="*60)
        print("📋 [진단 리포트] 환경 진단 결과")
        print("="*60)
        
        # 환경 정보
        env = diagnosis.get("environment", {})
        print(f"🐍 Python: {env.get('python_version', 'N/A').split()[0]}")
        print(f"💻 Platform: {env.get('platform', 'N/A')}")
        print(f"📁 작업 디렉토리: {env.get('working_directory', 'N/A')}")
        
        # 파일 상태
        files = diagnosis.get("files", {})
        print(f"\n📄 중요 파일들:")
        for file_path, info in files.items():
            if isinstance(info, dict):
                status = "✅" if info.get("exists") else "❌"
                size = info.get("size", 0)
                print(f"  {status} {file_path} ({size} bytes)")
        
        # Import 상태
        imports = diagnosis.get("imports", {})
        print(f"\n📦 Import 상태:")
        print(f"  프로토콜 버퍼: {'✅' if imports.get('pb_available') else '❌'}")
        print(f"  gRPC 클라이언트: {'✅' if imports.get('pb_grpc_available') else '❌'}")
        
        encodings = imports.get("encoding_options", [])
        if encodings:
            print(f"  사용 가능한 인코딩: {', '.join(encodings)}")
        
        # 인증 상태
        auth = diagnosis.get("auth", {})
        print(f"\n🔑 인증 정보:")
        print(f"  Client ID: {'✅' if auth.get('client_id_exists') else '❌'}")
        print(f"  Client Secret: {'✅' if auth.get('client_secret_exists') else '❌'}")
        
        # 네트워크 상태
        network = diagnosis.get("network", {})
        print(f"\n🌐 네트워크:")
        print(f"  API 연결: {'✅' if network.get('api_reachable') else '❌'}")
        if network.get("response_time"):
            print(f"  응답 시간: {network['response_time']:.3f}초")
        
        print("="*60)
    
    @property
    def token(self):
        """Access Token 획득 (디버깅 포함)"""
        if self._token is None or self._token["expire_at"] < time.time():
            try:
                print("🔑 [디버그] 토큰 요청 시작")
                start_time = time.time()
                
                resp = self._sess.post(
                    API_BASE + "/v1/authenticate",
                    data={"client_id": self.client_id, "client_secret": self.client_secret},
                )
                resp.raise_for_status()
                self._token = resp.json()
                
                elapsed = time.time() - start_time
                print(f"✅ [디버그] 토큰 획득 성공 ({elapsed:.3f}초)")
                
                self.debug_info["performance_metrics"]["token_acquisition_time"] = elapsed
                
            except Exception as e:
                print(f"❌ [디버그] 토큰 획득 실패: {e}")
                self.debug_info["errors"].append({
                    "type": "token_acquisition",
                    "error": str(e),
                    "timestamp": time.time()
                })
                raise
                
        return self._token["access_token"]
    
    def test_multiple_configurations(self, pcm_data: bytes) -> Dict[str, Any]:
        """🧪 여러 설정으로 성능 테스트"""
        
        print("🧪 [테스트] 다중 설정 성능 테스트 시작")
        test_results = {}
        
        for config_name, config in TEST_CONFIGS.items():
            print(f"\n🔬 [테스트] {config_name} 설정 테스트: {config['description']}")
            
            try:
                start_time = time.time()
                
                # 설정 적용
                result = self._test_single_configuration(
                    pcm_data, 
                    config["encoding"],
                    config["chunk_duration_ms"]
                )
                
                elapsed_time = time.time() - start_time
                
                test_results[config_name] = {
                    "config": config,
                    "result": result,
                    "elapsed_time": elapsed_time,
                    "success": bool(result),
                    "timestamp": time.time()
                }
                
                print(f"✅ [테스트] {config_name} 완료: {elapsed_time:.2f}초")
                
            except Exception as e:
                test_results[config_name] = {
                    "config": config,
                    "error": str(e),
                    "elapsed_time": None,
                    "success": False,
                    "timestamp": time.time()
                }
                print(f"❌ [테스트] {config_name} 실패: {e}")
        
        # 결과 비교 출력
        self._print_test_comparison(test_results)
        
        # 디버깅 정보에 저장
        self.debug_info["tests_performed"].append({
            "type": "multi_configuration_test",
            "results": test_results,
            "timestamp": time.time()
        })
        
        return test_results
    
    def _test_single_configuration(self, pcm_data: bytes, encoding: str, chunk_duration_ms: int) -> str:
        """단일 설정 테스트"""
        
        # 동적으로 설정 생성
        def get_test_config(keywords=None):
            encoding_value = getattr(pb.DecoderConfig.AudioEncoding, encoding)
            return pb.DecoderConfig(
                sample_rate=SAMPLE_RATE,
                encoding=encoding_value,
                use_itn=True,
                use_disfluency_filter=False,
                use_profanity_filter=False,
                keywords=keywords,
            )
        
        try:
            base = GRPC_SERVER_URL
            with grpc.secure_channel(base, credentials=grpc.ssl_channel_credentials()) as channel:
                stub = pb_grpc.OnlineDecoderStub(channel)
                cred = grpc.access_token_call_credentials(self.token)
                
                collected_texts = []
                
                def test_req_iterator():
                    # 설정 전송
                    config = get_test_config(VOICE_PHISHING_KEYWORDS)
                    yield pb.DecoderRequest(streaming_config=config)
                    
                    # 청크 전송
                    bytes_per_sample = 2
                    chunk_size = int((SAMPLE_RATE * chunk_duration_ms / 1000) * bytes_per_sample)
                    
                    for start in range(0, len(pcm_data), chunk_size):
                        chunk = pcm_data[start:start + chunk_size]
                        if chunk:
                            yield pb.DecoderRequest(audio_content=chunk)
                            time.sleep(chunk_duration_ms / 1000.0)
                
                req_iter = test_req_iterator()
                resp_iter = stub.Decode(req_iter, credentials=cred)
                
                for resp in resp_iter:
                    if resp.error:
                        print(f"❌ gRPC 오류: {resp.error}")
                        break
                    
                    for res in resp.results:
                        if res.is_final and res.alternatives:
                            text = res.alternatives[0].text.strip()
                            if text:
                                collected_texts.append(text)
                
                return " ".join(collected_texts)
                
        except Exception as e:
            print(f"❌ 테스트 실행 오류: {e}")
            raise
    
    def _print_test_comparison(self, test_results: Dict[str, Any]):
        """📊 테스트 결과 비교 출력"""
        
        print("\n" + "="*80)
        print("📊 [테스트 결과] 성능 비교")
        print("="*80)
        
        # 성공한 테스트들만 정렬 (시간순)
        successful_tests = {
            name: result for name, result in test_results.items() 
            if result.get("success") and result.get("elapsed_time")
        }
        
        if successful_tests:
            sorted_tests = sorted(
                successful_tests.items(), 
                key=lambda x: x[1]["elapsed_time"]
            )
            
            print("🏆 성능 순위 (빠른 순):")
            for i, (name, result) in enumerate(sorted_tests, 1):
                config = result["config"]
                elapsed = result["elapsed_time"]
                text_result = result.get("result", "")
                
                print(f"{i}. {name}")
                print(f"   설정: {config['encoding']} + {config['chunk_duration_ms']}ms")
                print(f"   시간: {elapsed:.2f}초")
                print(f"   결과: {text_result[:50]}..." if len(text_result) > 50 else f"   결과: {text_result}")
                print()
            
            # 최고 성능과 비교
            fastest = sorted_tests[0]
            fastest_time = fastest[1]["elapsed_time"]
            
            print("⚡ 성능 개선 비율:")
            for name, result in sorted_tests:
                if name != fastest[0]:
                    improvement = (result["elapsed_time"] / fastest_time)
                    print(f"   {name}: {improvement:.1f}x 느림")
        
        # 실패한 테스트들
        failed_tests = {
            name: result for name, result in test_results.items() 
            if not result.get("success")
        }
        
        if failed_tests:
            print("\n❌ 실패한 테스트들:")
            for name, result in failed_tests.items():
                error = result.get("error", "알 수 없는 오류")
                print(f"   {name}: {error}")
        
        print("="*80)
    
    def save_debug_report(self, filename: str = None):
        """💾 디버깅 리포트 저장"""
        
        if not filename:
            timestamp = int(time.time())
            filename = f"debug_report_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.debug_info, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"💾 [디버그] 리포트 저장 완료: {filename}")
            return filename
            
        except Exception as e:
            print(f"❌ [디버그] 리포트 저장 실패: {e}")
            return None

# 🧪 테스트 실행 함수
def run_comprehensive_test():
    """🧪 종합적인 테스트 실행"""
    
    print("🚀 [종합 테스트] 시작")
    
    # 1. 환경변수에서 인증 정보 가져오기
    client_id = os.getenv('RETURN_CLIENT_ID')
    client_secret = os.getenv('RETURN_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("❌ [종합 테스트] 환경변수 RTZR_CLIENT_ID, RTZR_CLIENT_SECRET 필요")
        print("💡 .env 파일에 설정하거나 환경변수로 설정하세요")
        return
    
    # 2. 디버그 클라이언트 생성
    debug_client = DebugRTZRClient(client_id, client_secret, debug_mode=True)
    
    # 3. 환경 진단
    diagnosis = debug_client.diagnose_environment()
    
    # 4. 테스트용 PCM 데이터 생성 (또는 실제 파일 사용)
    test_pcm_data = create_test_audio_data()
    
    if test_pcm_data:
        # 5. 다중 설정 테스트
        test_results = debug_client.test_multiple_configurations(test_pcm_data)
        
        # 6. 리포트 저장
        report_file = debug_client.save_debug_report()
        
        print(f"\n🎉 [종합 테스트] 완료!")
        print(f"📋 리포트 파일: {report_file}")
    else:
        print("❌ [종합 테스트] 테스트용 오디오 데이터 없음")

def create_test_audio_data() -> bytes:
    """🎵 테스트용 오디오 데이터 생성"""
    
    # 실제 음성 파일이 있다면 사용
    test_files = [
        "test_audio.webm",
        "test_audio.mp3", 
        "test_audio.wav",
        "avoice/test_audio.webm"
    ]
    
    for test_file in test_files:
        if Path(test_file).exists():
            print(f"📁 [테스트] 테스트 파일 발견: {test_file}")
            try:
                with open(test_file, 'rb') as f:
                    audio_data = f.read()
                
                # PCM으로 변환
                pcm_data = convert_to_pcm(audio_data)
                return pcm_data
                
            except Exception as e:
                print(f"❌ [테스트] 파일 읽기 실패: {e}")
    
    print("⚠️ [테스트] 테스트용 오디오 파일 없음")
    print("💡 test_audio.webm 파일을 프로젝트 루트에 넣어주세요")
    return b""

def convert_to_pcm(audio_data: bytes) -> bytes:
    """🔄 오디오를 PCM으로 변환"""
    
    try:
        from pydub import AudioSegment
        from io import BytesIO
        
        audio_io = BytesIO(audio_data)
        
        # 포맷 자동 감지
        try:
            audio = AudioSegment.from_file(audio_io, format="webm")
        except:
            try:
                audio_io.seek(0)
                audio = AudioSegment.from_file(audio_io, format="mp3")
            except:
                audio_io.seek(0)
                audio = AudioSegment.from_file(audio_io)
        
        # PCM 변환
        audio = audio.set_frame_rate(SAMPLE_RATE)
        audio = audio.set_channels(1)
        audio = audio.set_sample_width(2)
        
        return audio.raw_data
        
    except Exception as e:
        print(f"❌ [변환] PCM 변환 실패: {e}")
        return b""

if __name__ == "__main__":
    # 종합 테스트 실행
    run_comprehensive_test()