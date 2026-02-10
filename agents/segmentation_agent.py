"""Segmentation Analysis Agent."""

from typing import List, Dict

from .base_agent import BaseAgent
from orchestrator.context_store import SegmentInfo
from utils.scoring import ModuleScore, ScoreItem, Recommendation, Impact, Effort, KPIImpact


class SegmentationAgent(BaseAgent):
    """
    Analyzes target industry/segment coverage.

    Evaluates:
    - Identified target segments
    - Pain point coverage per segment
    - Segment-specific messaging
    - Industry page quality
    - Use case articulation
    """

    agent_name = "segmentation"
    agent_description = "Analyzes target industry/segment coverage"
    dependencies = ["website"]
    weight = 1.0

    async def run(self) -> ModuleScore:
        """Execute segmentation analysis asynchronously."""
        module = ModuleScore(name="Segmentation Analysis", weight=self.weight)

        # Gather segment data from crawled pages
        segment_pages = list(self.context.get_pages_by_type('segment'))
        all_segments = set()

        # Also include solutions pages and pages with identified segments
        for page in self.context.pages.values():
            all_segments.update(page.identified_segments)
            if page not in segment_pages:
                if hasattr(page, 'page_type') and page.page_type == 'solutions':
                    segment_pages.append(page)
                elif page.identified_segments:
                    segment_pages.append(page)

        # Always include homepage + about page content for ICP inference
        home_url = self.context.company_website.rstrip('/')
        for url, page in self.context.pages.items():
            if page not in segment_pages:
                if url.rstrip('/') == home_url or '/about' in url.lower():
                    segment_pages.append(page)

        # Build content for analysis
        segment_content = self._build_segment_content(segment_pages)

        if not self.llm.is_available():
            return self._fallback_analysis(module, list(all_segments), len(segment_pages))

        try:
            result = await self.llm.analyze_with_prompt_async(
                "segmentation",
                company_name=self.context.company_name,
                company_website=self.context.company_website,
                industry=self.context.industry,
                segment_pages=segment_content,
                detected_segments=', '.join(all_segments) if all_segments else 'None detected',
                max_tokens=4000
            )

            # Build score items
            score_mapping = {
                "segment_clarity": ("Segment Clarity", 20),
                "pain_point_coverage": ("Pain Point Coverage", 25),
                "segment_messaging": ("Segment-Specific Messaging", 20),
                "industry_pages": ("Industry Page Quality", 20),
                "use_case_articulation": ("Use Case Articulation", 15),
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

            # Store identified segments in context
            for seg_data in result.get("identified_segments", []):
                segment = SegmentInfo(
                    name=seg_data.get("name", ""),
                    description=seg_data.get("description", ""),
                    pain_points=seg_data.get("pain_points", []),
                    coverage_score=seg_data.get("coverage_score", 0),
                    pages_addressing=seg_data.get("pages_addressing", []),
                    recommendations=seg_data.get("recommendations", [])
                )
                self.context.identified_segments.append(segment)
            
            # Extract and store primary segment
            primary = result.get("primary_segment", {})
            if primary:
                self.context.primary_segment = primary.get("name", "")
                self.context.primary_segment_justification = primary.get("justification", "")
                self.context.primary_segment_priority = primary.get("priority", "Medium")
            
            # Build recommendations
            for rec in result.get("recommendations", []):
                impact_map = {"High": Impact.HIGH, "Medium": Impact.MEDIUM, "Low": Impact.LOW}
                effort_map = {"High": Effort.HIGH, "Medium": Effort.MEDIUM, "Low": Effort.LOW}

                # Find relevant segment/solutions page for linking
                page_url = self.context.company_website
                for url in self.context.pages.keys():
                    if '/solutions' in url.lower() or '/industries' in url.lower() or '/use-cases' in url.lower():
                        page_url = url
                        break

                module.recommendations.append(Recommendation(
                    issue=rec.get("issue", ""),
                    recommendation=rec.get("recommendation", ""),
                    impact=impact_map.get(rec.get("impact", "Medium"), Impact.MEDIUM),
                    effort=effort_map.get(rec.get("effort", "Medium"), Effort.MEDIUM),
                    category="Segmentation",
                    page_url=page_url,
                    kpi_impact=KPIImpact.PIPELINE_VELOCITY
                ))

            module.analysis_text = result.get("analysis", "")
            module.raw_data = {
                "segments_found": list(all_segments),
                "segment_pages_count": len(segment_pages),
                "identified_segments": result.get("identified_segments", []),
                "primary_segment": result.get("primary_segment", {}),
                "analysis": result.get("analysis", ""),
                "gaps": result.get("gaps", [])
            }

        except Exception as e:
            print(f"  Error in segmentation analysis: {e}")
            return self._fallback_analysis(module, list(all_segments), len(segment_pages))

        return module

    def _build_segment_content(self, segment_pages: List) -> str:
        """Build content string from segment pages."""
        content_parts = []

        # Include segment pages
        for page in segment_pages[:5]:
            content_parts.append(f"""
--- SEGMENT PAGE: {page.url} ---
Title: {page.title}
H1: {', '.join(page.h1_tags)}
H2: {', '.join(page.h2_tags[:5])}
Content: {page.raw_text[:3000]}
Detected Segments: {', '.join(page.identified_segments)}
""")

        # Also include solutions/products pages that might have segment info
        for page in self.context.pages.values():
            if page.page_type in ['solutions', 'product'] and page not in segment_pages:
                content_parts.append(f"""
--- {page.page_type.upper()} PAGE: {page.url} ---
Title: {page.title}
H1: {', '.join(page.h1_tags)}
Content Preview: {page.raw_text[:1500]}
Detected Segments: {', '.join(page.identified_segments)}
""")
                if len(content_parts) > 8:
                    break

        # If no specific segment pages found OR content is sparse, add priority pages (Home, About)
        if not segment_pages or len('\n'.join(content_parts)) < 6000:
            priority_content = self.get_priority_pages_content()
            if priority_content:
                content_parts.append("\n--- PRIORITY PAGES (For Segment Inference) ---\n" + priority_content)

        return '\n'.join(content_parts)[:15000]

    def _fallback_analysis(self, module: ModuleScore, segments: List[str], segment_page_count: int) -> ModuleScore:
        """Provide fallback analysis."""
        # Score based on what we detected
        clarity_score = min(len(segments) * 3, 15)
        page_score = min(segment_page_count * 5, 15)

        module.items = [
            ScoreItem("Segment Clarity", "Clear target segment identification", 20, clarity_score,
                     f"Detected {len(segments)} segments: {', '.join(segments[:5])}"),
            ScoreItem("Pain Point Coverage", "Segment pain points addressed", 25, 12,
                     "Manual review recommended"),
            ScoreItem("Segment-Specific Messaging", "Tailored messaging per segment", 20, 10,
                     "Manual review recommended"),
            ScoreItem("Industry Page Quality", "Dedicated industry/segment pages", 20, page_score,
                     f"Found {segment_page_count} segment-specific pages"),
            ScoreItem("Use Case Articulation", "Clear use case documentation", 15, 7,
                     "Manual review recommended"),
        ]

        module.analysis_text = f"""
Basic segmentation analysis completed.

**Segments Detected:** {', '.join(segments) if segments else 'None explicitly identified'}
**Segment Pages Found:** {segment_page_count}

For detailed analysis of pain point coverage and messaging effectiveness, LLM analysis is required.
"""

        module.recommendations = [
            Recommendation(
                issue="Segment targeting not assessed",
                recommendation="Create dedicated landing pages for each primary target segment with industry-specific language, pain points, and case studies",
                impact=Impact.HIGH,
                effort=Effort.HIGH,
                category="Segmentation",
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.PIPELINE_VELOCITY
            ),
            Recommendation(
                issue="Segment self-identification unclear",
                recommendation="Add an 'Industries' or 'Solutions by Role' section to the main navigation so visitors can self-select into their segment",
                impact=Impact.HIGH,
                effort=Effort.MEDIUM,
                category="Segmentation",
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.LEAD_CONVERSION
            ),
        ]
        module.raw_data = {
            "segments_found": segments,
            "segment_pages_count": segment_page_count,
            "primary_segment": {
                "name": segments[0] if segments else "None identified",
                "justification": "Fallback analysis justification (LLM unavailable)",
                "priority": "Medium"
            }
        }
        
        # Also store in context for template
        if segments:
            self.context.primary_segment = segments[0]
            self.context.primary_segment_justification = "Fallback analysis justification (LLM unavailable)"
            self.context.primary_segment_priority = "Medium"

        return module

    def self_audit(self) -> bool:
        """Validate segmentation analysis quality."""
        if not super().self_audit():
            return False

        # Should have some segment data
        score = self.analysis.module_score
        if score and score.raw_data:
            # Having no segments might be valid, but flag for review
            pass

        return True
