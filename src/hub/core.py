from flask import Flask, jsonify, render_template, abort, request, url_for
from pathlib import Path
import os
import datetime
import logging
import markdown
import yaml
from typing import Dict, List, Optional
from functools import lru_cache
import time

class VeinityHub:
    def __init__(self):
        # Initialize Flask app with correct template directory
        self.app = Flask(__name__, template_folder='templates')
        self.app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
        
        # Setup logging
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        
        # Configure paths
        self.base_path = Path(os.path.dirname(os.path.dirname(__file__)))
        self.library = self.base_path / "modules" / "library" / "articles"
        self.cache = self.base_path / "modules" / "library" / "cache"
        
        # Load configurations
        self.ad_config = self._load_ad_config()
        self.site_config = self._load_site_config()
        
        # Initialize cache timestamp
        self._last_cache_update = time.time()
        
    def _load_ad_config(self) -> Dict:
        """Load advertising configuration"""
        config_path = self.base_path / "config" / "ads.yaml"
        try:
            if config_path.exists():
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
            return {
                'enabled': False,
                'slots': {
                    'header': '',
                    'sidebar': '',
                    'in_content': '',
                    'footer': ''
                }
            }
        except Exception as e:
            self.logger.error(f"Error loading ad config: {str(e)}")
            return {}

    def _load_site_config(self) -> Dict:
        """Load site configuration"""
        config_path = self.base_path / "config" / "site.yaml"
        try:
            if config_path.exists():
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
            return {
                'site_name': 'Veinity',
                'description': 'Your source for tech news and insights',
                'contact_email': '',
                'social_links': {}
            }
        except Exception as e:
            self.logger.error(f"Error loading site config: {str(e)}")
            return {}

    def _should_update_cache(self, max_age: int = 300) -> bool:
        """Check if cache should be updated (default 5 minutes)"""
        return time.time() - self._last_cache_update > max_age

    def _parse_article_metadata(self, content: str) -> tuple[Dict, str]:
        """Extract YAML frontmatter and markdown content"""
        if content.startswith('---'):
            try:
                _, frontmatter, markdown_content = content.split('---', 2)
                metadata = yaml.safe_load(frontmatter)
                return metadata, markdown_content.strip()
            except Exception as e:
                self.logger.error(f"Error parsing frontmatter: {str(e)}")
        return {}, content

    @lru_cache(maxsize=32)
    def _get_article_preview(self, content: str, length: int = 160) -> str:
        """Generate article preview from content"""
        try:
            # Remove YAML frontmatter if present
            if content.startswith('---'):
                content = content.split('---', 2)[2]
            
            # Convert markdown to plain text
            text = content.replace('#', '').replace('*', '').strip()
            
            # Return truncated preview
            if len(text) > length:
                return text[:length].rsplit(' ', 1)[0] + '...'
            return text
        except Exception as e:
            self.logger.error(f"Error generating preview: {str(e)}")
            return ""

    def _get_recent_articles(self, category: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """Get recent articles, optionally filtered by category"""
        articles = []
        try:
            search_path = self.library / category if category else self.library
            files = sorted(search_path.glob('*.md'), key=os.path.getmtime, reverse=True)
            
            for file_path in files[:limit]:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    metadata, _ = self._parse_article_metadata(content)
                    if metadata:
                        metadata['path'] = str(file_path.relative_to(self.library))
                        articles.append(metadata)
                        
            return articles
        except Exception as e:
            self.logger.error(f"Error getting recent articles: {str(e)}")
            return []

    def _get_categories(self) -> List[str]:
        """Get list of available categories"""
        try:
            return [d.name for d in self.library.iterdir() if d.is_dir()]
        except Exception as e:
            self.logger.error(f"Error getting categories: {str(e)}")
            return []

    def _get_related_articles(self, article_metadata: Dict, limit: int = 3) -> List[Dict]:
        """Get related articles based on category and tags"""
        try:
            related = []
            current_category = article_metadata.get('category')
            current_tags = set(article_metadata.get('tags', []))
            
            for article_file in self.library.rglob('*.md'):
                if len(related) >= limit:
                    break
                    
                with open(article_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    metadata, _ = self._parse_article_metadata(content)
                    
                    # Skip current article
                    if metadata.get('title') == article_metadata.get('title'):
                        continue
                    
                    # Check if related by category or tags
                    if (metadata.get('category') == current_category or 
                        set(metadata.get('tags', [])) & current_tags):
                        metadata['path'] = str(article_file.relative_to(self.library))
                        related.append(metadata)
            
            return related
        except Exception as e:
            self.logger.error(f"Error finding related articles: {str(e)}")
            return []

    def _format_date(self, date_str: str, format: str = '%B %d, %Y') -> str:
        """Format date string for display"""
        try:
            date_obj = datetime.datetime.fromisoformat(date_str)
            return date_obj.strftime(format)
        except Exception as e:
            self.logger.error(f"Error formatting date: {str(e)}")
            return date_str

    def setup_routes(self):
        @self.app.route('/')
        def index():
            """Render the homepage with recent articles"""
            recent_articles = self._get_recent_articles(limit=10)
            categories = self._get_categories()
            
            return render_template('index.html',
                title="Veinity - Latest Tech News",
                articles=recent_articles,
                categories=categories,
                ad_config=self.ad_config)

        @self.app.route('/category/<category>')
        def category_view(category: str):
            """Render category-specific article listing"""
            articles = self._get_recent_articles(category=category)
            if not articles:
                abort(404)
                
            return render_template('category.html',
                title=f"Veinity - {category.title()} News",
                category=category,
                articles=articles,
                ad_config=self.ad_config)

        @self.app.route('/article/<path:article_path>')
        def article_view(article_path: str):
            """Render individual article"""
            try:
                article_file = self.library / article_path
                if not article_file.exists():
                    abort(404)
                    
                with open(article_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                metadata, markdown_content = self._parse_article_metadata(content)
                html_content = markdown.markdown(
                    markdown_content,
                    extensions=['fenced_code', 'codehilite', 'tables', 'toc']
                )
                
                related_articles = self._get_related_articles(metadata)
                
                return render_template('article.html',
                    title=metadata.get('title', 'Article'),
                    metadata=metadata,
                    content=html_content,
                    related_articles=related_articles,
                    ad_config=self.ad_config)
                    
            except Exception as e:
                self.logger.error(f"Error rendering article: {str(e)}")
                abort(500)

        @self.app.route('/search')
        def search():
            """Search articles"""
            query = request.args.get('q', '')
            if not query:
                return render_template('search.html', 
                    title="Search Articles",
                    results=[])
                
            # Basic search implementation
            results = []
            for article_file in self.library.rglob('*.md'):
                try:
                    with open(article_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        metadata, markdown_content = self._parse_article_metadata(content)
                        if query.lower() in content.lower():
                            metadata['path'] = str(article_file.relative_to(self.library))
                            results.append(metadata)
                except Exception as e:
                    self.logger.error(f"Error searching file {article_file}: {str(e)}")
                    
            return render_template('search.html',
                title=f"Search Results for '{query}'",
                query=query,
                results=results,
                ad_config=self.ad_config)

        @self.app.route("/health")
        def health():
            """Health check endpoint"""
            try:
                # Basic check that we can access library
                if not self.library.exists():
                    self.logger.warning("Library directory not found")
                
                return jsonify({
                    "status": "operational",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "version": "0.1.0"
                })
            except Exception as e:
                self.logger.error(f"Health check failed: {str(e)}")
                return jsonify({
                    "status": "error",
                    "error": str(e)
                }), 500

        @self.app.template_filter('format_date')
        def format_date_filter(date_str: str, format: str = '%B %d, %Y') -> str:
            """Template filter for date formatting"""
            return self._format_date(date_str, format)

        @self.app.context_processor
        def inject_globals():
            """Inject global template variables"""
            return {
                'categories': self._get_categories(),
                'current_year': datetime.datetime.now().year,
                'site_name': self.site_config.get('site_name', 'Veinity'),
                'site_description': self.site_config.get('description', ''),
                'social_links': self.site_config.get('social_links', {}),
                'analytics_id': os.getenv('ANALYTICS_ID', ''),
                'get_recent_articles': self._get_recent_articles
            }

        @self.app.template_filter('truncate_html')
        def truncate_html_filter(content: str, length: int = 160) -> str:
            """Template filter for truncating HTML content"""
            return self._get_article_preview(content, length)

        @self.app.errorhandler(404)
        def page_not_found(e):
            """Custom 404 error handler"""
            return render_template('404.html', title='Page Not Found'), 404

        @self.app.errorhandler(500)
        def server_error(e):
            """Custom 500 error handler"""
            return render_template('500.html', title='Server Error'), 500
