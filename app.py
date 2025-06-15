from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend integration

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GitHub API configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_USERNAME = os.getenv('GITHUB_USERNAME')
GITHUB_API_BASE = 'https://api.github.com'

# Cache for storing repo data (in production, use Redis or similar)
repo_cache = {
    'data': None,
    'last_updated': None,
    'cache_duration': timedelta(minutes=30)  # Cache for 30 minutes
}

class GitHubService:
    """Service class for GitHub API interactions"""
    
    def __init__(self, token, username):
        self.token = token
        self.username = username
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Template-API'
        }
    
    def fetch_repositories(self, filter_forks=True, filter_languages=None, sort='updated'):
        """
        Fetch repositories from GitHub API
        
        Args:
            filter_forks (bool): Exclude forked repositories
            filter_languages (list): Filter by programming languages
            sort (str): Sort order ('updated', 'created', 'pushed', 'full_name')
        """
        try:
            url = f"{GITHUB_API_BASE}/users/{self.username}/repos"
            params = {
                'type': 'owner',
                'sort': sort,
                'direction': 'desc',
                'per_page': 100
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            repos = response.json()
            
            # Filter repositories
            filtered_repos = []
            for repo in repos:
                # Skip forks if requested
                if filter_forks and repo.get('fork', False):
                    continue
                
                # Filter by languages if specified
                if filter_languages:
                    repo_language = repo.get('language', '').lower()
                    if repo_language not in [lang.lower() for lang in filter_languages]:
                        continue
                
                # Extract relevant information
                repo_data = {
                    'id': repo['id'],
                    'name': repo['name'],
                    'full_name': repo['full_name'],
                    'description': repo.get('description', ''),
                    'url': repo['html_url'],
                    'clone_url': repo['clone_url'],
                    'language': repo.get('language'),
                    'stars': repo['stargazers_count'],
                    'forks': repo['forks_count'],
                    'created_at': repo['created_at'],
                    'updated_at': repo['updated_at'],
                    'pushed_at': repo['pushed_at'],
                    'topics': repo.get('topics', []),
                    'is_private': repo['private'],
                    'homepage': repo.get('homepage'),
                    'archived': repo.get('archived', False)
                }
                
                filtered_repos.append(repo_data)
            
            return filtered_repos
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching repositories: {str(e)}")
            raise Exception(f"Failed to fetch repositories: {str(e)}")
    
    def get_repository_languages(self, repo_name):
        """Get programming languages used in a specific repository"""
        try:
            url = f"{GITHUB_API_BASE}/repos/{self.username}/{repo_name}/languages"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching languages for {repo_name}: {str(e)}")
            return {}
    
    def get_repository_readme(self, repo_name):
        """Get README content for a specific repository"""
        try:
            url = f"{GITHUB_API_BASE}/repos/{self.username}/{repo_name}/readme"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            readme_data = response.json()
            
            # Decode README content from base64
            if 'content' in readme_data:
                import base64
                content_base64 = readme_data['content']
                readme_content = base64.b64decode(content_base64).decode('utf-8')
                
                # Log the README content
                logger.info(f"README content for {repo_name}:")
                logger.info("="*60)
                logger.info(readme_content)
                logger.info("="*60)
                
                return {
                    'path': readme_data.get('path'),
                    'size': readme_data.get('size'),
                    'content': readme_content,
                    'download_url': readme_data.get('download_url')
                }
            else:
                logger.warning(f"No content found in README for {repo_name}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching README for {repo_name}: {str(e)}")
            return None
    
    def get_pinned_repositories(self):
        """Get pinned repositories using GitHub GraphQL API"""
        try:
            # GraphQL endpoint
            graphql_url = "https://api.github.com/graphql"
            
            # GraphQL query for pinned repositories
            query = """
            query($username: String!) {
                user(login: $username) {
                    pinnedItems(first: 6, types: [REPOSITORY]) {
                        totalCount
                        edges {
                            node {
                                ... on Repository {
                                    id
                                    name
                                    nameWithOwner
                                    description
                                    url
                                    homepageUrl
                                    stargazerCount
                                    forkCount
                                    isPrivate
                                    isFork
                                    isArchived
                                    createdAt
                                    updatedAt
                                    pushedAt
                                    primaryLanguage {
                                        name
                                        color
                                    }
                                    languages(first: 5, orderBy: {field: SIZE, direction: DESC}) {
                                        edges {
                                            node {
                                                name
                                            }
                                            size
                                        }
                                    }
                                    repositoryTopics(first: 10) {
                                        edges {
                                            node {
                                                topic {
                                                    name
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            """
            
            # GraphQL headers (need different auth format)
            graphql_headers = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Make GraphQL request
            response = requests.post(
                graphql_url,
                json={
                    'query': query,
                    'variables': {'username': self.username}
                },
                headers=graphql_headers
            )
            response.raise_for_status()
            
            data = response.json()
            
            if 'errors' in data:
                logger.error(f"GraphQL errors: {data['errors']}")
                # Check for common permission errors
                for error in data['errors']:
                    if 'insufficient' in error.get('message', '').lower() or 'forbidden' in error.get('message', '').lower():
                        logger.error("Token permissions issue: Your GitHub token may need additional scopes.")
                        logger.error("Required scopes: public_repo, read:user")
                        logger.error("Visit: https://github.com/settings/tokens to update your token")
                return []
            
            # Extract pinned repositories from GraphQL response
            pinned_repos = []
            pinned_items = data.get('data', {}).get('user', {}).get('pinnedItems', {})
            
            logger.info(f"Found {pinned_items.get('totalCount', 0)} pinned repositories")
            
            for edge in pinned_items.get('edges', []):
                repo = edge['node']
                
                # Extract topics
                topics = []
                for topic_edge in repo.get('repositoryTopics', {}).get('edges', []):
                    topics.append(topic_edge['node']['topic']['name'])
                
                # Extract languages
                languages = {}
                for lang_edge in repo.get('languages', {}).get('edges', []):
                    languages[lang_edge['node']['name']] = lang_edge['size']
                
                # Format repository data
                repo_data = {
                    'id': repo['id'],
                    'name': repo['name'],
                    'full_name': repo['nameWithOwner'],
                    'description': repo.get('description', ''),
                    'url': repo['url'],
                    'homepage': repo.get('homepageUrl'),
                    'language': repo.get('primaryLanguage', {}).get('name') if repo.get('primaryLanguage') else None,
                    'language_color': repo.get('primaryLanguage', {}).get('color') if repo.get('primaryLanguage') else None,
                    'stars': repo['stargazerCount'],
                    'forks': repo['forkCount'],
                    'created_at': repo['createdAt'],
                    'updated_at': repo['updatedAt'],
                    'pushed_at': repo['pushedAt'],
                    'topics': topics,
                    'languages': languages,
                    'is_private': repo['isPrivate'],
                    'is_fork': repo['isFork'],
                    'archived': repo['isArchived'],
                    'is_pinned': True  # Mark as pinned
                }
                
                pinned_repos.append(repo_data)
            
            return pinned_repos
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching pinned repositories: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching pinned repositories: {str(e)}")
            return []

# Initialize GitHub service
github_service = None
if GITHUB_TOKEN and GITHUB_USERNAME:
    github_service = GitHubService(GITHUB_TOKEN, GITHUB_USERNAME)

def is_cache_valid():
    """Check if cached data is still valid"""
    if not repo_cache['data'] or not repo_cache['last_updated']:
        return False
    
    time_since_update = datetime.now() - repo_cache['last_updated']
    return time_since_update < repo_cache['cache_duration']

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'GitHub Template API',
        'version': '1.0.0',
        'github_configured': github_service is not None
    })

@app.route('/api/repositories', methods=['GET'])
def get_repositories():
    """
    Get GitHub repositories with optional filtering
    
    Query parameters:
    - include_forks: Include forked repositories (default: false)
    - languages: Comma-separated list of languages to filter by
    - sort: Sort order (updated, created, pushed, full_name)
    - limit: Maximum number of repositories to return
    - force_refresh: Force refresh of cached data
    """
    
    if not github_service:
        return jsonify({
            'error': 'GitHub service not configured. Please set GITHUB_TOKEN and GITHUB_USERNAME environment variables.'
        }), 500
    
    try:
        # Get query parameters
        include_forks = request.args.get('include_forks', 'false').lower() == 'true'
        languages = request.args.get('languages', '').split(',') if request.args.get('languages') else None
        sort = request.args.get('sort', 'updated')
        limit = request.args.get('limit', type=int)
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        # Check cache first (unless force refresh is requested)
        if not force_refresh and is_cache_valid():
            logger.info("Returning cached repository data")
            repos = repo_cache['data']
        else:
            # Fetch fresh data from GitHub
            logger.info("Fetching fresh repository data from GitHub")
            repos = github_service.fetch_repositories(
                filter_forks=not include_forks,
                filter_languages=languages,
                sort=sort
            )
            
            # Update cache
            repo_cache['data'] = repos
            repo_cache['last_updated'] = datetime.now()
        
        # Apply limit if specified
        if limit and limit > 0:
            repos = repos[:limit]
        
        return jsonify({
            'repositories': repos,
            'count': len(repos),
            'cached': not force_refresh and is_cache_valid(),
            'last_updated': repo_cache['last_updated'].isoformat() if repo_cache['last_updated'] else None
        })
        
    except Exception as e:
        logger.error(f"Error in get_repositories: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/repositories/<repo_name>/languages', methods=['GET'])
def get_repository_languages(repo_name):
    """Get programming languages used in a specific repository"""
    
    if not github_service:
        return jsonify({
            'error': 'GitHub service not configured'
        }), 500
    
    try:
        languages = github_service.get_repository_languages(repo_name)
        return jsonify({
            'repository': repo_name,
            'languages': languages
        })
    except Exception as e:
        logger.error(f"Error getting languages for {repo_name}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/repositories/<repo_name>/readme', methods=['GET'])
def get_repository_readme(repo_name):
    """Get README content for a specific repository"""
    
    if not github_service:
        return jsonify({
            'error': 'GitHub service not configured'
        }), 500
    
    try:
        readme_data = github_service.get_repository_readme(repo_name)
        
        if readme_data:
            # README content is already logged in the service method
            return jsonify({
                'repository': repo_name,
                'readme': readme_data
            })
        else:
            return jsonify({
                'repository': repo_name,
                'readme': None,
                'message': 'README not found or not accessible'
            }), 404
            
    except Exception as e:
        logger.error(f"Error getting README for {repo_name}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/pinned', methods=['GET'])
def get_pinned_repositories():
    """
    Get pinned repositories - the ones you've specifically chosen to showcase
    This endpoint is perfect for website portfolio sections
    """
    
    if not github_service:
        return jsonify({
            'error': 'GitHub service not configured'
        }), 500
    
    try:
        # Get pinned repositories using GraphQL
        pinned_repos = github_service.get_pinned_repositories()
        
        # Format for website display
        formatted_repos = []
        for repo in pinned_repos:
            formatted_repos.append({
                'name': repo['name'],
                'description': repo['description'] or 'No description available',
                'url': repo['url'],
                'homepage': repo['homepage'],
                'language': repo['language'],
                'language_color': repo['language_color'],
                'stars': repo['stars'],
                'forks': repo['forks'],
                'topics': repo['topics'],
                'languages': repo['languages'],
                'last_updated': repo['updated_at'],
                'is_pinned': True
            })
        
        return jsonify({
            'pinned_repositories': formatted_repos,
            'count': len(formatted_repos)
        })
        
    except Exception as e:
        logger.error(f"Error in get_pinned_repositories: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/featured', methods=['GET'])
def get_featured_repositories():
    """
    Get featured repositories (top repositories by stars/activity)
    This endpoint is optimized for website templating
    """
    
    if not github_service:
        return jsonify({
            'error': 'GitHub service not configured'
        }), 500
    
    try:
        # Get query parameters
        limit = request.args.get('limit', 6, type=int)  # Default to 6 for website display
        
        # Get all repositories
        repos = github_service.fetch_repositories(filter_forks=True, sort='updated')
        
        # Sort by stars and recent activity for featured display
        featured_repos = sorted(
            repos, 
            key=lambda r: (r['stars'], r['updated_at']), 
            reverse=True
        )[:limit]
        
        # Format for website display
        formatted_repos = []
        for repo in featured_repos:
            formatted_repos.append({
                'name': repo['name'],
                'description': repo['description'] or 'No description available',
                'url': repo['url'],
                'language': repo['language'],
                'stars': repo['stars'],
                'topics': repo['topics'][:5],  # Limit topics for display
                'last_updated': repo['updated_at']
            })
        
        return jsonify({
            'featured_repositories': formatted_repos,
            'count': len(formatted_repos)
        })
        
    except Exception as e:
        logger.error(f"Error in get_featured_repositories: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Check if required environment variables are set
    if not GITHUB_TOKEN or not GITHUB_USERNAME:
        logger.warning("GITHUB_TOKEN and GITHUB_USERNAME must be set in environment variables")
        print("⚠️  Please create a .env file with your GitHub credentials:")
        print("   GITHUB_TOKEN=your_github_token")
        print("   GITHUB_USERNAME=your_github_username")
    
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5001)),
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    ) 