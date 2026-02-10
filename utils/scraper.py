"""Web scraping utilities for marketing audit."""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import re
import socket
import ipaddress
import logging
from typing import Dict, List, Optional, Set
from xml.etree import ElementTree
from orchestrator.context_store import PageData

logger = logging.getLogger(__name__)


class WebScraper:
    """Web scraper for marketing audit."""

    SOCIAL_PATTERNS = {
        'linkedin': r'linkedin\.com',
        'twitter': r'(twitter\.com|x\.com)',
        'facebook': r'facebook\.com',
        'instagram': r'instagram\.com',
        'youtube': r'youtube\.com',
    }

    CTA_PATTERNS = [
        r'get started', r'sign up', r'start free', r'book demo', r'schedule',
        r'contact', r'try free', r'request', r'download', r'learn more',
        r'buy now', r'subscribe', r'join', r'register', r'free trial'
    ]

    def __init__(self, base_url: str, max_pages: int = 10, delay: float = 1.0):
        self.base_url = base_url.rstrip('/')
        self.base_domain = urlparse(base_url).netloc
        self.max_pages = max_pages
        self.delay = delay
        self.visited: Set[str] = set()
        self.pages: Dict[str, PageData] = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        parsed = urlparse(url)
        # Remove fragments and trailing slashes
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized

    def is_internal(self, url: str) -> bool:
        """Check if URL is internal to the base domain."""
        parsed = urlparse(url)
        return parsed.netloc == self.base_domain or parsed.netloc == ''

    def validate_url(self, url: str) -> None:
        """Validate URL to prevent SSRF attacks.

        Raises ValueError if the URL is unsafe.
        """
        parsed = urlparse(url)

        # Only allow http and https schemes
        if parsed.scheme not in ('http', 'https'):
            raise ValueError(f"Blocked scheme: {parsed.scheme}")

        hostname = parsed.hostname
        if not hostname:
            raise ValueError("URL has no hostname")

        # Block metadata endpoints
        if hostname in ('metadata.google.internal', '169.254.169.254'):
            raise ValueError(f"Blocked metadata endpoint: {hostname}")

        # Resolve hostname and check IP ranges
        try:
            addr_info = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            raise ValueError(f"Cannot resolve hostname: {hostname}")

        for family, _type, _proto, _canonname, sockaddr in addr_info:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError(f"Blocked private/reserved IP: {ip}")

    def fetch_page(self, url: str) -> Optional[PageData]:
        """Fetch and parse a single page."""
        try:
            self.validate_url(url)
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

                if self.is_internal(full_url):
                    page.internal_links.append(full_url)
                else:
                    page.external_links.append(full_url)

                # Check for social links
                for platform, pattern in self.SOCIAL_PATTERNS.items():
                    if re.search(pattern, full_url, re.I):
                        page.social_links[platform] = full_url

            # Images
            for img in soup.find_all('img'):
                page.images.append({
                    'src': urljoin(url, img.get('src', '')),
                    'alt': img.get('alt', ''),
                    'has_alt': bool(img.get('alt')),
                })

            # CTAs (buttons and links with CTA-like text)
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

            # Testimonials (heuristic detection)
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
                        import json
                        data = json.loads(script.string)
                        if isinstance(data, dict) and '@type' in data:
                            page.schema_types.append(data['@type'])
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and '@type' in item:
                                    page.schema_types.append(item['@type'])
                    except:
                        pass

            # Raw text for analysis
            for script in soup(["script", "style"]):
                script.decompose()
            page.raw_text = soup.get_text(separator=' ', strip=True)

            return page

        except Exception as e:
            print(f"  Error fetching {url}: {e}")
            return None

    def parse_sitemap(self, base_url: str) -> List[str]:
        """
        Parse sitemap.xml to discover URLs.

        Handles both regular sitemaps and sitemap index files.
        Returns only same-domain URLs.
        """
        sitemap_url = f"{base_url.rstrip('/')}/sitemap.xml"
        urls = []

        try:
            response = self.session.get(sitemap_url, timeout=10)
            if response.status_code != 200:
                logger.info("No sitemap found at %s (status %d)", sitemap_url, response.status_code)
                return []

            root = ElementTree.fromstring(response.content)
            # Handle namespace
            ns = ''
            if root.tag.startswith('{'):
                ns = root.tag.split('}')[0] + '}'

            # Check if this is a sitemap index file
            sitemap_tags = root.findall(f'{ns}sitemap')
            if sitemap_tags:
                # Sitemap index - fetch each child sitemap
                for sitemap in sitemap_tags:
                    loc = sitemap.find(f'{ns}loc')
                    if loc is not None and loc.text:
                        child_urls = self._parse_single_sitemap(loc.text.strip())
                        urls.extend(child_urls)
            else:
                # Regular sitemap - extract <loc> URLs
                for url_tag in root.findall(f'{ns}url'):
                    loc = url_tag.find(f'{ns}loc')
                    if loc is not None and loc.text:
                        urls.append(loc.text.strip())

        except Exception as e:
            logger.info("Error parsing sitemap for %s: %s", base_url, e)
            return []

        # Filter to same domain only
        base_domain = urlparse(base_url).netloc
        same_domain_urls = [u for u in urls if urlparse(u).netloc == base_domain]

        logger.info("Sitemap: discovered %d URLs (%d same-domain)", len(urls), len(same_domain_urls))
        return same_domain_urls

    def _parse_single_sitemap(self, sitemap_url: str) -> List[str]:
        """Parse a single sitemap XML file and return list of URLs."""
        urls = []
        try:
            response = self.session.get(sitemap_url, timeout=10)
            if response.status_code != 200:
                return []

            root = ElementTree.fromstring(response.content)
            ns = ''
            if root.tag.startswith('{'):
                ns = root.tag.split('}')[0] + '}'

            for url_tag in root.findall(f'{ns}url'):
                loc = url_tag.find(f'{ns}loc')
                if loc is not None and loc.text:
                    urls.append(loc.text.strip())
        except Exception as e:
            logger.info("Error parsing child sitemap %s: %s", sitemap_url, e)
        return urls

    def crawl(self) -> Dict[str, PageData]:
        """Crawl the website up to max_pages."""
        # Priority pages to try first
        priority_paths = [
            '', '/about', '/about-us', '/pricing', '/products', '/product',
            '/solutions', '/services', '/contact', '/contact-us', '/blog',
            '/resources', '/customers', '/case-studies', '/features', '/platform',
            '/company', '/team', '/why-us', '/demo', '/free-trial'
        ]

        # Start with priority URLs
        to_visit = []
        for path in priority_paths:
            url = self.normalize_url(f"{self.base_url}{path}")
            if url not in to_visit:
                to_visit.append(url)

        while to_visit and len(self.pages) < self.max_pages:
            url = to_visit.pop(0)
            normalized = self.normalize_url(url)

            if normalized in self.visited:
                continue

            self.visited.add(normalized)
            print(f"  Crawling: {url}")

            page = self.fetch_page(url)
            if page:
                self.pages[normalized] = page

                # Add new internal links to queue
                for link in page.internal_links:
                    norm_link = self.normalize_url(link)
                    if norm_link not in self.visited and norm_link not in to_visit:
                        # Skip certain patterns
                        if not any(x in norm_link.lower() for x in ['/tag/', '/category/', '/page/', '#', '.pdf', '.jpg', '.png']):
                            to_visit.append(norm_link)

            time.sleep(self.delay)

        return self.pages

    def get_all_social_links(self) -> Dict[str, str]:
        """Aggregate social links from all pages."""
        social = {}
        for page in self.pages.values():
            social.update(page.social_links)
        return social

    def get_homepage(self) -> Optional[PageData]:
        """Get the homepage data."""
        home_url = self.normalize_url(self.base_url)
        return self.pages.get(home_url)
