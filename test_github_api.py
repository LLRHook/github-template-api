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

def check_token_permissions():
    """Check if the GitHub token has sufficient permissions for GraphQL"""
    if not GITHUB_TOKEN:
        return False
    
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    try:
        # Check token scopes
        response = requests.get('https://api.github.com/user', headers=headers)
        if response.status_code == 200:
            # Check multiple ways to get token scopes
            scopes = response.headers.get('X-OAuth-Scopes', '')
            scopes_accepted = response.headers.get('X-Accepted-OAuth-Scopes', '')
            
            print(f"🔐 Token scopes: {scopes}")
            if scopes_accepted:
                print(f"🔐 Accepted scopes: {scopes_accepted}")
            
            # If scopes are empty, try a different approach - test actual API access
            if not scopes or scopes.strip() == '':
                print("⚠️  Scopes header empty, testing actual API access...")
                
                # Test if we can access public repositories
                repo_test = requests.get(f'https://api.github.com/users/{GITHUB_USERNAME}/repos', 
                                       headers=headers, params={'per_page': 1})
                can_access_repos = repo_test.status_code == 200
                
                # Test if we can access user profile (for GraphQL)
                user_test = requests.get('https://api.github.com/user', headers=headers)
                can_access_user = user_test.status_code == 200
                
                if can_access_repos and can_access_user:
                    print("✅ Token has sufficient permissions (verified by API access)")
                    return True
                elif can_access_repos:
                    print("⚠️  Token can access repositories but user access uncertain")
                    print("   This should work for public repositories and pinned repos")
                    return True  # Return True for public repo access
                else:
                    print("❌ Token cannot access repositories")
                    return False
            
            # Original scope checking logic (when scopes are available)
            # Check for repository access (accept general or specific scopes)
            has_repo_access = any([
                'repo' in scopes,           # Full repository access (general/all repo token)
                'public_repo' in scopes,    # Public repository access (minimal)
            ])
            
            # Check for user access (accept general or specific scopes)  
            has_user_access = any([
                'user' in scopes,           # Full user access (general token)
                'read:user' in scopes,      # Read user access (minimal)
            ])
            
            if has_repo_access and has_user_access:
                print("✅ Token has sufficient permissions (general/all repo token)")
                return True
            elif has_repo_access and not has_user_access:
                print("⚠️  Token has repository access but missing user scope")
                print("   This may limit GraphQL API functionality")
                print("   Consider adding 'read:user' or 'user' scope")
                # Still return True for general repo tokens - they often work
                return True
            elif not has_repo_access:
                print("❌ Token missing repository access scopes")
                print("   Need: 'repo' (general) or 'public_repo' (minimal)")
                return False
            else:
                print("✅ Token has sufficient permissions")
                return True
        else:
            print(f"❌ Failed to check token permissions: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking token permissions: {e}")
        return False

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
        
        # Basic repository access test
        repo_response = requests.get(
            f'https://api.github.com/users/{GITHUB_USERNAME}/repos',
            headers=headers,
            params={'per_page': 3, 'sort': 'updated'}
        )
        
        if repo_response.status_code == 200:
            repos = repo_response.json()
            print(f"✅ Repository access successful!")
            print(f"   Found {len(repos)} repositories (showing most recent 3)")
            
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

def test_repository_details():
    """Test detailed repository information fetching"""
    print("🔍 Testing Detailed Repository Information...")
    
    if not GITHUB_TOKEN or not GITHUB_USERNAME:
        print("❌ GitHub credentials not configured")
        return False
    
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'GitHub-Template-API-Test'
    }
    
    try:
        # Get just 1 repo with ALL details
        repo_response = requests.get(
            f'https://api.github.com/users/{GITHUB_USERNAME}/repos',
            headers=headers,
            params={'per_page': 1, 'sort': 'updated'}
        )
        
        if repo_response.status_code != 200:
            print(f"❌ Failed to get repositories: {repo_response.status_code}")
            return False
        
        repos = repo_response.json()
        if not repos:
            print("❌ No repositories found")
            return False
            
        repo = repos[0]  # Get the first (most recent) repository
        print(f"\n📁 DETAILED REPOSITORY INFORMATION:")
        print(f"{'='*60}")
        
        # Print key fields in organized way
        key_fields = ['name', 'full_name', 'description', 'url', 'clone_url', 
                     'language', 'stargazers_count', 'forks_count', 'created_at', 
                     'updated_at', 'pushed_at', 'topics', 'homepage', 'archived']
        
        for field in key_fields:
            if field in repo:
                value = repo[field]
                if field == 'description' and not value:
                    value = 'No description'
                print(f"{field:20}: {value}")
        
        # Get additional repository details
        repo_name = repo['name']
        print(f"\n🔍 ADDITIONAL REPOSITORY DETAILS:")
        print(f"{'='*60}")
        
        # Get languages
        try:
            lang_response = requests.get(f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/languages", headers=headers)
            if lang_response.status_code == 200:
                languages = lang_response.json()
                print(f"Languages: {languages}")
            else:
                print(f"Languages: Failed to fetch ({lang_response.status_code})")
        except Exception as e:
            print(f"Languages: Error - {e}")
        
        # Get latest commit
        try:
            commits_response = requests.get(f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/commits", headers=headers, params={'per_page': 1})
            if commits_response.status_code == 200:
                commits = commits_response.json()
                if commits:
                    latest_commit = commits[0]
                    print(f"Latest commit:")
                    print(f"  └─ SHA: {latest_commit['sha'][:8]}")
                    print(f"  └─ Message: {latest_commit['commit']['message'][:100]}")
                    print(f"  └─ Author: {latest_commit['commit']['author']['name']}")
                    print(f"  └─ Date: {latest_commit['commit']['author']['date']}")
        except Exception as e:
            print(f"Latest commit: Error - {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing repository details: {str(e)}")
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

def test_pinned_repositories():
    """Test pinned repositories specifically"""
    print("\n📌 Testing Pinned Repositories...")
    
    # First check token permissions
    if not check_token_permissions():
        print("⚠️  Token permissions issue detected. Continuing with test anyway...")
    
    base_url = "http://localhost:5001"
    
    try:
        response = requests.get(f"{base_url}/api/pinned")
        if response.status_code == 200:
            data = response.json()
            print("✅ Pinned repositories endpoint working")
            print(f"   Found {data.get('count')} pinned repositories")
            
            if data.get('pinned_repositories'):
                print("\n📌 Your Pinned Repositories:")
                print("=" * 60)
                for i, repo in enumerate(data['pinned_repositories'], 1):
                    print(f"{i}. {repo['name']}")
                    print(f"   Description: {repo['description']}")
                    print(f"   Language: {repo['language'] or 'None'}")
                    print(f"   Stars: ⭐{repo['stars']} | Forks: 🍴{repo['forks']}")
                    print(f"   Topics: {', '.join(repo['topics']) if repo['topics'] else 'None'}")
                    print(f"   URL: {repo['url']}")
                    if repo.get('homepage'):
                        print(f"   Homepage: {repo['homepage']}")
                    print()
            else:
                print("\n⚠️  No pinned repositories found.")
                print("   Go to your GitHub profile and pin some repositories!")
            
            return True
        else:
            print(f"❌ Pinned repositories endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to local API")
        print("   Make sure the API is running: python app.py")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def test_readme_content():
    """Test README content fetching"""
    print("\n📄 Testing README Content Fetching...")
    
    if not GITHUB_TOKEN or not GITHUB_USERNAME:
        print("❌ GitHub credentials not configured")
        return False
    
    # Get a repository name first
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    try:
        # Get repositories, prioritizing public ones for testing
        repo_response = requests.get(
            f'https://api.github.com/users/{GITHUB_USERNAME}/repos',
            headers=headers,
            params={'per_page': 10, 'sort': 'updated'}  # Get more repos to find a public one
        )
        
        if repo_response.status_code != 200:
            print(f"❌ Failed to get repositories: {repo_response.status_code}")
            return False
        
        repos = repo_response.json()
        if not repos:
            print("❌ No repositories found")
            return False
        
        # Find a public repository for testing (if available)
        public_repo = None
        private_repo = None
        
        for repo in repos:
            if not repo.get('private', False):
                public_repo = repo
                break
            elif not private_repo:
                private_repo = repo
        
        # Use public repo if available, otherwise use most recent (even if private)
        test_repo = public_repo if public_repo else repos[0]
        repo_name = test_repo['name']
        is_private = test_repo.get('private', False)
        
        print(f"📁 Testing README for repository: {repo_name}")
        print(f"   Repository is: {'🔒 Private' if is_private else '🌐 Public'}")
        
        if public_repo:
            print("✅ Using public repository for testing")
        elif is_private:
            print("⚠️  No public repositories found - testing with private repo")
            print("   Your token may need 'repo' scope for private repository access")
        
        # Test API endpoint
        base_url = "http://localhost:5001"
        readme_response = requests.get(f"{base_url}/api/repositories/{repo_name}/readme")
        
        if readme_response.status_code == 200:
            data = readme_response.json()
            readme = data.get('readme')
            
            if readme:
                print("✅ README endpoint working")
                print(f"   Size: {readme.get('size', 0)} bytes")
                print(f"   Path: {readme.get('path', 'Unknown')}")
                
                content = readme.get('content', '')
                if content:
                    lines = content.split('\n')
                    print(f"\n📝 README Preview (first 10 lines):")
                    print("=" * 60)
                    for i, line in enumerate(lines[:10], 1):
                        print(f"{i:2}: {line}")
                    if len(lines) > 10:
                        print(f"... and {len(lines)-10} more lines")
                    print("=" * 60)
                else:
                    print("⚠️  README content is empty")
            else:
                print("⚠️  No README found for this repository")
            
            return True
        else:
            print(f"❌ README endpoint failed: {readme_response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to local API")
        print("   Make sure the API is running: python app.py")
        return False
    except Exception as e:
        print(f"❌ Error testing README: {str(e)}")
        return False

def test_pinned_with_readmes():
    """Test getting pinned repositories and their READMEs - Perfect for website portfolios"""
    print("\n🎯 PORTFOLIO SCENARIO: Pinned Repositories + READMEs")
    print("=" * 70)
    print("This simulates what your website would do:")
    print("1. Get pinned repositories (your showcase projects)")
    print("2. Fetch README content for each (as project descriptions)")
    print("=" * 70)
    
    base_url = "http://localhost:5001"
    
    try:
        # Step 1: Get pinned repositories
        print("\n[Step 1] 📌 Fetching pinned repositories...")
        pinned_response = requests.get(f"{base_url}/api/pinned")
        
        if pinned_response.status_code != 200:
            print(f"❌ Failed to get pinned repositories: {pinned_response.status_code}")
            print(f"   Response: {pinned_response.text}")
            return False
        
        pinned_data = pinned_response.json()
        pinned_repos = pinned_data.get('pinned_repositories', [])
        
        if not pinned_repos:
            print("⚠️  No pinned repositories found!")
            print("   Go to your GitHub profile and pin some repositories first.")
            return False
        
        print(f"✅ Found {len(pinned_repos)} pinned repositories")
        
        # Step 2: Get READMEs for each pinned repository
        print(f"\n[Step 2] 📄 Fetching READMEs for each pinned repository...")
        
        portfolio_data = []
        
        for i, repo in enumerate(pinned_repos, 1):
            repo_name = repo['name']
            print(f"\n[{i}/{len(pinned_repos)}] Processing: {repo_name}")
            print(f"   Description: {repo['description']}")
            print(f"   Language: {repo['language'] or 'None'}")
            print(f"   Stars: ⭐{repo['stars']} | Forks: 🍴{repo['forks']}")
            
            # Fetch README
            readme_response = requests.get(f"{base_url}/api/repositories/{repo_name}/readme")
            
            repo_data = {
                'name': repo_name,
                'description': repo['description'],
                'url': repo['url'],
                'language': repo['language'],
                'stars': repo['stars'],
                'forks': repo['forks'],
                'topics': repo['topics'],
                'homepage': repo.get('homepage'),
                'readme_content': None,
                'readme_summary': None
            }
            
            if readme_response.status_code == 200:
                readme_data = readme_response.json()
                readme = readme_data.get('readme')
                
                if readme and readme.get('content'):
                    content = readme['content']
                    repo_data['readme_content'] = content
                    
                    # Create summary (first 3 lines)
                    lines = content.split('\n')
                    non_empty_lines = [line.strip() for line in lines if line.strip()]
                    summary_lines = non_empty_lines[:3] if non_empty_lines else ['No content']
                    repo_data['readme_summary'] = '\n'.join(summary_lines)
                    
                    print(f"   ✅ README fetched ({len(content)} characters)")
                    print(f"   📝 Preview: {summary_lines[0][:60]}..." if summary_lines[0] else "")
                else:
                    print(f"   ⚠️  No README content found")
            else:
                print(f"   ❌ README fetch failed: {readme_response.status_code}")
            
            portfolio_data.append(repo_data)
        
        # Step 3: Display final portfolio data
        print(f"\n[Step 3] 🎨 FINAL PORTFOLIO DATA")
        print("=" * 70)
        print("This is what your website would receive:")
        print("=" * 70)
        
        for i, project in enumerate(portfolio_data, 1):
            print(f"\n🚀 PROJECT {i}: {project['name']}")
            print("-" * 50)
            print(f"Description: {project['description'] or 'No description'}")
            print(f"Language: {project['language'] or 'None'}")
            print(f"Stats: ⭐{project['stars']} stars, 🍴{project['forks']} forks")
            print(f"URL: {project['url']}")
            if project.get('homepage'):
                print(f"Homepage: {project['homepage']}")
            print(f"Topics: {', '.join(project['topics']) if project['topics'] else 'None'}")
            
            if project['readme_summary']:
                print(f"\n📄 README Summary:")
                print(f"{project['readme_summary']}")
            else:
                print(f"\n📄 README: Not available")
            
            print(f"\n💻 For Website Display:")
            # Show how this would look on a website
            title = project['name'].replace('-', ' ').title()
            description = project['readme_summary'] or project['description'] or 'No description available'
            print(f'<div class="project-card">')
            print(f'  <h3>{title}</h3>')
            print(f'  <p>{description[:100]}...</p>')
            print(f'  <span class="tech">{project["language"] or "N/A"}</span>')
            print(f'  <span class="stars">⭐ {project["stars"]}</span>')
            print(f'  <a href="{project["url"]}">View Project</a>')
            print(f'</div>')
        
        print(f"\n🎉 SUCCESS! Portfolio data ready for {len(portfolio_data)} projects")
        print("This data is perfect for populating your website's project section!")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to local API")
        print("   Make sure the API is running: python app.py")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def show_menu():
    """Display the test menu"""
    print("\n" + "=" * 60)
    print("🚀 GitHub Template API - Test Menu")
    print("=" * 60)
    print("1. 🔍 Test GitHub Connection")
    print("2. 📊 Test Repository Details (Detailed)")
    print("3. 🌐 Test Local API Endpoints")
    print("4. 📌 Test Pinned Repositories")
    print("5. 📄 Test README Content")
    print("6. 🎯 Portfolio Scenario (Pinned + READMEs)")
    print("7. 🧪 Run All Tests")
    print("8. ❌ Exit")
    print("=" * 60)

def run_all_tests():
    """Run all tests in sequence"""
    print("\n🧪 Running All Tests...")
    print("=" * 60)
    
    results = []
    
    # Test 1: GitHub Connection
    print("\n[1/5] Testing GitHub Connection...")
    github_ok = test_github_connection()
    results.append(("GitHub Connection", github_ok))
    
    if not github_ok:
        print("\n❌ GitHub connection failed. Skipping other tests.")
        return False
    
    # Test 2: Repository Details
    print("\n[2/5] Testing Repository Details...")
    details_ok = test_repository_details()
    results.append(("Repository Details", details_ok))
    
    # Test 3: API Endpoints
    print("\n[3/5] Testing API Endpoints...")
    api_ok = test_api_endpoints()
    results.append(("API Endpoints", api_ok))
    
    # Test 4: Pinned Repositories
    print("\n[4/5] Testing Pinned Repositories...")
    pinned_ok = test_pinned_repositories()
    results.append(("Pinned Repositories", pinned_ok))
    
    # Test 5: README Content
    print("\n[5/5] Testing README Content...")
    readme_ok = test_readme_content()
    results.append(("README Content", readme_ok))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:25}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Your API is ready to use.")
    else:
        print("⚠️  Some tests failed. Check the details above.")
    
    return all_passed

def main():
    """Main menu loop"""
    while True:
        show_menu()
        
        try:
            choice = input("\nSelect an option (1-8): ").strip()
            
            if choice == '1':
                print("\n🔍 Testing GitHub Connection...")
                github_ok = test_github_connection()
                if github_ok:
                    print("✅ GitHub connection successful!")
                else:
                    print("❌ GitHub connection failed. Check your credentials.")
                    
            elif choice == '2':
                print("\n📊 Testing Repository Details...")
                details_ok = test_repository_details()
                if details_ok:
                    print("✅ Repository details test successful!")
                else:
                    print("❌ Repository details test failed.")
                    
            elif choice == '3':
                print("\n🌐 Testing Local API Endpoints...")
                api_ok = test_api_endpoints()
                if api_ok:
                    print("✅ All API endpoints working!")
                else:
                    print("❌ Some API endpoints failed.")
                    
            elif choice == '4':
                test_pinned_repositories()
                
            elif choice == '5':
                test_readme_content()
                
            elif choice == '6':
                portfolio_ok = test_pinned_with_readmes()
                if portfolio_ok:
                    print("✅ Portfolio scenario completed successfully!")
                else:
                    print("❌ Portfolio scenario failed.")
                
            elif choice == '7':
                run_all_tests()
                
            elif choice == '8':
                print("\n👋 Goodbye!")
                break
                
            else:
                print("\n❌ Invalid option. Please choose 1-8.")
                
            # Pause before showing menu again
            input("\nPress Enter to continue...")
            
        except KeyboardInterrupt:
            print("\n\n👋 Test interrupted by user. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error: {str(e)}")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    main() 