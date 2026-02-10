"""Resource Hub Analysis Agent."""

from typing import List, Dict

from .base_agent import BaseAgent
from utils.scoring import ModuleScore, ScoreItem, Recommendation, Impact, Effort, KPIImpact


class ResourceHubAgent(BaseAgent):
    """
    Analyzes landing pages, gated content, and resource hubs.

    Evaluates:
    - Landing page quality
    - Gated content strategy
    - Form optimization
    - Content offer variety
    - Lead magnet effectiveness
    """

    agent_name = "resource_hub"
    agent_description = "Analyzes landing pages and resource hubs"
    dependencies = ["website", "conversion"]
    weight = 1.0

    async def run(self) -> ModuleScore:
        """Execute resource hub analysis asynchronously."""
        module = ModuleScore(name="Resource Hub Analysis", weight=self.weight)

        # Find resource-related pages
        resource_pages = []
        landing_pages = []
        gated_content = []

        for url, page in self.context.pages.items():
            url_lower = url.lower()

            # Resource pages
            if any(x in url_lower for x in ['/resource', '/guide', '/ebook', '/whitepaper', '/webinar', '/template']):
                resource_pages.append(page)

                # Check if gated (has form)
                if page.forms:
                    gated_content.append({
                        'url': url,
                        'title': page.title,
                        'form_fields': page.forms[0].get('field_count', 0) if page.forms else 0
                    })
            
            # Blog pages (as backup for resources)
            if '/blog' in url_lower:
                # We'll treat blogs as potential resources if we don't find formal ones
                pass

            # Landing pages (typically have form + limited navigation)
            if any(x in url_lower for x in ['/lp/', '/landing', '/offer', '/download']):
                landing_pages.append(page)

        # Store in context
        self.context.landing_pages = [{'url': p.url, 'title': p.title} for p in landing_pages]
        self.context.gated_content = gated_content
        
        # If no dedicated resource pages found, use blogs
        if not resource_pages:
             blog_pages = [p for u, p in self.context.pages.items() if '/blog' in u.lower()]
             if blog_pages:
                 resource_pages.extend(blog_pages[:5])

        # Build content for analysis
        resource_content = self._build_resource_content(resource_pages, landing_pages)

        if not self.llm.is_available():
            return self._fallback_analysis(module, resource_pages, landing_pages, gated_content)

        try:
            result = await self.llm.analyze_with_prompt_async(
                "resource_hub",
                company_name=self.context.company_name,
                company_website=self.context.company_website,
                resource_content=resource_content,
                gated_content_count=len(gated_content),
                landing_page_count=len(landing_pages),
                max_tokens=4000
            )

            # Build score items
            score_mapping = {
                "landing_page_quality": ("Landing Page Quality", 25),
                "gated_content_strategy": ("Gated Content Strategy", 20),
                "form_optimization": ("Form Optimization", 20),
                "content_offer_variety": ("Content Offer Variety", 20),
                "lead_magnet_effectiveness": ("Lead Magnet Effectiveness", 15),
            }

            for key, (name, max_pts) in score_mapping.items():
                if key in result.get("scores", {}):
                    score_data = result["scores"][key]
                    module.items.append(ScoreItem(
                        name=name,
                        description=f"Evaluates {name.lower()}",
                        max_points=max_pts,
                        actual_points=min(score_data.get("score", 0), max_pts),
                        notes=score_data.get("notes", ""),
                        recommendation=score_data.get("recommendation", ""),
                        business_impact=score_data.get("business_impact", ""),
                        page_url=score_data.get("page_url", ""),
                    ))

            # Build recommendations
            for rec in result.get("recommendations", []):
                impact_map = {"High": Impact.HIGH, "Medium": Impact.MEDIUM, "Low": Impact.LOW}
                effort_map = {"High": Effort.HIGH, "Medium": Effort.MEDIUM, "Low": Effort.LOW}

                # Link to first resource or landing page
                page_url = ""
                if landing_pages:
                    page_url = landing_pages[0].url
                elif resource_pages:
                    page_url = resource_pages[0].url
                else:
                    page_url = self.context.company_website

                module.recommendations.append(Recommendation(
                    issue=rec.get("issue", ""),
                    recommendation=rec.get("recommendation", ""),
                    impact=impact_map.get(rec.get("impact", "Medium"), Impact.MEDIUM),
                    effort=effort_map.get(rec.get("effort", "Medium"), Effort.MEDIUM),
                    category="Resource Hub",
                    page_url=page_url,
                    kpi_impact=KPIImpact.LEAD_CONVERSION
                ))

            module.analysis_text = result.get("analysis", "")
            module.raw_data = {
                "resource_pages": len(resource_pages),
                "landing_pages": len(landing_pages),
                "gated_content": len(gated_content),
                "content_types": result.get("content_types", []),
                "funnel_stages_covered": result.get("funnel_stages", [])
            }

        except Exception as e:
            print(f"  Error in resource hub analysis: {e}")
            return self._fallback_analysis(module, resource_pages, landing_pages, gated_content)

        return module

    def _build_resource_content(self, resource_pages: List, landing_pages: List) -> str:
        """Build content string from resource pages."""
        content_parts = []

        # Resource pages
        for page in resource_pages[:5]:
            form_info = ""
            if page.forms:
                form = page.forms[0]
                form_info = f"\nForm: {form.get('field_count', 0)} fields - {', '.join(form.get('fields', [])[:5])}"

            content_parts.append(f"""
--- RESOURCE PAGE: {page.url} ---
Title: {page.title}
H1: {', '.join(page.h1_tags)}
CTAs: {', '.join([c.get('text', '') for c in page.ctas[:3]])}{form_info}
Content: {page.raw_text[:2000]}
""")

        # Landing pages
        for page in landing_pages[:3]:
            form_info = ""
            if page.forms:
                form = page.forms[0]
                form_info = f"\nForm: {form.get('field_count', 0)} fields - {', '.join(form.get('fields', [])[:5])}"

            content_parts.append(f"""
--- LANDING PAGE: {page.url} ---
Title: {page.title}
H1: {', '.join(page.h1_tags)}
CTAs: {', '.join([c.get('text', '') for c in page.ctas[:3]])}{form_info}
Content: {page.raw_text[:1500]}
""")

        return '\n'.join(content_parts)[:12000]

    def _fallback_analysis(self, module: ModuleScore, resource_pages: List, landing_pages: List, gated_content: List) -> ModuleScore:
        """Provide fallback analysis."""
        # Score based on what we found
        resource_score = min(len(resource_pages) * 4, 20)
        landing_score = min(len(landing_pages) * 5, 20)
        gated_score = min(len(gated_content) * 4, 15)

        module.items = [
            ScoreItem("Landing Page Quality", "Dedicated landing pages", 25, landing_score,
                     f"Found {len(landing_pages)} landing pages"),
            ScoreItem("Gated Content Strategy", "Content behind forms", 20, gated_score,
                     f"Found {len(gated_content)} gated resources"),
            ScoreItem("Form Optimization", "Form length and design", 20, 10,
                     "Manual review recommended"),
            ScoreItem("Content Offer Variety", "Different content types", 20, resource_score,
                     f"Found {len(resource_pages)} resource pages"),
            ScoreItem("Lead Magnet Effectiveness", "Value of gated content", 15, 7,
                     "Manual review recommended"),
        ]

        has_resources = len(resource_pages) > 0
        has_landing = len(landing_pages) > 0
        has_gated = len(gated_content) > 0

        module.analysis_text = f"""
Resource hub analysis completed.

**Summary:**
- Resource pages found: {len(resource_pages)}
- Landing pages found: {len(landing_pages)}
- Gated content items: {len(gated_content)}

**Assessment:**
{'✓ Has resource content' if has_resources else '✗ No dedicated resource pages found'}
{'✓ Has landing pages' if has_landing else '✗ No landing pages detected'}
{'✓ Uses gated content' if has_gated else '✗ No gated content strategy detected'}
"""

        module.recommendations = [
            Recommendation(
                issue="Resource hub structure not assessed",
                recommendation="Create a centralized '/resources' page organized by content type (eBooks, webinars, case studies) and buyer stage (awareness, consideration, decision)",
                impact=Impact.HIGH,
                effort=Effort.MEDIUM,
                category="Resource Hub",
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.LEAD_CONVERSION
            ),
            Recommendation(
                issue="Lead magnet strategy not assessed",
                recommendation="Develop a high-value BOFU asset (ROI calculator, assessment tool, or benchmark report) to capture high-intent leads",
                impact=Impact.HIGH,
                effort=Effort.HIGH,
                category="Resource Hub",
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.PIPELINE_VELOCITY
            ),
        ]
        module.raw_data = {
            "resource_pages": len(resource_pages),
            "landing_pages": len(landing_pages),
            "gated_content": len(gated_content)
        }

        return module

    def self_audit(self) -> bool:
        """Validate resource hub analysis quality."""
        return super().self_audit()
