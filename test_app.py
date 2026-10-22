"""Offline regression tests for the API and its GitHub integration."""

import base64
import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import requests

import app as api


def github_response(payload, status=200, headers=None):
    response = requests.Response()
    response.status_code = status
    response.url = 'https://api.github.com/test'
    response.headers.update(headers or {})
    response._content = json.dumps(payload).encode('utf-8')
    response.encoding = 'utf-8'
    return response


def repository(name='example', language='Python', fork=False, stars=1):
    return {
        'id': 1,
        'name': name,
        'full_name': f'octocat/{name}',
        'description': None,
        'html_url': f'https://github.com/octocat/{name}',
        'clone_url': f'https://github.com/octocat/{name}.git',
        'language': language,
        'fork': fork,
        'stargazers_count': stars,
        'forks_count': 0,
        'created_at': '2026-01-01T00:00:00Z',
        'updated_at': '2026-10-01T00:00:00Z',
        'pushed_at': '2026-10-01T00:00:00Z',
        'private': False,
    }


class APITestCase(unittest.TestCase):
    def setUp(self):
        self.service = api.GitHubService('test-token', 'octocat')
        service_patch = patch.object(api, 'github_service', self.service)
        service_patch.start()
        self.addCleanup(service_patch.stop)
        cache_patch = patch.dict(api.repo_cache, {
            'data': None,
            'last_updated': None,
            'cache_duration': timedelta(minutes=30),
            'key': None,
        }, clear=True)
        cache_patch.start()
        self.addCleanup(cache_patch.stop)
        self.client = api.app.test_client()
        self.get_patch = patch('app.requests.get')
        self.get = self.get_patch.start()
        self.addCleanup(self.get_patch.stop)
        self.post_patch = patch('app.requests.post')
        self.post = self.post_patch.start()
        self.addCleanup(self.post_patch.stop)


class RepositoryCacheTests(APITestCase):
    def test_cache_does_not_mix_language_filters(self):
        repos = [repository('python'), repository('javascript', 'JavaScript')]
        self.get.return_value = github_response(repos)
        first = self.client.get('/api/repositories?languages=Python').get_json()
        second = self.client.get('/api/repositories?languages=JavaScript').get_json()
        self.assertEqual([repo['name'] for repo in first['repositories']], ['python'])
        self.assertEqual([repo['name'] for repo in second['repositories']], ['javascript'])

    def test_cache_does_not_mix_fork_filters(self):
        self.get.return_value = github_response([
            repository('owned'), repository('forked', fork=True),
        ])
        self.client.get('/api/repositories?include_forks=true')
        response = self.client.get('/api/repositories').get_json()
        self.assertEqual([repo['name'] for repo in response['repositories']], ['owned'])

    def test_cache_does_not_mix_sort_orders(self):
        self.get.side_effect = [
            github_response([repository('updated')]),
            github_response([repository('created')]),
        ]
        self.client.get('/api/repositories?sort=updated')
        response = self.client.get('/api/repositories?sort=created').get_json()
        self.assertEqual(response['repositories'][0]['name'], 'created')
        self.assertEqual(self.get.call_args.kwargs['params']['sort'], 'created')

    def test_first_response_is_not_reported_as_cached(self):
        self.get.return_value = github_response([repository()])
        first = self.client.get('/api/repositories').get_json()
        second = self.client.get('/api/repositories').get_json()
        self.assertFalse(first['cached'])
        self.assertTrue(second['cached'])
        self.assertEqual(first['last_updated'], second['last_updated'])
        self.get.assert_called_once()

    def test_empty_results_are_cached(self):
        self.get.return_value = github_response([])
        self.client.get('/api/repositories')
        response = self.client.get('/api/repositories').get_json()
        self.assertTrue(response['cached'])
        self.assertEqual(response['repositories'], [])
        self.get.assert_called_once()

    def test_language_whitespace_case_and_duplicates_share_cache(self):
        self.get.return_value = github_response([repository()])
        self.client.get('/api/repositories?languages=%20Python%20,python,,')
        response = self.client.get('/api/repositories?languages=PYTHON').get_json()
        self.assertEqual(response['count'], 1)
        self.assertTrue(response['cached'])
        self.get.assert_called_once()

    def test_limit_is_applied_without_truncating_cached_data(self):
        self.get.return_value = github_response([repository('one'), repository('two')])
        self.assertEqual(self.client.get('/api/repositories?limit=1').get_json()['count'], 1)
        response = self.client.get('/api/repositories?limit=2').get_json()
        self.assertEqual(response['count'], 2)
        self.assertTrue(response['cached'])
        self.get.assert_called_once()

    def test_force_refresh_and_expired_cache_fetch_fresh_data(self):
        self.get.side_effect = [github_response([repository(str(i))]) for i in range(3)]
        self.client.get('/api/repositories')
        refreshed = self.client.get('/api/repositories?force_refresh=true').get_json()
        self.assertEqual(refreshed['repositories'][0]['name'], '1')
        self.assertFalse(refreshed['cached'])
        api.repo_cache['last_updated'] = datetime.now() - timedelta(minutes=31)
        expired = self.client.get('/api/repositories').get_json()
        self.assertEqual(expired['repositories'][0]['name'], '2')
        self.assertFalse(expired['cached'])

    def test_failed_refresh_preserves_the_previous_cache(self):
        self.get.side_effect = [
            github_response([repository()]), requests.exceptions.Timeout('private detail'),
        ]
        self.client.get('/api/repositories')
        failed = self.client.get('/api/repositories?force_refresh=true')
        self.assertEqual(failed.status_code, 504)
        cached = self.client.get('/api/repositories').get_json()
        self.assertTrue(cached['cached'])
        self.assertEqual(cached['count'], 1)
        self.assertEqual(self.get.call_count, 2)


class InputValidationTests(APITestCase):
    def test_invalid_limits_are_rejected_before_contacting_github(self):
        for endpoint in ('/api/repositories', '/api/featured'):
            for limit in ('abc', '1.5', '0', '-1', ''):
                with self.subTest(endpoint=endpoint, limit=limit):
                    response = self.client.get(endpoint, query_string={'limit': limit})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn('error', response.get_json())
        self.get.assert_not_called()

    def test_invalid_repository_options_are_rejected(self):
        for query in ('sort=stars', 'sort=', 'include_forks=maybe', 'force_refresh=1'):
            with self.subTest(query=query):
                response = self.client.get('/api/repositories?' + query)
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.get_json())
        self.get.assert_not_called()

    def test_featured_limit_and_ranking_remain_compatible(self):
        self.get.return_value = github_response([
            repository('one', stars=1), repository('three', stars=3),
            repository('two', stars=2), repository('forked', fork=True, stars=100),
        ])
        response = self.client.get('/api/featured?limit=2')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([repo['name'] for repo in response.get_json()['featured_repositories']],
                         ['three', 'two'])


class GitHubResponseTests(APITestCase):
    def test_null_language_does_not_break_language_filter(self):
        self.get.return_value = github_response([
            repository('no-language', None), repository('python'),
        ])
        response = self.client.get('/api/repositories?languages=Python')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([repo['name'] for repo in response.get_json()['repositories']], ['python'])

    def test_all_repository_pages_are_returned(self):
        self.get.side_effect = [
            github_response([repository('page-one')], headers={
                'Link': '<https://api.github.com/users/octocat/repos?page=2>; rel="next"',
            }),
            github_response([repository('page-two')]),
        ]
        response = self.client.get('/api/repositories')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([repo['name'] for repo in response.get_json()['repositories']],
                         ['page-one', 'page-two'])
        self.assertEqual(self.get.call_args.kwargs['params']['page'], 2)

    def test_later_page_failure_does_not_cache_partial_results(self):
        self.get.side_effect = [
            github_response([repository()], headers={
                'Link': '<https://api.github.com/users/octocat/repos?page=2>; rel="next"',
            }),
            github_response({'message': 'unavailable'}, status=503),
        ]
        response = self.client.get('/api/repositories')
        self.assertEqual(response.status_code, 502)
        self.assertIsNone(api.repo_cache['data'])

    def test_timeouts_are_gateway_errors_on_every_endpoint(self):
        self.get.side_effect = requests.exceptions.Timeout('private timeout detail')
        self.post.side_effect = requests.exceptions.Timeout('private timeout detail')
        for endpoint in ('/api/repositories', '/api/featured', '/api/pinned',
                         '/api/repositories/example/languages', '/api/repositories/example/readme'):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 504)
                self.assertIn('error', response.get_json())
                self.assertNotIn('private timeout detail', response.get_data(as_text=True))

    def test_every_github_request_has_a_finite_timeout(self):
        self.get.return_value = github_response([])
        self.client.get('/api/repositories')
        self.get.return_value = github_response({})
        self.client.get('/api/repositories/example/languages')
        self.get.return_value = github_response({'content': base64.b64encode(b'hello').decode()})
        self.client.get('/api/repositories/example/readme')
        self.post.return_value = github_response({'data': {'user': {'pinnedItems': {'edges': []}}}})
        self.client.get('/api/pinned')
        for call in self.get.call_args_list + self.post.call_args_list:
            with self.subTest(call=call):
                timeout = call.kwargs.get('timeout')
                self.assertIsNotNone(timeout)
                values = timeout if isinstance(timeout, tuple) else (timeout,)
                self.assertTrue(all(0 < value <= 30 for value in values))

    def test_http_failures_are_not_successful_empty_responses(self):
        for status in (401, 403, 500, 503):
            for endpoint in ('/api/repositories', '/api/featured', '/api/pinned',
                             '/api/repositories/example/languages', '/api/repositories/example/readme'):
                with self.subTest(status=status, endpoint=endpoint):
                    self.get.return_value = github_response({'message': 'private detail'}, status)
                    self.post.return_value = github_response({'message': 'private detail'}, status)
                    response = self.client.get(endpoint)
                    self.assertEqual(response.status_code, 502)
                    self.assertIn('error', response.get_json())
                    self.assertNotIn('private detail', response.get_data(as_text=True))

    def test_connection_errors_are_gateway_errors(self):
        self.get.side_effect = requests.exceptions.ConnectionError('private detail')
        response = self.client.get('/api/repositories/example/languages')
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('private detail', response.get_data(as_text=True))

    def test_readme_not_found_preserves_existing_response(self):
        self.get.return_value = github_response({'message': 'Not Found'}, 404)
        response = self.client.get('/api/repositories/example/readme')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {
            'repository': 'example', 'readme': None,
            'message': 'README not found or not accessible',
        })

    def test_missing_repository_languages_return_not_found(self):
        self.get.return_value = github_response({'message': 'Not Found'}, 404)
        response = self.client.get('/api/repositories/example/languages')
        self.assertEqual(response.status_code, 404)
        self.assertIn('error', response.get_json())

    def test_successful_readme_decodes_wrapped_base64(self):
        encoded = base64.encodebytes('Hello, 世界!'.encode()).decode()
        self.get.return_value = github_response({
            'content': encoded, 'path': 'README.md', 'size': 14,
            'download_url': 'https://example.com/README.md',
        })
        response = self.client.get('/api/repositories/example/readme')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['readme']['content'], 'Hello, 世界!')

    def test_invalid_readme_content_is_a_gateway_error(self):
        for content in ('!!!', None, base64.b64encode(b'\xff').decode()):
            with self.subTest(content=content):
                self.get.return_value = github_response({'content': content})
                response = self.client.get('/api/repositories/example/readme')
                self.assertEqual(response.status_code, 502)
                self.assertIn('error', response.get_json())

    def test_wrong_json_shapes_are_gateway_errors(self):
        for endpoint, payload in (
            ('/api/repositories', {}),
            ('/api/repositories/example/languages', []),
            ('/api/repositories/example/readme', []),
            ('/api/pinned', {'data': {'user': None}}),
            ('/api/pinned', {}),
        ):
            with self.subTest(endpoint=endpoint, payload=payload):
                self.get.return_value = github_response(payload)
                self.post.return_value = github_response(payload)
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 502)
                self.assertIn('error', response.get_json())

    def test_pinned_response_keeps_nullable_language_and_project_fields(self):
        self.post.return_value = github_response({'data': {'user': {'pinnedItems': {
            'totalCount': 1,
            'edges': [{'node': {
                'id': 'project-id', 'name': 'example', 'nameWithOwner': 'octocat/example',
                'description': None, 'url': 'https://github.com/octocat/example',
                'homepageUrl': None, 'stargazerCount': 5, 'forkCount': 2,
                'isPrivate': False, 'isFork': False, 'isArchived': False,
                'createdAt': '2026-01-01T00:00:00Z',
                'updatedAt': '2026-10-01T00:00:00Z', 'pushedAt': None,
                'primaryLanguage': None,
                'languages': {'edges': [{'node': {'name': 'Python'}, 'size': 100}]},
                'repositoryTopics': {'edges': [{'node': {'topic': {'name': 'api'}}}]},
            }}],
        }}}})
        response = self.client.get('/api/pinned')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            'count': 1,
            'pinned_repositories': [{
                'name': 'example', 'description': 'No description available',
                'url': 'https://github.com/octocat/example', 'homepage': None,
                'language': None, 'language_color': None, 'stars': 5, 'forks': 2,
                'topics': ['api'], 'languages': {'Python': 100},
                'last_updated': '2026-10-01T00:00:00Z', 'is_pinned': True,
            }],
        })

    def test_empty_pinned_repositories_are_a_valid_success(self):
        self.post.return_value = github_response({'data': {'user': {'pinnedItems': {'edges': []}}}})
        response = self.client.get('/api/pinned')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'pinned_repositories': [], 'count': 0})

    def test_graphql_errors_do_not_masquerade_as_empty_pins(self):
        self.post.return_value = github_response({
            'data': {'user': None}, 'errors': [{'message': 'private detail'}],
        })
        response = self.client.get('/api/pinned')
        self.assertEqual(response.status_code, 502)
        self.assertIn('error', response.get_json())
        self.assertNotIn('private detail', response.get_data(as_text=True))

    def test_malformed_upstream_json_is_a_gateway_error(self):
        self.get.return_value = github_response({})
        self.get.return_value._content = b'not-json'
        response = self.client.get('/api/repositories/example/languages')
        self.assertEqual(response.status_code, 502)
        self.assertIn('error', response.get_json())


if __name__ == '__main__':
    unittest.main()
