#!/usr/bin/env python3
"""Test OpenRouter API key validity."""

import httpx
import os
import sys
from pathlib import Path

# Add server to path
sys.path.insert(0, str(Path(__file__).parent / 'server'))

from config import get_settings

def test_api_key():
    """Test if the OpenRouter API key is valid."""
    settings = get_settings()
    api_key = settings.openrouter_api_key
    
    if not api_key:
        print("❌ No API key found in configuration")
        return False
    
    print(f"Testing API key: {api_key[:20]}...")
    
    try:
        response = httpx.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'deepseek/deepseek-chat-v3.1:free',
                'messages': [{'role': 'user', 'content': 'Hello'}],
                'max_tokens': 10
            },
            timeout=10.0
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ API key is valid and working!")
            data = response.json()
            print(f"Response: {data.get('choices', [{}])[0].get('message', {}).get('content', 'No content')}")
            return True
        else:
            print("❌ API call failed")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_api_key()
    sys.exit(0 if success else 1)
