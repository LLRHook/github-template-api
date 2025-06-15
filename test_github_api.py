#!/usr/bin/env python3
"""
Test script for GitHub API integration
Run this to validate your GitHub token and API setup
"""

import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_USERNAME = os.getenv('GITHUB_USERNAME')

def test_github_connection():
    """Test basic GitHub API connection"""
    print("🔍 Testing GitHub API Connection...")
    print(f"Username: {GITHUB_USERNAME}")
    print(f"Token: {'✅ Present' if GITHUB_TOKEN else '❌ Missing'}")
    
    if not GITHUB_TOKEN or not GITHUB_USERNAME:
        print("\n❌ Missing credentials!")
        print("Please create a .env file with:")
        print("GITHUB_TOKEN=your_github_token")
        print("GITHUB_USERNAME=your_github_username")
        return False
    
    # Test API connection
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'GitHub-Template-API-Test'
    }
    
    try:
        # Test authentication
        auth_response = requests.get('https://api.github.com/user', headers=headers)
        if auth_response.status_code == 200:
            user_data = auth_response.json()
            print(f"✅ Authentication successful!")
            print(f"   Authenticated as: {user_data.get('login')}")
            print(f"   Account type: {user_data.get('type')}")
        else:
            print(f"❌ Authentication failed: {auth_response.status_code}")
            print(f"   Response: {auth_response.text}")
            return False
        
        # Test repository access
        repo_response = requests.get(
            f'https://api.github.com/users/{GITHUB_USERNAME}/repos',
            headers=headers,
            params={'per_page': 5}
        )
        
        if repo_response.status_code == 200:
            repos = repo_response.json()
            print(f"✅ Repository access successful!")
            print(f"   Found {len(repos)} repositories (showing first 5)")
            
            for repo in repos:
                description = repo.get('description') or 'No description'
                print(f"   📁 {repo['name']} - {description[:50]}")
        else:
            print(f"❌ Repository access failed: {repo_response.status_code}")
            print(f"   Response: {repo_response.text}")
            return False
        
        # Check rate limits
        rate_limit_response = requests.get('https://api.github.com/rate_limit', headers=headers)
        if rate_limit_response.status_code == 200:
            rate_data = rate_limit_response.json()
            core_limit = rate_data['resources']['core']
            print(f"\n📊 Rate Limit Status:")
            print(f"   Remaining: {core_limit['remaining']}/{core_limit['limit']}")
            print(f"   Reset time: {core_limit['reset']}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def test_api_endpoints():
    """Test local API endpoints"""
    print("\n🌐 Testing Local API Endpoints...")
    
    base_url = "http://localhost:5001"
    
    try:
        # Test health check
        health_response = requests.get(f"{base_url}/")
        if health_response.status_code == 200:
            health_data = health_response.json()
            print("✅ Health check passed")
            print(f"   Service: {health_data.get('service')}")
            print(f"   GitHub configured: {health_data.get('github_configured')}")
        else:
            print(f"❌ Health check failed: {health_response.status_code}")
            return False
        
        # Test repositories endpoint
        repos_response = requests.get(f"{base_url}/api/repositories?limit=3")
        if repos_response.status_code == 200:
            repos_data = repos_response.json()
            print("✅ Repositories endpoint working")
            print(f"   Found {repos_data.get('count')} repositories")
        else:
            print(f"❌ Repositories endpoint failed: {repos_response.status_code}")
            return False
        
        # Test featured endpoint
        featured_response = requests.get(f"{base_url}/api/featured?limit=3")
        if featured_response.status_code == 200:
            featured_data = featured_response.json()
            print("✅ Featured endpoint working")
            print(f"   Found {featured_data.get('count')} featured repositories")
        else:
            print(f"❌ Featured endpoint failed: {featured_response.status_code}")
            return False
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to local API")
        print("   Make sure the API is running: python app.py")
        return False
    except Exception as e:
        print(f"❌ Unexpected error testing API: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 GitHub Template API - Connection Test")
    print("=" * 50)
    
    # Test GitHub connection
    github_ok = test_github_connection()
    
    if github_ok:
        print("\n" + "=" * 50)
        print("🎉 GitHub connection successful!")
        print("\nNext steps:")
        print("1. Run the API: python app.py")
        print("2. Test endpoints: python test_github_api.py")
        print("3. Visit: http://localhost:5001")
        
        # Ask if user wants to test local API
        print("\n" + "=" * 50)
        try:
            test_api = input("Test local API endpoints now? (y/n): ").lower().strip()
            if test_api == 'y':
                api_ok = test_api_endpoints()
                
                if api_ok:
                    print("\n🎉 All tests passed! Your API is ready to use.")
                else:
                    print("\n⚠️  API tests failed. Check if the server is running.")
        except KeyboardInterrupt:
            print("\n\n👋 Test interrupted by user")
    else:
        print("\n❌ GitHub connection failed. Please check your credentials.")
        print("\nSetup steps:")
        print("1. Create a .env file")
        print("2. Add your GITHUB_TOKEN and GITHUB_USERNAME")
        print("3. Run this test again") 