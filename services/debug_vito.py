import configparser
import os
import requests
import json

def debug_config_file():
    """config.ini 파일 내용을 확인하는 함수"""
    print("=== CONFIG FILE DEBUG ===")
    
    file_dir = os.path.dirname(os.path.abspath(__file__))
    par_dir = os.path.dirname(file_dir)
    config_path = os.path.join(par_dir, "config.ini")
    
    print(f"Config file path: {config_path}")
    print(f"Config file exists: {os.path.exists(config_path)}")
    
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            print("Config file contents:")
            print(f.read())
        
        env_config = configparser.ConfigParser()
        env_config.read(config_path)
        
        print(f"Available sections: {env_config.sections()}")
        if 'DEFAULT' in env_config:
            print(f"Keys in DEFAULT section: {list(env_config['DEFAULT'].keys())}")
            
            # 값들 확인 (보안을 위해 일부만 표시)
            if 'CLIENT_ID' in env_config['DEFAULT']:
                client_id = env_config['DEFAULT']['CLIENT_ID']
                print(f"CLIENT_ID length: {len(client_id)}")
                print(f"CLIENT_ID starts with: {client_id[:10]}...")
            else:
                print("CLIENT_ID not found in config")
                
            if 'CLIENT_SECRET' in env_config['DEFAULT']:
                client_secret = env_config['DEFAULT']['CLIENT_SECRET']
                print(f"CLIENT_SECRET length: {len(client_secret)}")
                print(f"CLIENT_SECRET starts with: {client_secret[:10]}...")
            else:
                print("CLIENT_SECRET not found in config")
        else:
            print("DEFAULT section not found")
    else:
        print("Config file does not exist!")
    
    print()

def test_authentication():
    """VITO API 인증을 테스트하는 함수"""
    print("=== AUTHENTICATION TEST ===")
    
    try:
        file_dir = os.path.dirname(os.path.abspath(__file__))
        par_dir = os.path.dirname(file_dir)
        config_path = os.path.join(par_dir, "config.ini")
        
        env_config = configparser.ConfigParser()
        env_config.read(config_path)
        
        client_id = env_config['DEFAULT']['CLIENT_ID']
        client_secret = env_config['DEFAULT']['CLIENT_SECRET']
        
        print(f"Attempting authentication...")
        print(f"API URL: https://openapi.vito.ai/v1/authenticate")
        
        # 요청 데이터 확인
        data = {
            'client_id': client_id,
            'client_secret': client_secret
        }
        
        print(f"Request data keys: {list(data.keys())}")
        print(f"Client ID length: {len(client_id)}")
        print(f"Client Secret length: {len(client_secret)}")
        
        # 실제 요청
        resp = requests.post(
            'https://openapi.vito.ai/v1/authenticate',
            data=data
        )
        
        print(f"Response status code: {resp.status_code}")
        print(f"Response headers: {dict(resp.headers)}")
        
        if resp.status_code == 200:
            print("✅ Authentication successful!")
            response_json = resp.json()
            print(f"Response keys: {list(response_json.keys())}")
            if 'access_token' in response_json:
                token = response_json['access_token']
                print(f"Access token length: {len(token)}")
                print(f"Access token starts with: {token[:20]}...")
        else:
            print("❌ Authentication failed!")
            print(f"Response text: {resp.text}")
            
            # 상세 에러 분석
            try:
                error_json = resp.json()
                print(f"Error JSON: {json.dumps(error_json, indent=2)}")
            except:
                print("Response is not valid JSON")
                
    except Exception as e:
        print(f"Error during authentication test: {e}")
    
    print()

def check_environment():
    """환경 설정을 확인하는 함수"""
    print("=== ENVIRONMENT CHECK ===")
    
    # 필요한 패키지들 확인
    required_packages = ['requests', 'grpc', 'pyaudio', 'configparser']
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} is available")
        except ImportError:
            print(f"❌ {package} is NOT available")
    
    print()

def main():
    """메인 디버깅 함수"""
    print("VITO API Debugging Script")
    print("=" * 50)
    
    check_environment()
    debug_config_file()
    test_authentication()
    
    print("Debugging complete!")

if __name__ == "__main__":
    main()