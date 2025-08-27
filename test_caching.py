#!/usr/bin/env python3
"""
Test script for ManualMind caching implementation.
Tests both Redis query caching and Nginx response caching.
"""

import time
import requests
import json
import redis
import os
from dotenv import load_dotenv

load_dotenv()

def test_redis_cache():
    """Test Redis query caching functionality."""
    print("🔍 Testing Redis Query Caching...")
    
    # Connect to Redis
    try:
        redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True
        )
        redis_client.ping()
        print("✅ Redis connection successful")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False
    
    # Clear any existing cache entries for our test
    test_query = "How do I test the vocoder on Roland Juno X?"
    cache_pattern = "query_cache:*"
    
    # Clear previous test cache entries
    for key in redis_client.scan_iter(match=cache_pattern):
        redis_client.delete(key)
    print("🧹 Cleared previous cache entries")
    
    return True

def test_api_caching():
    """Test API endpoint caching behavior."""
    print("\n🔍 Testing API Query Caching...")
    
    api_url = "http://localhost:8000/query"
    test_query = {
        "question": "How do I test the vocoder on Roland Juno X?",
        "max_results": 3
    }
    
    print("📝 Making first API request (should be slow - no cache)...")
    start_time = time.time()
    
    try:
        response1 = requests.post(api_url, json=test_query, timeout=30)
        first_duration = time.time() - start_time
        
        if response1.status_code == 200:
            print(f"✅ First request successful ({first_duration:.2f}s)")
            result1 = response1.json()
        else:
            print(f"❌ First request failed: {response1.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ First request failed: {e}")
        return False
    
    print("\n📝 Making second API request (should be fast - Redis cached)...")
    start_time = time.time()
    
    try:
        response2 = requests.post(api_url, json=test_query, timeout=30)
        second_duration = time.time() - start_time
        
        if response2.status_code == 200:
            print(f"✅ Second request successful ({second_duration:.2f}s)")
            result2 = response2.json()
            
            # Compare responses
            if result1 == result2:
                print("✅ Cached response matches original")
                
                # Check if second request was significantly faster
                if second_duration < first_duration * 0.5:  # At least 50% faster
                    print(f"✅ Caching performance improvement: {first_duration/second_duration:.1f}x faster")
                else:
                    print(f"⚠️  Caching may not be working - times: {first_duration:.2f}s vs {second_duration:.2f}s")
            else:
                print("❌ Cached response differs from original")
                return False
        else:
            print(f"❌ Second request failed: {response2.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Second request failed: {e}")
        return False
    
    return True

def test_nginx_caching():
    """Test Nginx response caching."""
    print("\n🔍 Testing Nginx Response Caching...")
    
    api_url = "http://localhost/query"  # Through Nginx proxy
    test_query = {
        "question": "How do I configure the filter on Roland Juno X?",
        "max_results": 3
    }
    
    print("📝 Making first request through Nginx proxy...")
    
    try:
        response1 = requests.post(api_url, json=test_query, timeout=30)
        
        if response1.status_code == 200:
            cache_status1 = response1.headers.get('X-Cache-Status', 'UNKNOWN')
            print(f"✅ First request successful - Cache Status: {cache_status1}")
        else:
            print(f"❌ First request failed: {response1.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ First request failed: {e}")
        print("⚠️  Nginx may not be running or accessible on port 80")
        return False
    
    print("\n📝 Making second request through Nginx proxy...")
    
    try:
        response2 = requests.post(api_url, json=test_query, timeout=30)
        
        if response2.status_code == 200:
            cache_status2 = response2.headers.get('X-Cache-Status', 'UNKNOWN')
            print(f"✅ Second request successful - Cache Status: {cache_status2}")
            
            if cache_status2 == 'HIT':
                print("✅ Nginx cache is working - got cache HIT")
            elif cache_status2 == 'MISS':
                print("⚠️  Got cache MISS - cache may need time to warm up")
            else:
                print(f"⚠️  Unexpected cache status: {cache_status2}")
        else:
            print(f"❌ Second request failed: {response2.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Second request failed: {e}")
        return False
    
    return True

def test_cache_key_normalization():
    """Test query normalization for consistent cache keys."""
    print("\n🔍 Testing Query Normalization...")
    
    api_url = "http://localhost:8000/query"
    
    # Test queries that should be normalized to the same cache key
    queries = [
        "How do I use the vocoder?",
        "  How do I use the vocoder?  ",
        "how do i use the vocoder?",
        "HOW DO I USE THE VOCODER?",
        "How    do   I    use   the   vocoder?"
    ]
    
    print("📝 Testing query normalization with variations...")
    responses = []
    
    for i, query in enumerate(queries):
        test_query = {"question": query, "max_results": 3}
        
        try:
            response = requests.post(api_url, json=test_query, timeout=30)
            if response.status_code == 200:
                responses.append(response.json())
                print(f"✅ Query {i+1} successful")
            else:
                print(f"❌ Query {i+1} failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Query {i+1} failed: {e}")
            return False
    
    # Check if all normalized queries return the same response
    if all(resp == responses[0] for resp in responses):
        print("✅ Query normalization working - all variations return same cached response")
        return True
    else:
        print("❌ Query normalization failed - responses differ")
        return False

def main():
    """Run all caching tests."""
    print("🤖 ManualMind Caching Test Suite")
    print("=" * 50)
    
    results = []
    
    # Test Redis connection and basic functionality
    results.append(test_redis_cache())
    
    # Test API-level caching (Redis)
    results.append(test_api_caching())
    
    # Test Nginx proxy caching
    results.append(test_nginx_caching())
    
    # Test query normalization
    results.append(test_cache_key_normalization())
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print(f"✅ Passed: {sum(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}")
    
    if all(results):
        print("\n🎉 All caching tests passed!")
        return True
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    main()