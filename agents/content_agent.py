"""Content Quality Assessment Agent."""

from typing import List

from .base_agent import BaseAgent
from utils.scoring import ModuleScore, ScoreItem, Recommendation, Impact, Effort, KPIImpact


class ContentAgent(BaseAgent):
    """
    Analyzes content quality and effectiveness.

    Evaluates:
    - Content freshness
    - Depth and value
    - Readability
    - Visual support
    - Content variety
    - Thought leadership
    """

    agent_name = "content"
    agent_description = "Analyzes content quality and effectiveness"
    dependencies = ["website"]
    weight = 1.0

    async def run(self) -> ModuleScore:
        """Execute content analysis asynchronously."""
        module = ModuleScore(name="Content Quality", weight=self.weight)

        # Detect content types
        has_blog = False
        has_resources = False
        has_case_studies = False
        content_samples = []

        for url, page in self.context.pages.items():
            url_lower = url.lower()

            if '/blog' in url_lower or '/posts' in url_lower:
                has_blog = True
            if '/resource' in url_lower or '/guide' in url_lower or '/ebook' in url_lower:
                has_resources = True
            if '/case-stud' in url_lower or '/customer' in url_lower or '/success' in url_lower:
                has_case_studies = True

            content_samples.append(f"""
--- PAGE: {url} ---
Title: {page.title}
Headings: {', '.join(page.h1_tags + page.h2_tags[:3])}
Content Preview: {page.raw_text[:2500]}
Images: {len(page.images)} images
""")

        page_content = '\n'.join(content_samples)[:15000]

        if not self.llm.is_available():
            return self._fallback_analysis(module, has_blog, has_resources, has_case_studies)

        try:
            result = await self.llm.analyze_with_prompt_async(
                "content",
                company_name=self.context.company_name,
                company_website=self.context.company_website,
                page_content=page_content,
                max_tokens=4000
            )

            # Build score items
            score_mapping = {
                "content_freshness": ("Content Freshness", 15),
                "depth_value": ("Depth & Value", 20),
                "readability": ("Readability", 15),
                "visual_support": ("Visual Support", 15),
                "content_variety": ("Content Variety", 15),
                "thought_leadership": ("Thought Leadership", 20),
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

                # Find relevant content page for linking
                page_url = self.context.company_website
                for url in self.context.pages.keys():
                    if '/blog' in url.lower() or '/resource' in url.lower():
                        page_url = url
                        break

                module.recommendations.append(Recommendation(
                    issue=rec.get("issue", ""),
                    recommendation=rec.get("recommendation", ""),
                    impact=impact_map.get(rec.get("impact", "Medium"), Impact.MEDIUM),
                    effort=effort_map.get(rec.get("effort", "Medium"), Effort.MEDIUM),
                    category="Content Quality",
                    page_url=page_url,
                    kpi_impact=KPIImpact.WEBSITE_TRAFFIC
                ))

            module.analysis_text = result.get("analysis", "")
            module.raw_data = {
                "strengths": result.get("strengths", []),
                "weaknesses": result.get("weaknesses", []),
                "has_blog": has_blog,
                "has_resources": has_resources,
                "has_case_studies": has_case_studies
            }

        except Exception as e:
            print(f"  Error in content analysis: {e}")
            return self._fallback_analysis(module, has_blog, has_resources, has_case_studies)

        return module

    def _fallback_analysis(self, module: ModuleScore, has_blog: bool, has_resources: bool, has_case_studies: bool) -> ModuleScore:
        """Provide fallback scores based on basic detection."""
        variety_score = 5
        if has_blog:
            variety_score += 4
        if has_resources:
            variety_score += 3
        if has_case_studies:
            variety_score += 3

        module.items = [
            ScoreItem("Content Freshness", "Recent updates present", 15, 7, "Manual review recommended"),
            ScoreItem("Depth & Value", "Substantive content", 20, 10, "Manual review recommended"),
            ScoreItem("Readability", "Scannable, clear content", 15, 7, "Manual review recommended"),
            ScoreItem("Visual Support", "Images enhance content", 15, 7, "Manual review recommended"),
            ScoreItem("Content Variety", "Blog, case studies, resources", 15, variety_score,
                     f"Blog: {'Yes' if has_blog else 'No'}, Resources: {'Yes' if has_resources else 'No'}, Case Studies: {'Yes' if has_case_studies else 'No'}"),
            ScoreItem("Thought Leadership", "Original insights", 20, 10, "Manual review recommended"),
        ]
        module.recommendations = [
            Recommendation(
                issue="Content depth not verified",
                recommendation="Add long-form content (1500+ words) on core product use cases with specific examples, data, and actionable takeaways",
                impact=Impact.HIGH,
                effort=Effort.HIGH,
                category="Content Quality",
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.WEBSITE_TRAFFIC
            ),
            Recommendation(
                issue="Thought leadership not assessed",
                recommendation="Publish original research or proprietary data insights quarterly to establish subject matter authority",
                impact=Impact.HIGH,
                effort=Effort.HIGH,
                category="Content Quality",
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.BRAND_AWARENESS
            ),
        ]
        if not has_case_studies:
            module.recommendations.append(Recommendation(
                issue="No case studies detected",
                recommendation="Create 2-3 customer case studies with measurable results (e.g., '40% reduction in X') to support bottom-of-funnel conversion",
                impact=Impact.HIGH,
                effort=Effort.MEDIUM,
                category="Content Quality",
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.CLOSE_RATE
            ))
        module.analysis_text = f"Basic content inventory: Blog present: {has_blog}, Resources section: {has_resources}, Case studies: {has_case_studies}"
        module.raw_data = {
            "has_blog": has_blog,
            "has_resources": has_resources,
            "has_case_studies": has_case_studies
        }
        return module

    def self_audit(self) -> bool:
        """Validate content analysis quality."""
        return super().self_audit()
