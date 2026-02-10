"""Enhanced Website Crawling Agent."""

import requests
import re
import time
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Optional, Set

from .base_agent import BaseAgent
from orchestrator.context_store import PageData
from utils.scoring import ModuleScore, ScoreItem


class WebsiteAgent(BaseAgent):
    """
    Enhanced website crawling agent.

    Crawls up to 20 pages with:
    - Priority path detection
    - Segment/industry page detection
    - Resource hub detection
    - Page type classification
    """

    agent_name = "website"
    agent_description = "Crawls and indexes website pages"
    dependencies = []  # No dependencies - runs first
    weight = 0  # No scoring weight - just data collection

    # Expanded priority paths
    PRIORITY_PATHS = [
        '', '/about', '/about-us', '/pricing', '/products', '/product',
        '/solutions', '/services', '/contact', '/contact-us', '/blog',
        '/resources', '/customers', '/case-studies', '/features', '/platform',
        '/company', '/team', '/why-us', '/demo', '/free-trial',
        # New segment-related paths
        '/industries', '/verticals', '/use-cases', '/for-enterprise',
        '/for-startups', '/for-teams', '/segments', '/sectors'
    ]

    # Patterns for identifying segment/industry pages
    SEGMENT_PATTERNS = [
        r'/industries', r'/verticals', r'/for-', r'/use-case',
        r'/sector', r'/segment', r'/market'
    ]

    # Social media patterns
    SOCIAL_PATTERNS = {
        'linkedin': r'linkedin\.com',
        'twitter': r'(twitter\.com|x\.com)',
        'facebook': r'facebook\.com',
        'instagram': r'instagram\.com',
        'youtube': r'youtube\.com',
    }

    # CTA patterns
    CTA_PATTERNS = [
        r'get started', r'sign up', r'start free', r'book demo', r'schedule',
        r'contact', r'try free', r'request', r'download', r'learn more',
        r'buy now', r'subscribe', r'join', r'register', r'free trial'
    ]

    def __init__(self, context, llm_client=None, verbose=False):
        super().__init__(context, llm_client, verbose)
        self.visited: Set[str] = set()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    async def run(self) -> ModuleScore:
        """Execute website crawling asynchronously."""
        module = ModuleScore(name="Website Crawl", weight=0)

        base_url = self.context.company_website.rstrip('/')
        base_domain = urlparse(base_url).netloc
        max_pages = self.context.max_pages

        # Build priority queue
        to_visit = []
        for path in self.PRIORITY_PATHS:
            url = self._normalize_url(f"{base_url}{path}")
            if url not in to_visit:
                to_visit.append(url)

        pages_crawled = 0
        segment_pages_found = 0

        while to_visit and len(self.context.pages) < max_pages:
            url = to_visit.pop(0)
            normalized = self._normalize_url(url)

            if normalized in self.visited:
                continue

            self.visited.add(normalized)
            print(f"  Crawling: {url}")

            page = self._fetch_page(url, base_domain)
            if page:
                # Classify page type
                page.page_type = self._classify_page_type(url, page)

                # Detect segments mentioned on the page
                page.identified_segments = self._detect_segments(page)
                if page.identified_segments:
                    segment_pages_found += 1

                self.context.add_page(page)
                pages_crawled += 1

                # Add new internal links to queue
                for link in page.internal_links:
                    norm_link = self._normalize_url(link)
                    if norm_link not in self.visited and norm_link not in to_visit:
                        # Skip certain patterns
                        if not any(x in norm_link.lower() for x in ['/tag/', '/category/', '/page/', '#', '.pdf', '.jpg', '.png']):
                            # Prioritize segment-related pages
                            if any(re.search(p, norm_link.lower()) for p in self.SEGMENT_PATTERNS):
                                to_visit.insert(0, norm_link)  # Add to front
                            else:
                                to_visit.append(norm_link)

            time.sleep(1.0)  # Rate limiting

        # Store summary in module
        module.items.append(ScoreItem(
            name="Pages Crawled",
            description="Total pages indexed",
            max_points=max_pages,
            actual_points=pages_crawled,
            notes=f"Crawled {pages_crawled} of {max_pages} max pages"
        ))

        module.analysis_text = f"""
Website crawl completed for {self.context.company_name}.

**Summary:**
- Pages crawled: {pages_crawled}
- Segment-related pages: {segment_pages_found}
- Social links found: {', '.join(self.context.social_links.keys()) if self.context.social_links else 'None'}

**Page Types Found:**
{self._get_page_type_summary()}
"""

        module.raw_data = {
            'pages_crawled': pages_crawled,
            'segment_pages': segment_pages_found,
            'page_types': self._get_page_type_counts()
        }

        return module

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized

    def _is_internal(self, url: str, base_domain: str) -> bool:
        """Check if URL is internal to the base domain."""
        parsed = urlparse(url)
        return parsed.netloc == base_domain or parsed.netloc == ''

    def _fetch_page(self, url: str, base_domain: str) -> Optional[PageData]:
        """Fetch and parse a single page."""
        try:
            start_time = time.time()
            response = self.session.get(url, timeout=15, allow_redirects=True)
            load_time = time.time() - start_time

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'lxml')
            page = PageData(url=url)
            page.status_code = response.status_code
            page.load_time = load_time
            page.content_length = len(response.content)
            page.html = response.text

            # Title
            title_tag = soup.find('title')
            page.title = title_tag.get_text(strip=True) if title_tag else ""

            # Meta tags
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            page.meta_description = meta_desc.get('content', '') if meta_desc else ""

            meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
            page.meta_keywords = meta_keywords.get('content', '') if meta_keywords else ""

            # Headings
            page.h1_tags = [h.get_text(strip=True) for h in soup.find_all('h1')]
            page.h2_tags = [h.get_text(strip=True) for h in soup.find_all('h2')]
            page.h3_tags = [h.get_text(strip=True) for h in soup.find_all('h3')]

            # Paragraphs
            page.paragraphs = [p.get_text(strip=True) for p in soup.find_all('p') if p.get_text(strip=True)]

            # Links
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                full_url = urljoin(url, href)
                page.links.append(full_url)

                if self._is_internal(full_url, base_domain):
                    page.internal_links.append(full_url)
                else:
                    page.external_links.append(full_url)

                # Check for social links
                for platform, pattern in self.SOCIAL_PATTERNS.items():
                    if re.search(pattern, full_url, re.I):
                        page.social_links[platform] = full_url
                        if platform not in self.context.social_links:
                            self.context.social_links[platform] = full_url

            # Images
            for img in soup.find_all('img'):
                page.images.append({
                    'src': urljoin(url, img.get('src', '')),
                    'alt': img.get('alt', ''),
                    'has_alt': bool(img.get('alt')),
                })

            # CTAs
            for element in soup.find_all(['a', 'button']):
                text = element.get_text(strip=True).lower()
                for pattern in self.CTA_PATTERNS:
                    if re.search(pattern, text, re.I):
                        page.ctas.append({
                            'text': element.get_text(strip=True),
                            'tag': element.name,
                            'href': element.get('href', ''),
                        })
                        break

            # Forms
            for form in soup.find_all('form'):
                inputs = form.find_all(['input', 'textarea', 'select'])
                page.forms.append({
                    'action': form.get('action', ''),
                    'method': form.get('method', 'get'),
                    'field_count': len(inputs),
                    'fields': [i.get('name', i.get('placeholder', '')) for i in inputs],
                })

            # Testimonials
            testimonial_patterns = [
                soup.find_all(class_=re.compile(r'testimonial|quote|review', re.I)),
                soup.find_all('blockquote'),
            ]
            for pattern_results in testimonial_patterns:
                for elem in pattern_results:
                    text = elem.get_text(strip=True)
                    if len(text) > 20:
                        page.testimonials.append(text[:500])

            # Schema markup
            schema_scripts = soup.find_all('script', type='application/ld+json')
            if schema_scripts:
                page.has_schema = True
                for script in schema_scripts:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and '@type' in data:
                            page.schema_types.append(data['@type'])
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and '@type' in item:
                                    page.schema_types.append(item['@type'])
                    except:
                        pass

            # Raw text
            for script in soup(["script", "style"]):
                script.decompose()
            page.raw_text = soup.get_text(separator=' ', strip=True)

            return page

        except Exception as e:
            print(f"  Error fetching {url}: {e}")
            return None

    def _classify_page_type(self, url: str, page: PageData) -> str:
        """Classify the page type based on URL and content."""
        url_lower = url.lower()
        base = self.context.company_website.rstrip('/')

        if url.rstrip('/') == base:
            return 'homepage'
        if '/pricing' in url_lower:
            return 'pricing'
        if '/about' in url_lower or '/team' in url_lower or '/company' in url_lower:
            return 'about'
        if '/product' in url_lower or '/platform' in url_lower or '/features' in url_lower:
            return 'product'
        if '/solution' in url_lower:
            return 'solutions'
        if '/blog' in url_lower or '/posts' in url_lower:
            return 'blog'
        if '/case-stud' in url_lower or '/customer' in url_lower:
            return 'case_study'
        if '/resource' in url_lower or '/guide' in url_lower or '/ebook' in url_lower:
            return 'resources'
        if '/contact' in url_lower:
            return 'contact'
        if '/demo' in url_lower or '/trial' in url_lower:
            return 'conversion'
        if any(re.search(p, url_lower) for p in self.SEGMENT_PATTERNS):
            return 'segment'

        return 'other'

    def _detect_segments(self, page: PageData) -> List[str]:
        """Detect industry/segment mentions on the page."""
        segments = []
        text = page.raw_text.lower()

        # Common B2B industry/segment patterns
        segment_keywords = [
            'healthcare', 'financial services', 'fintech', 'education', 'edtech',
            'retail', 'ecommerce', 'manufacturing', 'logistics', 'real estate',
            'legal', 'insurance', 'technology', 'saas', 'enterprise', 'smb',
            'startups', 'agencies', 'government', 'nonprofit', 'media'
        ]

        for keyword in segment_keywords:
            if keyword in text:
                segments.append(keyword)

        return segments[:10]  # Limit to top 10

    def _get_page_type_summary(self) -> str:
        """Get summary of page types found."""
        counts = self._get_page_type_counts()
        lines = []
        for page_type, count in sorted(counts.items(), key=lambda x: -x[1]):
            lines.append(f"- {page_type}: {count}")
        return '\n'.join(lines)

    def _get_page_type_counts(self) -> Dict[str, int]:
        """Get counts by page type."""
        counts = {}
        for page in self.context.pages.values():
            pt = page.page_type or 'other'
            counts[pt] = counts.get(pt, 0) + 1
        return counts

    def self_audit(self) -> bool:
        """Validate crawl quality."""
        # Need at least 1 page crawled
        if len(self.context.pages) < 1:
            return False

        # Should have found the homepage
        if not self.context.get_homepage():
            return False

        return True
