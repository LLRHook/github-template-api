# GitHub Template API

A Flask-based API service for fetching GitHub repositories to template website sections with your project portfolio.

## 🚀 Quick Start

### 1. Clone and Setup

```bash
# Clone the repository (if you haven't already)
git clone <your-repo-url>
cd github-template-api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` with your GitHub credentials:

```env
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_USERNAME=your_github_username
FLASK_ENV=development
FLASK_DEBUG=True
```

### 3. Get GitHub Personal Access Token

1. Go to [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Select scopes: `public_repo` (for public repositories)
4. Copy the token and add it to your `.env` file

### 4. Run the API

```bash
python app.py
```

The API will be available at `http://localhost:5000`

## 📡 API Endpoints

### Health Check
```
GET /
```

Returns API status and configuration info.

### Get All Repositories
```
GET /api/repositories
```

**Query Parameters:**
- `include_forks` (boolean): Include forked repositories (default: false)
- `languages` (string): Comma-separated list of languages to filter by
- `sort` (string): Sort order - `updated`, `created`, `pushed`, `full_name` (default: updated)
- `limit` (integer): Maximum number of repositories to return
- `force_refresh` (boolean): Force refresh of cached data (default: false)

**Example:**
```bash
curl "http://localhost:5000/api/repositories?limit=10&languages=Python,JavaScript"
```

### Get Pinned Repositories
```
GET /api/pinned
```

Returns your pinned repositories - the ones you've specifically chosen to showcase on your GitHub profile. **This is the best endpoint for portfolio websites!**

**Example:**
```bash
curl "http://localhost:5000/api/pinned"
```

### Get Featured Repositories
```
GET /api/featured
```

Returns top repositories optimized for website display (based on stars and activity).

**Query Parameters:**
- `limit` (integer): Number of featured repositories (default: 6)

**Example:**
```bash
curl "http://localhost:5000/api/featured?limit=4"
```

### Get Repository Languages
```
GET /api/repositories/{repo_name}/languages
```

Returns programming languages used in a specific repository.

## 📋 Response Format

### Repository Object
```json
{
  "id": 12345,
  "name": "my-awesome-project",
  "full_name": "username/my-awesome-project",
  "description": "An awesome project description",
  "url": "https://github.com/username/my-awesome-project",
  "clone_url": "https://github.com/username/my-awesome-project.git",
  "language": "Python",
  "stars": 42,
  "forks": 7,
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-12-01T00:00:00Z",
  "pushed_at": "2023-12-01T00:00:00Z",
  "topics": ["api", "python", "flask"],
  "is_private": false,
  "homepage": "https://my-project.com",
  "archived": false
}
```

## 🌐 Frontend Integration

### JavaScript Example

```javascript
// Fetch featured repositories for your website
async function loadFeaturedProjects() {
  try {
    const response = await fetch('http://localhost:5000/api/featured?limit=6');
    const data = await response.json();
    
    const projectsContainer = document.getElementById('projects');
    
    data.featured_repositories.forEach(repo => {
      const projectCard = `
        <div class="project-card">
          <h3><a href="${repo.url}" target="_blank">${repo.name}</a></h3>
          <p>${repo.description}</p>
          <div class="project-meta">
            <span class="language">${repo.language || 'N/A'}</span>
            <span class="stars">⭐ ${repo.stars}</span>
          </div>
          <div class="topics">
            ${repo.topics.map(topic => `<span class="topic">${topic}</span>`).join('')}
          </div>
        </div>
      `;
      projectsContainer.innerHTML += projectCard;
    });
  } catch (error) {
    console.error('Failed to load projects:', error);
  }
}

// Load projects when page loads
document.addEventListener('DOMContentLoaded', loadFeaturedProjects);
```

### React Example

```jsx
import { useState, useEffect } from 'react';

function FeaturedProjects() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:5000/api/featured?limit=6')
      .then(res => res.json())
      .then(data => {
        setProjects(data.featured_repositories);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load projects:', err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Loading projects...</div>;

  return (
    <div className="featured-projects">
      <h2>Featured Projects</h2>
      <div className="projects-grid">
        {projects.map(project => (
          <div key={project.name} className="project-card">
            <h3>
              <a href={project.url} target="_blank" rel="noopener noreferrer">
                {project.name}
              </a>
            </h3>
            <p>{project.description}</p>
            <div className="project-meta">
              <span className="language">{project.language || 'N/A'}</span>
              <span className="stars">⭐ {project.stars}</span>
            </div>
            <div className="topics">
              {project.topics.map(topic => (
                <span key={topic} className="topic">{topic}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

## 🔧 Configuration Options

### Environment Variables

- `GITHUB_TOKEN`: Your GitHub personal access token
- `GITHUB_USERNAME`: Your GitHub username
- `FLASK_ENV`: Flask environment (development/production)
- `FLASK_DEBUG`: Enable Flask debug mode (True/False)
- `PORT`: Port to run the server on (default: 5000)

### Caching

The API includes built-in caching to avoid hitting GitHub's rate limits:
- Cache duration: 30 minutes
- Force refresh: Use `force_refresh=true` parameter
- In production: Consider using Redis for distributed caching

## 🚀 Deployment

### Using Gunicorn (Production)

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Docker

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

### Environment Variables for Production

Make sure to set these in your production environment:
- `GITHUB_TOKEN`
- `GITHUB_USERNAME`
- `FLASK_ENV=production`
- `FLASK_DEBUG=False`

## 🔒 Security Notes

1. **Never commit your `.env` file** - it's already in `.gitignore`
2. **Use environment variables** in production, not `.env` files
3. **Rotate your GitHub tokens** regularly
4. **Use HTTPS** in production
5. **Consider rate limiting** for public APIs

## 📈 Rate Limits

GitHub API rate limits:
- **Authenticated requests**: 5,000 per hour
- **Unauthenticated requests**: 60 per hour

The API includes caching to help manage rate limits effectively.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

This project is licensed under the MIT License. 