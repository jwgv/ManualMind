#!/usr/bin/env python3
"""
Test script for query length limits in ManualMind.
Tests both frontend validation and backend API validation.
"""

import requests
import json

def test_query_length_limits():
    """Test query length validation on the API endpoint."""
    print("🔍 Testing Query Length Limits...")
    
    api_url = "http://localhost:8000/query"
    
    # Test cases
    test_cases = [
        {
            "name": "Valid short query",
            "query": "How do I use the vocoder?",
            "should_pass": True
        },
        {
            "name": "Valid medium query",
            "query": "How do I configure the filter settings on my Roland Juno X synthesizer to get a warm pad sound?",
            "should_pass": True
        },
        {
            "name": "Query at limit (500 characters)",
            "query": "A" * 500,
            "should_pass": True
        },
        {
            "name": "Query over limit (501 characters)",
            "query": "A" * 501,
            "should_pass": False
        },
        {
            "name": "Very long query (1000 characters)",
            "query": "A" * 1000,
            "should_pass": False
        },
        {
            "name": "Empty query",
            "query": "",
            "should_pass": False
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        print(f"\n📝 Testing: {test_case['name']}")
        print(f"   Query length: {len(test_case['query'])} characters")
        
        try:
            response = requests.post(api_url, json={
                "question": test_case["query"],
                "max_results": 3
            }, timeout=10)
            
            if test_case["should_pass"]:
                if response.status_code == 200:
                    print("   ✅ PASS: Valid query accepted")
                    results.append(True)
                else:
                    print(f"   ❌ FAIL: Valid query rejected (status: {response.status_code})")
                    if response.status_code == 422:
                        error_detail = response.json()
                        print(f"   Error: {error_detail}")
                    results.append(False)
            else:
                if response.status_code in [400, 422]:
                    print(f"   ✅ PASS: Invalid query properly rejected (status: {response.status_code})")
                    results.append(True)
                else:
                    print(f"   ❌ FAIL: Invalid query should be rejected but got status: {response.status_code}")
                    results.append(False)
                    
        except requests.exceptions.RequestException as e:
            print(f"   ❌ ERROR: Request failed: {e}")
            results.append(False)
    
    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All query length validation tests passed!")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False

def test_frontend_limits():
    """Test frontend validation by checking the HTML."""
    print("\n🔍 Testing Frontend Query Limits...")
    
    try:
        response = requests.get("http://localhost:8000/static/index.html")
        if response.status_code == 200:
            html_content = response.text
            
            # Check for maxlength attribute
            if 'maxlength="500"' in html_content:
                print("✅ Frontend has maxlength attribute set to 500")
                
                # Check for character count display
                if 'char-count' in html_content and '/ 500 characters' in html_content:
                    print("✅ Frontend has character count display")
                    return True
                else:
                    print("❌ Frontend missing character count display")
                    return False
            else:
                print("❌ Frontend missing maxlength attribute")
                return False
        else:
            print(f"❌ Could not fetch frontend HTML (status: {response.status_code})")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Frontend test failed: {e}")
        return False

def main():
    """Run all query limit tests."""
    print("🤖 ManualMind Query Length Validation Test Suite")
    print("=" * 55)
    
    # Test frontend
    frontend_ok = test_frontend_limits()
    
    # Test backend API
    backend_ok = test_query_length_limits()
    
    print("\n" + "=" * 55)
    print("📋 Final Results:")
    print(f"   Frontend validation: {'✅ PASS' if frontend_ok else '❌ FAIL'}")
    print(f"   Backend validation:  {'✅ PASS' if backend_ok else '❌ FAIL'}")
    
    if frontend_ok and backend_ok:
        print("\n🎉 All query length validation tests passed!")
        return True
    else:
        print("\n⚠️  Some validation tests failed.")
        return False

if __name__ == "__main__":
    main()