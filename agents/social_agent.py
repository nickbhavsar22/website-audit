"""Social Media Audit Agent."""

import requests
import asyncio
from typing import Dict, Optional

from .base_agent import BaseAgent
from utils.scoring import ModuleScore, ScoreItem, Recommendation, Impact, Effort, KPIImpact


class SocialAgent(BaseAgent):
    """
    Analyzes social media presence and effectiveness.

    Evaluates:
    - Social presence (accounts exist)
    - Posting frequency
    - Engagement rate
    - Content mix
    - Brand consistency
    - Best practices
    """

    agent_name = "social"
    agent_description = "Analyzes social media presence and effectiveness"
    dependencies = ["website"]
    weight = 1.0

    async def run(self) -> ModuleScore:
        """Execute social media analysis asynchronously."""
        module = ModuleScore(name="Social Media", weight=self.weight)

        # Collect social links from all pages
        social_links = {}
        for page in self.context.pages.values():
            for platform, url in page.social_links.items():
                if platform not in social_links:
                    social_links[platform] = url

        # Store in context for other uses
        self.context.social_links = social_links

        if not social_links:
            return self._no_social_presence(module)

        # Try to gather some public data about social presence
        social_data = {}
        for platform, url in social_links.items():
            social_data[platform] = {
                'url': url,
                'content': await asyncio.to_thread(self._fetch_social_page, url)
            }

        if not self.llm.is_available():
            return self._fallback_analysis(module, social_links)

        # Prepare content for LLM
        social_content = f"""
## Social Media Profiles Found

Company: {self.context.company_name}
Website: {self.context.company_website}

### Platforms Detected:
"""

        for platform, data in social_data.items():
            social_content += f"\n**{platform.title()}**: {data['url']}\n"
            if data['content']:
                social_content += f"Page content sample available\n"
            else:
                social_content += f"(Profile URL found, detailed analysis requires manual review or API access)\n"

        social_content += """
### Analysis Request:
Based on the social profiles found, provide an assessment. Note that detailed engagement metrics
require API access or manual review. Focus on:
- Presence and profile completeness (based on URLs found)
- Platform selection appropriateness for B2B SaaS
- Recommendations for improvement

Platforms NOT found should be noted but scored as 0 for that platform.
"""

        try:
            result = await self.llm.analyze_with_prompt_async(
                "social",
                company_name=self.context.company_name,
                company_website=self.context.company_website,
                social_content=social_content
            )

            # Calculate aggregate scores across platforms
            platform_scores = result.get("platforms", {})

            criteria = {
                "presence": ("Social Presence", 10),
                "posting_frequency": ("Posting Frequency", 15),
                "engagement_rate": ("Engagement Rate", 25),
                "content_mix": ("Content Mix", 15),
                "brand_consistency": ("Brand Consistency", 15),
                "best_practices": ("Best Practices", 20),
            }

            for criterion_key, (criterion_name, max_pts) in criteria.items():
                total_score = 0
                total_max = 0
                notes_parts = []
                rec_parts = []

                for platform, data in platform_scores.items():
                    if data.get("found", False) and "scores" in data:
                        scores = data["scores"]
                        if criterion_key in scores:
                            total_score += scores[criterion_key].get("score", 0)
                            total_max += scores[criterion_key].get("max", max_pts)
                            if scores[criterion_key].get("notes"):
                                notes_parts.append(f"{platform}: {scores[criterion_key]['notes']}")
                            if scores[criterion_key].get("recommendation"):
                                rec_parts.append(f"{platform}: {scores[criterion_key]['recommendation']}")

                if total_max > 0:
                    normalized_score = int((total_score / total_max) * max_pts)
                else:
                    normalized_score = max_pts // 2

                module.items.append(ScoreItem(
                    name=criterion_name,
                    description=f"Evaluates {criterion_name.lower()} across platforms",
                    max_points=max_pts,
                    actual_points=min(normalized_score, max_pts),
                    notes="; ".join(notes_parts[:2]) if notes_parts else "Limited data available",
                    recommendation="; ".join(rec_parts[:2]) if rec_parts else "",
                    page_url=self.context.company_website,
                ))

            # Build recommendations
            for rec in result.get("recommendations", []):
                impact_map = {"High": Impact.HIGH, "Medium": Impact.MEDIUM, "Low": Impact.LOW}
                effort_map = {"High": Effort.HIGH, "Medium": Effort.MEDIUM, "Low": Effort.LOW}

                # Try to link to relevant social platform URL
                page_url = ""
                platform = rec.get("platform", "").lower()
                if platform and platform in social_links:
                    page_url = social_links[platform]
                elif social_links:
                    page_url = list(social_links.values())[0]
                if not page_url:
                    page_url = self.context.company_website

                module.recommendations.append(Recommendation(
                    issue=rec.get("issue", ""),
                    recommendation=rec.get("recommendation", ""),
                    impact=impact_map.get(rec.get("impact", "Medium"), Impact.MEDIUM),
                    effort=effort_map.get(rec.get("effort", "Medium"), Effort.MEDIUM),
                    category="Social Media",
                    page_url=page_url,
                    kpi_impact=KPIImpact.BRAND_AWARENESS
                ))

            module.analysis_text = result.get("overall_analysis", "")
            module.raw_data = {
                "platforms_found": list(social_links.keys()),
                "platform_urls": social_links,
                "strengths": result.get("strengths", []),
                "weaknesses": result.get("weaknesses", [])
            }

        except Exception as e:
            print(f"  Error in social analysis: {e}")
            return self._fallback_analysis(module, social_links)

        return module

    def _fetch_social_page(self, url: str) -> Optional[str]:
        """Attempt to fetch a social media page (limited by auth requirements)."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.text[:5000]
        except:
            pass
        return None

    def _no_social_presence(self, module: ModuleScore) -> ModuleScore:
        """Handle case where no social links are found."""
        module.items = [
            ScoreItem("Social Presence", "Active accounts exist", 100, 0,
                     "No social media links found on website")
        ]
        module.recommendations = [
            Recommendation(
                issue="No social media links found on website",
                recommendation="Add social media links to website footer/header and create profiles on LinkedIn, Twitter/X at minimum",
                impact=Impact.HIGH,
                effort=Effort.MEDIUM,
                category="Social Media"
            )
        ]
        module.analysis_text = "No social media presence was detected from the website. Social links were not found in the header, footer, or content areas."
        module.raw_data = {"platforms_found": []}
        return module

    def _fallback_analysis(self, module: ModuleScore, social_links: Dict) -> ModuleScore:
        """Provide fallback scores."""
        platforms_found = list(social_links.keys())
        presence_score = min(len(platforms_found) * 2, 10)

        module.items = [
            ScoreItem("Social Presence", "Active accounts exist", 10, presence_score,
                     f"Found: {', '.join(platforms_found)}"),
            ScoreItem("Posting Frequency", "Consistent posting", 15, 7,
                     "Manual review required - API access needed for metrics"),
            ScoreItem("Engagement Rate", "Engagement relative to followers", 25, 12,
                     "Manual review required - API access needed for metrics"),
            ScoreItem("Content Mix", "Content variety", 15, 7,
                     "Manual review required"),
            ScoreItem("Brand Consistency", "Visual/messaging alignment", 15, 7,
                     "Manual review required"),
            ScoreItem("Best Practices", "Platform optimization", 20, 10,
                     "Manual review required"),
        ]
        module.analysis_text = f"""
Social media profiles detected: {', '.join(platforms_found) if platforms_found else 'None'}

**Note:** Detailed social media metrics (engagement rates, posting frequency, etc.) require either:
1. API access to each platform
2. Manual review of the profiles

The scores above are estimates based on presence detection only. For a complete social media audit,
manual review of the last 15-20 posts on each platform is recommended.
"""
        module.recommendations = [
            Recommendation(
                issue="Social engagement strategy not assessed",
                recommendation="Shift from broadcasting (link drops) to engagement — reply to comments, ask questions, and share employee thought leadership on LinkedIn",
                impact=Impact.MEDIUM,
                effort=Effort.LOW,
                category="Social Media",
                page_url=social_links.get('linkedin', self.context.company_website),
                kpi_impact=KPIImpact.BRAND_AWARENESS
            ),
            Recommendation(
                issue="Content sharing not assessed",
                recommendation="Add social sharing buttons to blog posts and resource pages to amplify content distribution",
                impact=Impact.MEDIUM,
                effort=Effort.LOW,
                category="Social Media",
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.WEBSITE_TRAFFIC
            ),
        ]
        module.raw_data = {
            "platforms_found": platforms_found,
            "platform_urls": social_links
        }
        return module

    def self_audit(self) -> bool:
        """Validate social analysis quality."""
        return super().self_audit()
