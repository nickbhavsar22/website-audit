"""Top 5 Critical Pages Analysis Agent."""

from typing import List, Optional

from .base_agent import BaseAgent
from orchestrator.context_store import CriticalPage, ScreenshotData
from utils.scoring import ModuleScore, ScoreItem, Recommendation, Impact, Effort, KPIImpact


class Top5PagesAgent(BaseAgent):
    """
    Grades the 5 most critical pages with screenshots.

    Analyzes:
    - Homepage
    - Product/Platform page
    - Solutions page
    - Pricing page
    - About page

    Each page gets a detailed grade with screenshot for the report.
    """

    agent_name = "top5_pages"
    agent_description = "Grades critical pages with screenshots"
    dependencies = ["website", "positioning"]
    weight = 1.5  # Higher weight for critical page analysis

    CRITICAL_PAGE_TYPES = [
        ('homepage', [''], 'Homepage'),
        ('product', ['/product', '/platform', '/features'], 'Product/Platform'),
        ('solutions', ['/solutions', '/use-cases'], 'Solutions'),
        ('pricing', ['/pricing', '/plans'], 'Pricing'),
        ('about', ['/about', '/about-us', '/company', '/team'], 'About'),
    ]

    async def run(self) -> ModuleScore:
        """Execute critical pages analysis asynchronously."""
        module = ModuleScore(name="Top 5 Critical Pages", weight=self.weight)

        # Find the critical pages
        critical_pages = self._find_critical_pages()

        if not critical_pages:
            module.analysis_text = "Could not identify critical pages for analysis."
            return module

        # Request screenshots for each critical page (full page + hero element)
        for cp in critical_pages:
            self.request_screenshot(cp.url)
            # Request element-level screenshots for key areas
            self.request_screenshot(cp.url, selector="header, .hero, h1")
            self.request_screenshot(cp.url, selector=".cta, [class*='cta'], a[class*='button'], button[class*='primary']")

        # Build content for analysis
        pages_content = self._build_pages_content(critical_pages)

        if not self.llm.is_available():
            return self._fallback_analysis(module, critical_pages)

        try:
            result = await self.llm.analyze_with_prompt_async(
                "top5_pages",
                company_name=self.context.company_name,
                company_website=self.context.company_website,
                pages_content=pages_content,
                max_tokens=4000
            )

            # Process each page's grade
            page_grades = result.get("page_grades", {})

            for cp in critical_pages:
                page_key = cp.page_type
                if page_key in page_grades:
                    grade_data = page_grades[page_key]
                    cp.grade = grade_data.get("grade", "C")
                    cp.score = grade_data.get("score", 50)
                    cp.strengths = grade_data.get("strengths", [])
                    cp.weaknesses = grade_data.get("weaknesses", [])
                    cp.recommendations = grade_data.get("recommendations", [])

                # Store in context
                self.context.critical_pages.append(cp)

                # Add score item
                module.items.append(ScoreItem(
                    name=f"{cp.page_type.title()} Page",
                    description=f"Quality of {cp.page_type} page",
                    max_points=20,
                    actual_points=int(cp.score / 5),  # Convert 0-100 to 0-20
                    notes=f"Grade: {cp.grade} - {', '.join(cp.weaknesses[:2]) if cp.weaknesses else 'Good overall'}",
                    recommendation=cp.recommendations[0] if cp.recommendations else "",
                    page_url=cp.url,
                ))

            # Map page types to KPI impacts
            page_kpi_map = {
                'homepage': KPIImpact.BOUNCE_RATE,
                'product': KPIImpact.PIPELINE_VELOCITY,
                'solutions': KPIImpact.LEAD_CONVERSION,
                'pricing': KPIImpact.CLOSE_RATE,
                'about': KPIImpact.CUSTOMER_TRUST,
            }

            # Overall recommendations
            for rec in result.get("recommendations", []):
                impact_map = {"High": Impact.HIGH, "Medium": Impact.MEDIUM, "Low": Impact.LOW}
                effort_map = {"High": Effort.HIGH, "Medium": Effort.MEDIUM, "Low": Effort.LOW}

                # Try to determine which page this recommendation is for
                page_url = rec.get("page_url", "")
                page_type = rec.get("page_type", "").lower()
                kpi = page_kpi_map.get(page_type, KPIImpact.LEAD_CONVERSION)

                if not page_url and page_type:
                    # Find the URL for this page type
                    for cp in critical_pages:
                        if cp.page_type == page_type:
                            page_url = cp.url
                            break

                module.recommendations.append(Recommendation(
                    issue=rec.get("issue", ""),
                    recommendation=rec.get("recommendation", ""),
                    impact=impact_map.get(rec.get("impact", "Medium"), Impact.MEDIUM),
                    effort=effort_map.get(rec.get("effort", "Medium"), Effort.MEDIUM),
                    category="Critical Pages",
                    page_url=page_url,
                    kpi_impact=kpi
                ))

            module.analysis_text = result.get("overall_analysis", "")
            module.raw_data = {
                "pages_analyzed": [cp.page_type for cp in critical_pages],
                "page_grades": page_grades,
                "average_score": sum(cp.score for cp in critical_pages) / len(critical_pages) if critical_pages else 0
            }

        except Exception as e:
            print(f"  Error in top 5 pages analysis: {e}")
            return self._fallback_analysis(module, critical_pages)

        return module

    def _find_critical_pages(self) -> List[CriticalPage]:
        """Find the 5 critical pages from crawled content."""
        critical_pages = []
        base_url = self.context.company_website.rstrip('/')

        for page_type, patterns, display_name in self.CRITICAL_PAGE_TYPES:
            found_page = None

            # Try each pattern
            for pattern in patterns:
                if pattern == '':
                    # Homepage
                    for url in [base_url, f"{base_url}/"]:
                        if url in self.context.pages:
                            found_page = self.context.pages[url]
                            break
                else:
                    for url, page in self.context.pages.items():
                        if pattern in url.lower():
                            found_page = page
                            break

                if found_page:
                    break

            if found_page:
                critical_pages.append(CriticalPage(
                    page_type=page_type,
                    url=found_page.url
                ))

        return critical_pages

    def _build_pages_content(self, critical_pages: List[CriticalPage]) -> str:
        """Build content string for LLM analysis."""
        content_parts = []

        for cp in critical_pages:
            page = self.context.pages.get(cp.url)
            if page:
                content_parts.append(f"""
--- {cp.page_type.upper()} PAGE: {cp.url} ---
Title: {page.title}
Meta Description: {page.meta_description}
H1: {', '.join(page.h1_tags)}
H2: {', '.join(page.h2_tags[:6])}
CTAs: {', '.join([c.get('text', '') for c in page.ctas[:5]])}
Forms: {len(page.forms)} forms found
Images: {len(page.images)} images ({sum(1 for i in page.images if i.get('has_alt'))} with alt text)
Content:
{page.raw_text[:4000]}
""")

        return '\n'.join(content_parts)

    def _fallback_analysis(self, module: ModuleScore, critical_pages: List[CriticalPage]) -> ModuleScore:
        """Provide fallback analysis without LLM."""
        for cp in critical_pages:
            page = self.context.pages.get(cp.url)
            if page:
                # Basic heuristic scoring
                score = 50  # Base score

                # Has H1: +10
                if page.h1_tags:
                    score += 10
                # Has meta description: +10
                if page.meta_description and len(page.meta_description) > 50:
                    score += 10
                # Has CTAs: +10
                if page.ctas:
                    score += 10
                # Has reasonable content: +10
                if len(page.raw_text) > 500:
                    score += 10
                # Has images: +10
                if page.images:
                    score += 10

                cp.score = min(score, 100)
                cp.grade = self._score_to_grade(score)
                cp.strengths = []
                cp.weaknesses = ["Detailed analysis requires LLM"]

                self.context.critical_pages.append(cp)

                module.items.append(ScoreItem(
                    name=f"{cp.page_type.title()} Page",
                    description=f"Quality of {cp.page_type} page",
                    max_points=20,
                    actual_points=int(cp.score / 5),
                    notes=f"Grade: {cp.grade} (basic heuristic)"
                ))

        avg_score = sum(cp.score for cp in critical_pages) / len(critical_pages) if critical_pages else 0

        module.analysis_text = f"""
Analyzed {len(critical_pages)} critical pages using basic heuristics.

**Pages Found:**
{chr(10).join([f'- {cp.page_type.title()}: {cp.url} (Grade: {cp.grade})' for cp in critical_pages])}

**Average Score:** {avg_score:.0f}/100

For detailed page-by-page analysis with specific recommendations, LLM analysis is required.
"""

        module.raw_data = {
            "pages_analyzed": [cp.page_type for cp in critical_pages],
            "average_score": avg_score
        }

        return module

    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def self_audit(self) -> bool:
        """Validate critical pages analysis."""
        if not super().self_audit():
            return False

        # Should have analyzed at least 3 critical pages
        if len(self.context.critical_pages) < 3:
            return False

        return True
