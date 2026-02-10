"""Shared context store for agentic audit coordination."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime


class AgentStatus(Enum):
    """Status of an agent's execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVISION = "needs_revision"


@dataclass
class PageData:
    """Data extracted from a single page."""
    url: str
    title: str = ""
    meta_description: str = ""
    meta_keywords: str = ""
    h1_tags: List[str] = field(default_factory=list)
    h2_tags: List[str] = field(default_factory=list)
    h3_tags: List[str] = field(default_factory=list)
    paragraphs: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    internal_links: List[str] = field(default_factory=list)
    external_links: List[str] = field(default_factory=list)
    images: List[Dict] = field(default_factory=list)
    ctas: List[Dict] = field(default_factory=list)
    social_links: Dict[str, str] = field(default_factory=dict)
    forms: List[Dict] = field(default_factory=list)
    testimonials: List[str] = field(default_factory=list)
    load_time: float = 0.0
    status_code: int = 0
    content_length: int = 0
    has_schema: bool = False
    schema_types: List[str] = field(default_factory=list)
    raw_text: str = ""
    html: str = ""
    page_type: str = ""  # home, product, solutions, pricing, about, blog, etc.
    identified_segments: List[str] = field(default_factory=list)


@dataclass
class ScreenshotData:
    """Screenshot data for a page or element."""
    url: str
    screenshot_type: str  # "full_page" or "element"
    base64_data: str
    width: int = 0
    height: int = 0
    element_selector: str = ""
    captured_at: str = ""
    notes: str = ""


@dataclass
class SegmentInfo:
    """Information about an identified target segment."""
    name: str
    description: str = ""
    pain_points: List[str] = field(default_factory=list)
    coverage_score: float = 0.0  # 0-100
    pages_addressing: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class CriticalPage:
    """Data about a critical page (Top 5)."""
    page_type: str  # homepage, product, solutions, pricing, about
    url: str
    grade: str = ""
    score: float = 0.0
    max_score: float = 100.0
    screenshot: Optional[ScreenshotData] = None
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class AgentAnalysis:
    """Result from an agent's analysis."""
    agent_name: str
    status: AgentStatus = AgentStatus.PENDING
    module_score: Optional[Any] = None  # ModuleScore
    analysis_text: str = ""
    hidden_plan: str = ""  # Chain of Thouht plan
    raw_data: Dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    revision_count: int = 0
    self_audit_passed: bool = False


@dataclass
class ContextStore:
    """
    Shared state container for all agents during an audit.

    This is the central data store that agents read from and write to.
    It enables agents to coordinate and share information.
    """
    # Configuration
    company_name: str = ""
    company_website: str = ""
    industry: str = "B2B SaaS"
    audit_date: str = ""
    analyst_name: str = ""
    analyst_company: str = "Bhavsar Growth Consulting"
    analyst_website: str = "https://growth.llc"
    competitors: List[str] = field(default_factory=list)
    max_pages: int = 20

    # Crawled data
    pages: Dict[str, PageData] = field(default_factory=dict)

    # Screenshots
    screenshots: Dict[str, ScreenshotData] = field(default_factory=dict)

    # Agent analyses
    analyses: Dict[str, AgentAnalysis] = field(default_factory=dict)

    # Segmentation data
    identified_segments: List[SegmentInfo] = field(default_factory=list)
    primary_segment: str = ""
    primary_segment_justification: str = ""
    primary_segment_priority: str = ""

    # Critical pages (Top 5)
    critical_pages: List[CriticalPage] = field(default_factory=list)

    # Resource hub data
    landing_pages: List[Dict] = field(default_factory=list)
    gated_content: List[Dict] = field(default_factory=list)

    # Logos
    client_logo_b64: str = ""
    analyst_logo_b64: str = ""

    # Social links
    social_links: Dict[str, str] = field(default_factory=dict)

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = ""
    revision_cycle: int = 0
    max_revisions: int = 3

    def update_timestamp(self):
        """Update the last_updated timestamp."""
        self.last_updated = datetime.now().isoformat()

    def get_page(self, url: str) -> Optional[PageData]:
        """Get page data by URL."""
        return self.pages.get(url)

    def add_page(self, page: PageData):
        """Add or update a page in the store."""
        self.pages[page.url] = page
        self.update_timestamp()

    def get_screenshot(self, url: str) -> Optional[ScreenshotData]:
        """Get screenshot by URL."""
        return self.screenshots.get(url)

    def add_screenshot(self, screenshot: ScreenshotData):
        """Add a screenshot to the store."""
        key = f"{screenshot.url}:{screenshot.screenshot_type}"
        if screenshot.element_selector:
            key += f":{screenshot.element_selector}"
        self.screenshots[key] = screenshot
        self.update_timestamp()

    def get_analysis(self, agent_name: str) -> Optional[AgentAnalysis]:
        """Get analysis by agent name."""
        return self.analyses.get(agent_name)

    def set_analysis(self, analysis: AgentAnalysis):
        """Set analysis for an agent."""
        self.analyses[analysis.agent_name] = analysis
        self.update_timestamp()

    def get_homepage(self) -> Optional[PageData]:
        """Get the homepage data."""
        # Try common patterns
        patterns = [
            self.company_website.rstrip('/'),
            f"{self.company_website.rstrip('/')}/",
        ]
        for pattern in patterns:
            if pattern in self.pages:
                return self.pages[pattern]
        # Return first page if no exact match
        if self.pages:
            return list(self.pages.values())[0]
        return None

    def get_pages_by_type(self, page_type: str) -> List[PageData]:
        """Get all pages of a specific type."""
        return [p for p in self.pages.values() if p.page_type == page_type]

    def get_all_ctas(self) -> List[Dict]:
        """Get all CTAs from all pages."""
        all_ctas = []
        for page in self.pages.values():
            for cta in page.ctas:
                cta_with_page = cta.copy()
                cta_with_page['page_url'] = page.url
                all_ctas.append(cta_with_page)
        return all_ctas

    def get_all_forms(self) -> List[Dict]:
        """Get all forms from all pages."""
        all_forms = []
        for page in self.pages.values():
            for form in page.forms:
                form_with_page = form.copy()
                form_with_page['page_url'] = page.url
                all_forms.append(form_with_page)
        return all_forms

    def request_additional_crawl(self, urls: List[str]) -> List[str]:
        """
        Request additional URLs to be crawled.
        Returns list of URLs that were added to the queue.
        """
        # This will be handled by the orchestrator
        new_urls = [url for url in urls if url not in self.pages]
        return new_urls

    def is_complete(self) -> bool:
        """Check if all required analyses are complete."""
        required_agents = [
            'website', 'positioning', 'seo', 'conversion',
            'content', 'trust', 'social', 'segmentation',
            'resource_hub', 'top5_pages'
        ]
        for agent in required_agents:
            analysis = self.analyses.get(agent)
            if not analysis or analysis.status != AgentStatus.COMPLETED:
                return False
        return True

    def get_summary(self) -> Dict:
        """Get a summary of the context store state."""
        return {
            'company': self.company_name,
            'website': self.company_website,
            'pages_crawled': len(self.pages),
            'screenshots_captured': len(self.screenshots),
            'analyses_completed': sum(1 for a in self.analyses.values()
                                      if a.status == AgentStatus.COMPLETED),
            'analyses_pending': sum(1 for a in self.analyses.values()
                                    if a.status == AgentStatus.PENDING),
            'segments_identified': len(self.identified_segments),
            'critical_pages_graded': len(self.critical_pages),
            'revision_cycle': self.revision_cycle,
        }
