"""Conversion Path Analysis Agent."""

import json
from typing import List

from .base_agent import BaseAgent
from utils.scoring import ModuleScore, ScoreItem, Recommendation, Impact, Effort, KPIImpact


class ConversionAgent(BaseAgent):
    """
    Analyzes conversion paths and CTA effectiveness.

    Evaluates:
    - CTA visibility
    - CTA copy quality
    - Form optimization
    - Trust signals near conversion
    - Path clarity
    - Multiple entry points
    - Friction reduction
    """

    agent_name = "conversion"
    agent_description = "Analyzes conversion paths and CTA effectiveness"
    dependencies = ["website"]
    weight = 1.0

    def _generate_cot_plan(self) -> str:
        """Generate Chain of Thought plan."""
        return f"""
        Plan for Conversion Analysis of {self.context.company_name}:
        1. Identify key conversion points (Demo, Trial, Contact).
        2. Evaluate CTA copy using 'Click-to-Value' framework (Benefit vs. Action).
        3. Audit forms for friction (Fields count vs. Value offered).
        4. Check for 'Point of Anxiety' trust signals near submit buttons.
        5. Calculate potential 'Opportunity Cost' of observed friction.
        """

    async def run(self) -> ModuleScore:
        """Execute conversion analysis asynchronously."""
        module = ModuleScore(name="Conversion Paths", weight=self.weight)

        # Aggregate CTAs and forms from all pages
        all_ctas = self.context.get_all_ctas()
        all_forms = self.context.get_all_forms()

        # Get content from key conversion pages
        key_content = []
        for url, page in self.context.pages.items():
            url_lower = url.lower()
            if any(x in url_lower for x in ['pricing', 'demo', 'contact', 'trial', 'signup', 'get-started']):
                key_content.append(f"--- {url} ---\n{page.raw_text[:2000]}")

        if not self.llm.is_available():
            return self._fallback_analysis(module, all_ctas, all_forms)

        # Prepare data for LLM
        ctas_summary = json.dumps(all_ctas[:30], indent=2)
        forms_summary = json.dumps(all_forms[:10], indent=2)
        page_content = '\n'.join(key_content)[:10000]

        try:
            result = await self.llm.analyze_with_prompt_async(
                "conversion",
                company_name=self.context.company_name,
                company_website=self.context.company_website,
                ctas=ctas_summary,
                forms=forms_summary,
                page_content=page_content,
                max_tokens=4000
            )

            # Build score items
            score_mapping = {
                "cta_visibility": ("CTA Visibility", 20),
                "cta_copy": ("CTA Copy", 15),
                "form_optimization": ("Form Optimization", 15),
                "trust_signals": ("Trust Signals Near Conversion", 15),
                "path_clarity": ("Path Clarity", 15),
                "multiple_entry_points": ("Multiple Entry Points", 10),
                "friction_reduction": ("Friction Reduction", 10),
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

            # Store Framework Data
            module.raw_data = {
                "cta_inventory": result.get("cta_inventory", []),
                "strengths": result.get("strengths", []),
                "weaknesses": result.get("weaknesses", []),
                "total_ctas": len(all_ctas),
                "total_forms": len(all_forms),
                "opportunity_cost": result.get("opportunity_cost", {})
            }

            # Build recommendations
            for rec in result.get("recommendations", []):
                impact_map = {"High": Impact.HIGH, "Medium": Impact.MEDIUM, "Low": Impact.LOW}
                effort_map = {"High": Effort.HIGH, "Medium": Effort.MEDIUM, "Low": Effort.LOW}

                # Find the page URL if mentioned in the recommendation
                page_url = rec.get("page_url", "")
                if not page_url:
                    # Try to find relevant page from CTAs
                    for cta in all_ctas[:5]:
                        if cta.get('page_url'):
                            page_url = cta['page_url']
                            break
                if not page_url:
                    page_url = self.context.company_website

                module.recommendations.append(Recommendation(
                    issue=rec.get("issue", ""),
                    recommendation=rec.get("recommendation", ""),
                    impact=impact_map.get(rec.get("impact", "Medium"), Impact.MEDIUM),
                    effort=effort_map.get(rec.get("effort", "Medium"), Effort.MEDIUM),
                    business_impact=rec.get("business_impact", "Direct impact on valid leads."),
                    category="Conversion Paths",
                    page_url=page_url,
                    kpi_impact=KPIImpact.LEAD_CONVERSION
                ))

            # Augment analysis text with Opportunity Cost info
            opp_cost = result.get("opportunity_cost", {})
            module.analysis_text = result.get("analysis", "") + \
                f"\n\n**Opportunity Cost:** {opp_cost.get('estimated_lost_revenue', 'Unknown')}\n" + \
                f"*Factor: {opp_cost.get('friction_factor', 'N/A')}*"

        except Exception as e:
            print(f"  Error in conversion analysis: {e}")
            return self._fallback_analysis(module, all_ctas, all_forms)

        return module

    def _fallback_analysis(self, module: ModuleScore, all_ctas: List, all_forms: List) -> ModuleScore:
        """Provide fallback scores based on basic metrics."""
        cta_score = min(len(all_ctas) * 2, 20)
        form_score = 10 if all_forms else 5

        module.items = [
            ScoreItem("CTA Visibility", "Are CTAs prominent?", 20, cta_score, f"Found {len(all_ctas)} CTAs"),
            ScoreItem("CTA Copy", "Is copy compelling?", 15, 8, "Manual review recommended"),
            ScoreItem("Form Optimization", "Form length and clarity", 15, form_score, f"Found {len(all_forms)} forms"),
            ScoreItem("Trust Signals Near Conversion", "Social proof near CTAs", 15, 7, "Manual review recommended"),
            ScoreItem("Path Clarity", "Is next step obvious?", 15, 7, "Manual review recommended"),
            ScoreItem("Multiple Entry Points", "Options for different stages", 10, 5, "Manual review recommended"),
            ScoreItem("Friction Reduction", "Minimal steps to convert", 10, 5, "Manual review recommended"),
        ]
        module.recommendations = [
            Recommendation(
                issue="CTA effectiveness not fully assessed",
                recommendation="Replace generic CTA text ('Submit', 'Learn More') with value-driven copy ('Get Your Free Audit', 'Start Saving Today')",
                impact=Impact.HIGH,
                effort=Effort.LOW,
                category="Conversion Paths",
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.LEAD_CONVERSION
            ),
            Recommendation(
                issue="Form friction not fully assessed",
                recommendation="Reduce form fields to essential-only (Name, Email, Company) for initial contact forms — move qualifying questions to follow-up",
                impact=Impact.HIGH,
                effort=Effort.LOW,
                category="Conversion Paths",
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.LEAD_CONVERSION
            ),
        ]
        module.analysis_text = f"Basic analysis: Found {len(all_ctas)} CTAs and {len(all_forms)} forms across the site. Detailed analysis requires manual review."
        module.raw_data = {
            "total_ctas": len(all_ctas),
            "total_forms": len(all_forms)
        }
        return module

    def self_audit(self) -> bool:
        """Validate conversion analysis quality."""
        if not super().self_audit():
            return False

        score = self.analysis.module_score
        if not score:
            return False

        # Should have CTA data
        if score.raw_data.get('total_ctas', 0) == 0:
            # This might be valid for some sites, but flag for review
            pass

        return True
