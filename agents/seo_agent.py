"""SEO and Technical Analysis Agent."""

import re
from typing import List

from .base_agent import BaseAgent
from utils.scoring import ModuleScore, ScoreItem, Recommendation, Impact, Effort, KPIImpact


class SEOAgent(BaseAgent):
    """
    Analyzes SEO and technical health of the website.

    Evaluates:
    - Meta tags (title, description)
    - Heading structure (H1-H6)
    - Page speed
    - Mobile responsiveness
    - Image optimization
    - URL structure
    - Internal linking
    - Schema markup
    """

    agent_name = "seo"
    agent_description = "Analyzes SEO and technical health"
    dependencies = ["website"]
    weight = 1.0

    async def run(self) -> ModuleScore:
        """Execute SEO analysis asynchronously."""
        module = ModuleScore(name="SEO & Technical", weight=self.weight)

        pages = self.context.pages
        total_pages = len(pages)

        if total_pages == 0:
            module.analysis_text = "No pages could be analyzed."
            return module

        # Meta Tags Analysis
        pages_with_title = sum(1 for p in pages.values() if p.title and len(p.title) > 10)
        pages_with_desc = sum(1 for p in pages.values() if p.meta_description and len(p.meta_description) > 50)

        title_pct = (pages_with_title / total_pages) * 100
        desc_pct = (pages_with_desc / total_pages) * 100
        meta_score = int(((title_pct + desc_pct) / 200) * 15)

        meta_notes = []
        if title_pct < 100:
            meta_notes.append(f"{100-title_pct:.0f}% of pages missing proper titles")
        if desc_pct < 100:
            meta_notes.append(f"{100-desc_pct:.0f}% of pages missing meta descriptions")

        # Find a page missing meta for linking
        pages_missing_meta = [url for url, p in pages.items() if not p.meta_description or len(p.meta_description) < 50]

        module.items.append(ScoreItem(
            name="Meta Tags",
            description="Title and description optimization",
            max_points=15,
            actual_points=meta_score,
            notes="; ".join(meta_notes) if meta_notes else "Good meta tag coverage",
            recommendation="Add unique, keyword-rich meta descriptions (150-160 chars) to all pages missing them" if meta_score < 12 else "",
            page_url=pages_missing_meta[0] if pages_missing_meta else self.context.company_website,
        ))

        # Heading Structure Analysis
        pages_with_h1 = sum(1 for p in pages.values() if p.h1_tags)
        pages_with_single_h1 = sum(1 for p in pages.values() if len(p.h1_tags) == 1)
        pages_with_h2 = sum(1 for p in pages.values() if p.h2_tags)

        h1_pct = (pages_with_h1 / total_pages) * 100
        single_h1_pct = (pages_with_single_h1 / total_pages) * 100
        h2_pct = (pages_with_h2 / total_pages) * 100

        heading_score = int(((h1_pct * 0.5 + single_h1_pct * 0.3 + h2_pct * 0.2) / 100) * 10)

        heading_notes = []
        if h1_pct < 100:
            heading_notes.append(f"{100-h1_pct:.0f}% pages missing H1")
        if single_h1_pct < h1_pct:
            heading_notes.append("Some pages have multiple H1 tags")

        pages_missing_h1 = [url for url, p in pages.items() if not p.h1_tags]

        module.items.append(ScoreItem(
            name="Heading Structure",
            description="Proper H1-H6 hierarchy",
            max_points=10,
            actual_points=heading_score,
            notes="; ".join(heading_notes) if heading_notes else "Good heading structure",
            recommendation="Ensure every page has exactly one H1 tag that contains the primary keyword" if heading_score < 8 else "",
            page_url=pages_missing_h1[0] if pages_missing_h1 else self.context.company_website,
        ))

        # Page Speed Analysis
        load_times = [p.load_time for p in pages.values() if p.load_time > 0]
        avg_load_time = sum(load_times) / len(load_times) if load_times else 5.0

        if avg_load_time < 1.5:
            speed_score = 20
            speed_notes = f"Excellent avg load time: {avg_load_time:.2f}s"
        elif avg_load_time < 2.5:
            speed_score = 16
            speed_notes = f"Good avg load time: {avg_load_time:.2f}s"
        elif avg_load_time < 3.5:
            speed_score = 12
            speed_notes = f"Average load time: {avg_load_time:.2f}s - could improve"
        elif avg_load_time < 5.0:
            speed_score = 8
            speed_notes = f"Slow avg load time: {avg_load_time:.2f}s - needs optimization"
        else:
            speed_score = 4
            speed_notes = f"Very slow avg load time: {avg_load_time:.2f}s - critical issue"

        slowest_url = max(pages.items(), key=lambda x: x[1].load_time)[0] if pages else self.context.company_website

        module.items.append(ScoreItem(
            name="Page Speed",
            description="Load time under 3s",
            max_points=20,
            actual_points=speed_score,
            notes=speed_notes,
            recommendation="Optimize images, enable compression, leverage browser caching, and consider a CDN" if speed_score < 16 else "",
            page_url=slowest_url,
        ))

        # Mobile Responsiveness
        mobile_ready = sum(1 for p in pages.values() if 'viewport' in p.html.lower())
        mobile_pct = (mobile_ready / total_pages) * 100
        mobile_score = int((mobile_pct / 100) * 15)

        module.items.append(ScoreItem(
            name="Mobile Responsiveness",
            description="Mobile-friendly design indicators",
            max_points=15,
            actual_points=mobile_score,
            notes=f"{mobile_pct:.0f}% of pages have viewport meta tag",
            recommendation="Add viewport meta tag and ensure responsive design across all pages" if mobile_score < 12 else "",
            page_url=self.context.company_website,
        ))

        # Image Optimization
        total_images = sum(len(p.images) for p in pages.values())
        images_with_alt = sum(sum(1 for img in p.images if img.get('has_alt')) for p in pages.values())

        if total_images > 0:
            alt_pct = (images_with_alt / total_images) * 100
            img_score = int((alt_pct / 100) * 10)
            img_notes = f"{alt_pct:.0f}% of {total_images} images have alt text"
        else:
            img_score = 5
            img_notes = "No images found to analyze"

        module.items.append(ScoreItem(
            name="Image Optimization",
            description="Alt tags and optimization",
            max_points=10,
            actual_points=img_score,
            notes=img_notes,
            recommendation="Add descriptive alt text to all images for accessibility and SEO" if img_score < 8 else "",
            page_url=self.context.company_website,
        ))

        # URL Structure
        clean_urls = sum(1 for url in pages.keys()
                        if '?' not in url and not re.search(r'\d{5,}', url))
        url_pct = (clean_urls / total_pages) * 100
        url_score = int((url_pct / 100) * 10)

        module.items.append(ScoreItem(
            name="URL Structure",
            description="Clean, descriptive URLs",
            max_points=10,
            actual_points=url_score,
            notes=f"{url_pct:.0f}% clean URL structure",
            recommendation="Use descriptive, keyword-rich URL slugs and remove query parameters from indexable pages" if url_score < 8 else "",
            page_url=self.context.company_website,
        ))

        # Internal Linking
        avg_internal_links = sum(len(p.internal_links) for p in pages.values()) / total_pages

        if avg_internal_links >= 10:
            link_score = 10
            link_notes = f"Strong internal linking: avg {avg_internal_links:.1f} links/page"
        elif avg_internal_links >= 5:
            link_score = 7
            link_notes = f"Good internal linking: avg {avg_internal_links:.1f} links/page"
        else:
            link_score = 4
            link_notes = f"Weak internal linking: avg {avg_internal_links:.1f} links/page"

        module.items.append(ScoreItem(
            name="Internal Linking",
            description="Logical site structure",
            max_points=10,
            actual_points=link_score,
            notes=link_notes,
            recommendation="Add contextual internal links between related pages to improve crawlability and user navigation" if link_score < 8 else "",
            page_url=self.context.company_website,
        ))

        # Schema Markup
        pages_with_schema = sum(1 for p in pages.values() if p.has_schema)
        schema_pct = (pages_with_schema / total_pages) * 100

        if schema_pct >= 50:
            schema_score = 10
        elif schema_pct >= 25:
            schema_score = 7
        elif schema_pct > 0:
            schema_score = 4
        else:
            schema_score = 0

        schema_types = set()
        for p in pages.values():
            schema_types.update(p.schema_types)

        module.items.append(ScoreItem(
            name="Schema Markup",
            description="Structured data present",
            max_points=10,
            actual_points=schema_score,
            notes=f"{schema_pct:.0f}% pages with schema. Types: {', '.join(list(schema_types)[:5]) if schema_types else 'None'}",
            recommendation="Implement Organization, Product, and FAQ schema markup on key pages" if schema_score < 7 else "",
            page_url=self.context.company_website,
        ))

        # Generate recommendations
        recommendations = []

        # Find pages missing descriptions for linking
        pages_missing_desc = [url for url, p in pages.items()
                             if not p.meta_description or len(p.meta_description) < 50]

        if desc_pct < 80:
            recommendations.append(Recommendation(
                issue="Missing meta descriptions on multiple pages",
                recommendation="Add unique, compelling meta descriptions (150-160 chars) to all key pages",
                impact=Impact.HIGH,
                effort=Effort.LOW,
                page_url=pages_missing_desc[0] if pages_missing_desc else self.context.company_website,
                kpi_impact=KPIImpact.SEO_RANKING
            ))

        if avg_load_time > 3.0:
            # Find slowest page
            slowest_page = max(pages.items(), key=lambda x: x[1].load_time)[0]
            recommendations.append(Recommendation(
                issue=f"Slow page load times (avg {avg_load_time:.1f}s)",
                recommendation="Optimize images, enable compression, leverage browser caching, consider CDN",
                impact=Impact.HIGH,
                effort=Effort.MEDIUM,
                page_url=slowest_page,
                kpi_impact=KPIImpact.BOUNCE_RATE
            ))

        if total_images > 0 and alt_pct < 80:
            recommendations.append(Recommendation(
                issue=f"Missing alt text on {100-alt_pct:.0f}% of images",
                recommendation="Add descriptive alt text to all images for accessibility and SEO",
                impact=Impact.MEDIUM,
                effort=Effort.LOW,
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.SEO_RANKING
            ))

        if schema_pct < 25:
            recommendations.append(Recommendation(
                issue="Limited or no schema markup",
                recommendation="Implement Organization, Product, and FAQ schema on relevant pages",
                impact=Impact.MEDIUM,
                effort=Effort.MEDIUM,
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.SEO_RANKING
            ))

        if avg_internal_links < 5:
            recommendations.append(Recommendation(
                issue="Weak internal linking structure",
                recommendation="Add contextual internal links to improve site navigation and SEO",
                impact=Impact.MEDIUM,
                effort=Effort.LOW,
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.TIME_ON_SITE
            ))

        module.recommendations = recommendations[:5]

        # Analysis text
        module.analysis_text = f"""
The website was analyzed across {total_pages} pages for technical SEO health.

**Performance:** Average page load time is {avg_load_time:.2f} seconds. {'This is within acceptable range.' if avg_load_time < 3 else 'This needs improvement for better user experience and SEO.'}

**On-Page SEO:** {title_pct:.0f}% of pages have proper titles and {desc_pct:.0f}% have meta descriptions. {h1_pct:.0f}% have H1 tags with {single_h1_pct:.0f}% following the single-H1 best practice.

**Technical:** {mobile_pct:.0f}% of pages indicate mobile responsiveness. Internal linking averages {avg_internal_links:.1f} links per page. Schema markup is {'present' if schema_pct > 0 else 'not implemented'}.
"""

        # LLM-augmented strategic SEO recommendations
        if self.llm.is_available():
            try:
                heuristic_summary = (
                    f"Meta coverage: titles {title_pct:.0f}%, descriptions {desc_pct:.0f}%. "
                    f"H1 coverage: {h1_pct:.0f}%. Avg load time: {avg_load_time:.2f}s. "
                    f"Mobile ready: {mobile_pct:.0f}%. Schema: {schema_pct:.0f}%. "
                    f"Avg internal links: {avg_internal_links:.1f}. "
                    f"Image alt coverage: {alt_pct:.0f}% of {total_images} images. "
                    f"Schema types found: {', '.join(list(schema_types)[:5]) if schema_types else 'None'}."
                )

                seo_result = await self.llm.analyze_with_prompt_async(
                    "seo",
                    company_name=self.context.company_name,
                    company_website=self.context.company_website,
                    heuristic_summary=heuristic_summary,
                    max_tokens=2000
                )

                # Append LLM recommendations
                for rec in seo_result.get("prioritized_actions", []):
                    impact_map = {"High": Impact.HIGH, "Medium": Impact.MEDIUM, "Low": Impact.LOW}
                    effort_map = {"High": Effort.HIGH, "Medium": Effort.MEDIUM, "Low": Effort.LOW}

                    module.recommendations.append(Recommendation(
                        issue=rec.get("issue", ""),
                        recommendation=rec.get("recommendation", ""),
                        impact=impact_map.get(rec.get("impact", "Medium"), Impact.MEDIUM),
                        effort=effort_map.get(rec.get("effort", "Medium"), Effort.MEDIUM),
                        category="SEO & Technical",
                        page_url=self.context.company_website,
                        kpi_impact=KPIImpact.SEO_RANKING
                    ))

                # Augment analysis with strategic priorities
                strategic_text = seo_result.get("strategic_priorities", "")
                if strategic_text:
                    module.analysis_text += f"\n\n**Strategic SEO Priorities:**\n{strategic_text}"

            except Exception as e:
                print(f"  SEO LLM augmentation skipped: {e}")

        module.raw_data = {
            'total_pages': total_pages,
            'avg_load_time': avg_load_time,
            'meta_coverage': {'title': title_pct, 'description': desc_pct},
            'schema_types': list(schema_types)
        }

        return module

    def self_audit(self) -> bool:
        """Validate SEO analysis quality."""
        if not super().self_audit():
            return False

        score = self.analysis.module_score
        if not score:
            return False

        # Check that we analyzed a reasonable number of pages
        raw_data = score.raw_data
        if raw_data.get('total_pages', 0) < 3:
            return False

        return True
