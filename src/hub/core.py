from flask import Flask, jsonify, render_template, abort, request
from pathlib import Path
import os
import datetime
import logging
import markdown
import yaml
from typing import Dict, List, Optional

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
        self.library = self.base_path / "library" / "articles"
        self.cache = self.base_path / "library" / "cache"
        
        # Load configurations
        self.ad_config = self._load_ad_config()
        
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
                
                return render_template('article.html',
                    title=metadata.get('title', 'Article'),
                    metadata=metadata,
                    content=html_content,
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

        @self.app.context_processor
        def inject_globals():
            """Inject global template variables"""
            return {
                'categories': self._get_categories(),
                'current_year': datetime.datetime.now().year,
                'site_name': 'Veinity',
                'analytics_id': os.getenv('ANALYTICS_ID', '')
            }