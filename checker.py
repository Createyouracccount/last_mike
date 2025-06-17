#!/usr/bin/env python3
"""
긴급 TTS 디버깅 - 정확히 뭐가 문제인지 찾아보자
"""

import os
import requests
from dotenv import load_dotenv

def check_everything():
    """모든 걸 하나씩 체크해보자"""
    print("🚨 긴급 TTS 디버깅")
    print("=" * 50)
    
    # 1. .env 파일 직접 확인
    print("1️⃣ .env 파일 직접 읽기:")
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            content = f.read()
        
        for line in content.split('\n'):
            if 'ELEVENLABS' in line.upper():
                parts = line.split('=', 1)
                if len(parts) == 2:
                    key = parts[1].strip()
                    print(f"   파일에서 읽은 키: {key[:12]}...{key[-4:] if len(key) > 16 else key}")
                    print(f"   키 길이: {len(key)}")
                else:
                    print(f"   ❌ 잘못된 형식: {line}")
    except Exception as e:
        print(f"   ❌ 파일 읽기 실패: {e}")
    
    # 2. dotenv로 로드한 값 확인
    print("\n2️⃣ dotenv로 로드된 값:")
    load_dotenv(override=True)  # 강제로 다시 로드
    api_key = os.getenv('ELEVENLABS_API_KEY')
    
    if api_key:
        print(f"   로드된 키: {api_key[:12]}...{api_key[-4:] if len(api_key) > 16 else api_key}")
        print(f"   로드된 키 길이: {len(api_key)}")
    else:
        print("   ❌ 로드된 키 없음")
    
    # 3. 실제 API 테스트 (기본 엔드포인트)
    print("\n3️⃣ 기본 API 테스트:")
    if api_key:
        headers = {
            'Accept': 'application/json',
            'xi-api-key': api_key.strip()
        }
        
        try:
            response = requests.get('https://api.elevenlabs.io/v1/user', headers=headers, timeout=5)
            print(f"   상태코드: {response.status_code}")
            if response.status_code == 200:
                user_data = response.json()
                print(f"   ✅ 기본 API 성공: {user_data.get('first_name', 'N/A')}")
            else:
                print(f"   ❌ 기본 API 실패: {response.text}")
        except Exception as e:
            print(f"   ❌ 기본 API 오류: {e}")
    
    # 4. 음성 목록 확인 (Voice ID 검증)
    print("\n4️⃣ 음성 목록 확인:")
    if api_key:
        try:
            response = requests.get('https://api.elevenlabs.io/v1/voices', headers=headers, timeout=5)
            if response.status_code == 200:
                voices = response.json()
                voice_list = voices.get('voices', [])
                print(f"   ✅ 사용 가능한 음성: {len(voice_list)}개")
                
                # 처음 3개 음성 ID 출력
                for i, voice in enumerate(voice_list[:3]):
                    print(f"   음성 {i+1}: {voice.get('voice_id')} ({voice.get('name')})")
                
                # 현재 사용 중인 Voice ID 확인
                current_voice_id = "uyVNoMrnUku1dZyVEXwD"
                voice_exists = any(v.get('voice_id') == current_voice_id for v in voice_list)
                print(f"   현재 Voice ID 유효성: {'✅' if voice_exists else '❌'}")
                
            else:
                print(f"   ❌ 음성 목록 실패: {response.text}")
        except Exception as e:
            print(f"   ❌ 음성 목록 오류: {e}")
    
    # 5. 실제 TTS 테스트 (앱과 동일한 방식)
    print("\n5️⃣ 실제 TTS 테스트:")
    if api_key:
        # 사용 가능한 첫 번째 음성으로 테스트
        test_voice_id = "21m00Tcm4TlvDq8ikWAM"  # 기본 Rachel 음성
        
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{test_voice_id}/stream"
        params = {"output_format": "mp3_44100_128"}
        
        headers = {
            'Accept': 'audio/mpeg',
            'Content-Type': 'application/json',
            'xi-api-key': api_key.strip()
        }
        
        data = {
            "text": "테스트입니다",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
        
        try:
            response = requests.post(url, headers=headers, params=params, json=data, timeout=10)
            print(f"   TTS Stream 상태코드: {response.status_code}")
            
            if response.status_code == 200:
                print(f"   ✅ TTS 성공! 데이터 크기: {len(response.content)} bytes")
            else:
                print(f"   ❌ TTS 실패: {response.text}")
                
                # 다른 음성으로 재시도
                print("   다른 음성으로 재시도...")
                url2 = f"https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB/stream"
                response2 = requests.post(url2, headers=headers, params=params, json=data, timeout=10)
                print(f"   재시도 상태코드: {response2.status_code}")
                
        except Exception as e:
            print(f"   ❌ TTS 테스트 오류: {e}")

def suggest_immediate_fixes():
    """즉시 시도할 수 있는 해결책"""
    print("\n💡 즉시 시도할 해결책:")
    print("-" * 30)
    print("1. 🔄 애플리케이션 완전 재시작")
    print("   - Ctrl+C로 종료")
    print("   - python main.py 다시 실행")
    print()
    print("2. 🔑 ElevenLabs 계정 확인")
    print("   - https://elevenlabs.io/app 접속")
    print("   - 계정 상태 확인")
    print("   - 결제 정보 확인")
    print()
    print("3. 🆕 완전히 새로운 API 키 생성")
    print("   - 기존 키 모두 삭제")
    print("   - 새 키 생성")
    print("   - .env 파일 완전 재작성")
    print()
    print("4. 🎯 임시 해결책: TTS 비활성화")
    print("   - 음성 출력 없이 텍스트만으로 테스트")

if __name__ == "__main__":
    check_everything()
    suggest_immediate_fixes()