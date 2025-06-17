#!/usr/bin/env python3
"""
최종 확실한 TTS 테스트
공식 GitHub 예제 기반
"""

import asyncio
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

async def test_official_examples():
    """공식 GitHub 예제 기반 테스트"""
    
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("❌ ELEVENLABS_API_KEY 환경변수가 설정되지 않음")
        return False
    
    print(f"🔑 API 키: {api_key[:10]}...")
    
    try:
        # 1. 공식 예제 1: 기본 convert
        print("\n🧪 공식 예제 1: 기본 convert 테스트...")
        from elevenlabs.client import ElevenLabs
        
        client = ElevenLabs(api_key=api_key)
        
        audio_generator = client.text_to_speech.convert(
            text="안녕하세요. 보....이....스",
            voice_id="uyVNoMrnUku1dZyVEXwD",  # Adam
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128"
        )
        
        # generator 처리
        audio_chunks = []
        chunk_count = 0
        for chunk in audio_generator:
            if isinstance(chunk, bytes):
                audio_chunks.append(chunk)
                chunk_count += 1
                print(f"📦 청크 {chunk_count}: {len(chunk)} bytes")
        
        if audio_chunks:
            total_audio = b''.join(audio_chunks)
            print(f"✅ convert 성공: {len(total_audio)} bytes ({chunk_count} 청크)")
            
            # 파일 저장
            with open("test_convert.mp3", "wb") as f:
                f.write(total_audio)
            print("📁 파일 저장: test_convert.mp3")
        else:
            print("❌ convert 실패: 데이터 없음")
            return False
            
    except Exception as e:
        print(f"❌ convert 테스트 오류: {e}")
        return False
    
    try:
        # 2. 공식 예제 2: 스트리밍
        print("\n🧪 공식 예제 2: 스트리밍 테스트...")
        
        audio_stream = client.text_to_speech.stream(
            text="스트리밍 테스트입니다.",
            voice_id="uyVNoMrnUku1dZyVEXwD",
            model_id="eleven_multilingual_v2"
        )
        
        # 스트림 처리
        stream_chunks = []
        stream_count = 0
        for chunk in audio_stream:
            if isinstance(chunk, bytes):
                stream_chunks.append(chunk)
                stream_count += 1
                print(f"🌊 스트림 청크 {stream_count}: {len(chunk)} bytes")
        
        if stream_chunks:
            total_stream = b''.join(stream_chunks)
            print(f"✅ stream 성공: {len(total_stream)} bytes ({stream_count} 청크)")
            
            # 파일 저장
            with open("test_stream.mp3", "wb") as f:
                f.write(total_stream)
            print("📁 파일 저장: test_stream.mp3")
        else:
            print("❌ stream 실패: 데이터 없음")
            return False
            
    except Exception as e:
        print(f"❌ stream 테스트 오류: {e}")
        return False
    
    try:
        # 3. 비동기 버전 테스트
        print("\n🧪 공식 예제 3: 비동기 테스트...")
        from elevenlabs.client import AsyncElevenLabs
        
        async_client = AsyncElevenLabs(api_key=api_key)
        
        # 비동기 convert
        async_audio_gen = async_client.text_to_speech.convert(
            text="비동기 테스트입니다.",
            voice_id="uyVNoMrnUku1dZyVEXwD",
            model_id="eleven_multilingual_v2"
        )
        
        # async generator 처리
        async_chunks = []
        async_count = 0
        async for chunk in async_audio_gen:
            if isinstance(chunk, bytes):
                async_chunks.append(chunk)
                async_count += 1
                print(f"⚡ 비동기 청크 {async_count}: {len(chunk)} bytes")
        
        if async_chunks:
            total_async = b''.join(async_chunks)
            print(f"✅ 비동기 성공: {len(total_async)} bytes ({async_count} 청크)")
            
            # 파일 저장
            with open("test_async.mp3", "wb") as f:
                f.write(total_async)
            print("📁 파일 저장: test_async.mp3")
            
            return True
        else:
            print("❌ 비동기 실패: 데이터 없음")
            return False
            
    except Exception as e:
        print(f"❌ 비동기 테스트 오류: {e}")
        return False

async def test_voice_list():
    """사용 가능한 음성 목록 확인"""
    
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        return
    
    try:
        print("\n🎤 사용 가능한 음성 확인...")
        from elevenlabs.client import ElevenLabs
        
        client = ElevenLabs(api_key=api_key)
        
        # 음성 목록 조회
        voices = client.voices.search()
        
        print(f"📋 총 {len(voices.voices)} 개의 음성 발견:")
        
        for i, voice in enumerate(voices.voices[:5]):  # 처음 5개만
            print(f"   {i+1}. {voice.name} (ID: {voice.voice_id})")
            if hasattr(voice, 'labels'):
                labels = getattr(voice, 'labels', {})
                if labels:
                    print(f"      특성: {labels}")
        
        # 설정된 음성 ID 확인
        voice_id = os.getenv("TTS_VOICE_ID", "uyVNoMrnUku1dZyVEXwD")
        for voice in voices.voices:
            if voice.voice_id == voice_id:
                print(f"✅ 설정된 음성 발견: {voice.name}")
                break
        else:
            print(f"⚠️ 설정된 음성 ID ({voice_id})를 찾을 수 없음")
        
    except Exception as e:
        print(f"❌ 음성 목록 조회 오류: {e}")

async def main():
    print("🔊 ElevenLabs 최종 확실한 테스트")
    print("=" * 50)
    
    # 음성 목록 확인
    await test_voice_list()
    
    # 메인 테스트
    success = await test_official_examples()
    
    if success:
        print("\n🎉 모든 테스트 성공!")
        print("💡 이제 TTS 서비스가 확실히 작동할 것입니다.")
        
        # 생성된 파일들 확인
        files = ["test_convert.mp3", "test_stream.mp3", "test_async.mp3"]
        print("\n📁 생성된 파일들:")
        for file in files:
            if os.path.exists(file):
                size = os.path.getsize(file)
                print(f"   ✅ {file}: {size:,} bytes")
            else:
                print(f"   ❌ {file}: 없음")
                
        print("\n🔊 생성된 MP3 파일들을 재생해서 음성이 나오는지 확인해보세요!")
        
    else:
        print("\n❌ 테스트 실패!")
        print("💡 다음을 확인해주세요:")
        print("   1. API 키가 올바른지")
        print("   2. 계정에 크레딧이 있는지")
        print("   3. 네트워크 연결 상태")
        print("   4. ElevenLabs 라이브러리 버전")
        print("      pip install --upgrade elevenlabs")

if __name__ == "__main__":
    asyncio.run(main())