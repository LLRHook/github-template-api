from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from urllib3.exceptions import ReadTimeoutError
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging
from threading import Lock

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
GITHUB_REQUEST_TIMEOUT = (3.05, 10)

# Cache for storing repo data (in production, use Redis or similar)
repo_cache = {
    'data': None,
    'last_updated': None,
    'key': None,
    'cache_duration': timedelta(minutes=30)  # Cache for 30 minutes
}
repo_cache_lock = Lock()


class GitHubAPIError(Exception):
    """An upstream failure with a safe, client-facing message."""

    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


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

    def _request_json(self, method, url, expected_type=dict, **kwargs):
        """Bound network waits and preserve failures instead of returning empty data."""
        try:
            response = method(url, timeout=GITHUB_REQUEST_TIMEOUT, **kwargs)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout as exc:
            raise GitHubAPIError('GitHub request timed out', 504) from exc
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                raise GitHubAPIError('GitHub resource not found', 404) from exc
            raise GitHubAPIError('GitHub API request failed') from exc
        except requests.exceptions.ConnectionError as exc:
            # Requests 2.31 wraps response-body read timeouts in ConnectionError.
            # Match the transport exception type, never its potentially misleading text.
            if any(isinstance(reason, ReadTimeoutError) for reason in exc.args):
                raise GitHubAPIError('GitHub request timed out', 504) from exc
            raise GitHubAPIError('GitHub API request failed') from exc
        except (requests.exceptions.RequestException, ValueError) as exc:
            raise GitHubAPIError('GitHub API request failed') from exc

        if not isinstance(data, expected_type):
            raise GitHubAPIError('Invalid response from GitHub')
        return response, data
    
    def fetch_repositories(self, filter_forks=True, filter_languages=None, sort='updated'):
        """
        Fetch repositories from GitHub API
        
        Args:
            filter_forks (bool): Exclude forked repositories
            filter_languages (list): Filter by programming languages
            sort (str): Sort order ('updated', 'created', 'pushed', 'full_name')
        """
        url = f"{GITHUB_API_BASE}/users/{self.username}/repos"
        params = {
            'type': 'owner',
            'sort': sort,
            'direction': 'desc',
            'per_page': 100,
            'page': 1,
        }
        languages = {lang.strip().lower() for lang in filter_languages or [] if lang.strip()}
        filtered_repos = []
        while True:
            response, repos = self._request_json(
                requests.get, url, expected_type=list, headers=self.headers, params=params.copy()
            )
            for repo in repos:
                # Skip forks if requested
                if filter_forks and repo.get('fork', False):
                    continue
                
                # Filter by languages if specified
                if languages:
                    repo_language = (repo.get('language') or '').lower()
                    if repo_language not in languages:
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
            
            if 'next' not in response.links:
                break
            # Keep credentials on the configured GitHub endpoint, even if a Link URL is unexpected.
            params['page'] += 1
        return filtered_repos
    
    def get_repository_languages(self, repo_name):
        """Get programming languages used in a specific repository"""
        url = f"{GITHUB_API_BASE}/repos/{self.username}/{repo_name}/languages"
        _, languages = self._request_json(requests.get, url, headers=self.headers)
        return languages
    
    def get_repository_readme(self, repo_name):
        """Get README content for a specific repository"""
        try:
            url = f"{GITHUB_API_BASE}/repos/{self.username}/{repo_name}/readme"
            _, readme_data = self._request_json(requests.get, url, headers=self.headers)
            
            # Decode README content from base64
            if 'content' in readme_data:
                import base64
                content_base64 = readme_data['content']
                if not isinstance(content_base64, str):
                    raise GitHubAPIError('Invalid README content from GitHub')
                # GitHub wraps base64 content with newlines; reject other invalid bytes.
                readme_content = base64.b64decode(
                    ''.join(content_base64.split()), validate=True
                ).decode('utf-8')
                
                return {
                    'path': readme_data.get('path'),
                    'size': readme_data.get('size'),
                    'content': readme_content,
                    'download_url': readme_data.get('download_url')
                }
            else:
                logger.warning(f"No content found in README for {repo_name}")
                return None
                
        except GitHubAPIError as exc:
            if exc.status_code == 404:
                return None
            raise
        except (ValueError, TypeError) as exc:
            raise GitHubAPIError('Invalid README content from GitHub') from exc
    
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
            _, data = self._request_json(
                requests.post,
                graphql_url,
                json={
                    'query': query,
                    'variables': {'username': self.username}
                },
                headers=graphql_headers
            )
            if data.get('errors'):
                raise GitHubAPIError('GitHub GraphQL request failed')
            
            # Extract pinned repositories from GraphQL response
            pinned_repos = []
            pinned_items = data['data']['user']['pinnedItems']
            
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
            
        except (KeyError, TypeError, AttributeError) as exc:
            raise GitHubAPIError('Invalid response from GitHub') from exc

# Initialize GitHub service
github_service = None
if GITHUB_TOKEN and GITHUB_USERNAME:
    github_service = GitHubService(GITHUB_TOKEN, GITHUB_USERNAME)

def is_cache_valid(cache_key):
    """Check if cached data is still valid"""
    if (repo_cache['data'] is None or repo_cache['last_updated'] is None
            or repo_cache['key'] != cache_key):
        return False
    
    time_since_update = datetime.now() - repo_cache['last_updated']
    return time_since_update < repo_cache['cache_duration']


def parse_boolean_query(name):
    value = request.args.get(name, 'false').strip().lower()
    if value not in ('true', 'false'):
        raise ValueError(f'{name} must be true or false')
    return value == 'true'


def parse_limit(default=None):
    if 'limit' not in request.args:
        return default
    try:
        limit = int(request.args['limit'])
    except ValueError:
        raise ValueError('limit must be a positive integer') from None
    if limit <= 0:
        raise ValueError('limit must be a positive integer')
    return limit

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
        include_forks = parse_boolean_query('include_forks')
        languages = tuple(sorted({
            lang.strip().lower() for lang in request.args.get('languages', '').split(',')
            if lang.strip()
        }))
        sort = request.args.get('sort', 'updated')
        if sort not in ('updated', 'created', 'pushed', 'full_name'):
            raise ValueError('sort must be updated, created, pushed, or full_name')
        limit = parse_limit()
        force_refresh = parse_boolean_query('force_refresh')
        cache_key = (include_forks, languages, sort)
        
        # Check cache first (unless force refresh is requested)
        with repo_cache_lock:
            cache_hit = not force_refresh and is_cache_valid(cache_key)
            if cache_hit:
                repos = repo_cache['data']
                last_updated = repo_cache['last_updated']

        if cache_hit:
            logger.info("Returning cached repository data")
        else:
            # Fetch fresh data from GitHub
            logger.info("Fetching fresh repository data from GitHub")
            repos = github_service.fetch_repositories(
                filter_forks=not include_forks,
                filter_languages=languages,
                sort=sort
            )
            
            # Update cache
            last_updated = datetime.now()
            with repo_cache_lock:
                repo_cache.update(data=repos, last_updated=last_updated, key=cache_key)
        
        # Apply limit if specified
        if limit is not None:
            repos = repos[:limit]
        
        return jsonify({
            'repositories': repos,
            'count': len(repos),
            'cached': cache_hit,
            'last_updated': last_updated.isoformat()
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except GitHubAPIError as e:
        return jsonify({'error': str(e)}), e.status_code
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
    except GitHubAPIError as e:
        return jsonify({'error': str(e)}), e.status_code
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
            
    except GitHubAPIError as e:
        return jsonify({'error': str(e)}), e.status_code
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
        
    except GitHubAPIError as e:
        return jsonify({'error': str(e)}), e.status_code
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
        limit = parse_limit(default=6)
        
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
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except GitHubAPIError as e:
        return jsonify({'error': str(e)}), e.status_code
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
