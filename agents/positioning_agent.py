"""Positioning and Messaging Analysis Agent."""

import json
from typing import List, Optional

from .base_agent import BaseAgent
from utils.scoring import ModuleScore, ScoreItem, Recommendation, Impact, Effort, KPIImpact


class PositioningAgent(BaseAgent):
    """
    Analyzes positioning and messaging effectiveness.

    Evaluates:
    - Value proposition clarity
    - Differentiation
    - ICP alignment
    - Pain point articulation
    - Outcome focus
    - Messaging consistency
    """

    agent_name = "positioning"
    agent_description = "Analyzes positioning and messaging effectiveness"
    dependencies = ["website"]  # Needs crawled pages
    weight = 2.0  # Double weight for positioning
    expected_llm_fields = {
        "scores": dict,
        "jtbd_analysis": dict,
        "messaging_house": dict,
        "analysis": str
    }

    def _generate_cot_plan(self) -> str:
        """Generate Chain of Thought plan."""
        return f"""
        Plan for Positioning Analysis of {self.context.company_name}:
        1. Identify the 'Job to be Done' (JTBD) from the priority pages.
        2. Evaluate if the Functional Job (task) and Emotional Job (feeling) are addressed.
        3. Check for specific Value Propositions vs generic claims.
        4. Assess differentiation: 'Why us?' vs competitors.
        5. If gaps found, draft a 'Messaging House' repair strategy.
        """

    async def run(self) -> ModuleScore:
        """Execute positioning analysis asynchronously."""
        module = ModuleScore(name="Positioning & Messaging", weight=self.weight)

        # Get content from priority pages
        page_content = self.get_priority_pages_content()

        if not page_content:
            module.analysis_text = "No content available for analysis."
            return module

        if not self.llm.is_available():
            return self._fallback_analysis(module)

        # Load and format prompt
        try:
            result = await self.llm.analyze_with_prompt_async(
                "positioning",
                company_name=self.context.company_name,
                company_website=self.context.company_website,
                industry=self.context.industry,
                page_content=page_content,
                max_tokens=4000
            )

            # Validate and patch missing fields
            result = self._validate_llm_response(result)

            # Ensure JTBD fields have sensible defaults
            jtbd = result.get("jtbd_analysis", {})
            if not jtbd.get("functional_job"):
                jtbd["functional_job"] = "Not clearly articulated on the website"
            if not jtbd.get("emotional_job"):
                jtbd["emotional_job"] = "Not clearly articulated on the website"
            result["jtbd_analysis"] = jtbd

            # Ensure messaging house has defaults
            mh = result.get("messaging_house", {})
            if not mh.get("core_pillar"):
                mh["core_pillar"] = "No clear umbrella message identified"
            result["messaging_house"] = mh

            # Ensure recommended_assets has defaults if empty
            assets = jtbd.get("recommended_assets", [])
            if not assets:
                jtbd["recommended_assets"] = [
                    {"type": "Case Study", "description": "Customer success story demonstrating core value proposition"},
                    {"type": "Comparison Guide", "description": "Side-by-side comparison against key alternatives"},
                    {"type": "ROI Calculator", "description": "Interactive tool quantifying business outcomes"}
                ]

            # Build score items from LLM response
            score_mapping = {
                "value_proposition_clarity": ("Value Proposition Clarity", 20),
                "differentiation": ("Differentiation", 20),
                "icp_alignment": ("ICP Alignment & JTBD", 15),
                "pain_point_articulation": ("Pain Point Articulation", 15),
                "outcome_focus": ("Outcome Focus", 15),
                "consistency": ("Consistency", 15),
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
                "strengths": result.get("strengths", []),
                "weaknesses": result.get("weaknesses", []),
                "jtbd_analysis": result.get("jtbd_analysis", {}),
                "messaging_house": result.get("messaging_house", {})
            }

            # Build recommendations
            for rec in result.get("recommendations", []):
                impact_map = {"High": Impact.HIGH, "Medium": Impact.MEDIUM, "Low": Impact.LOW}
                effort_map = {"High": Effort.HIGH, "Medium": Effort.MEDIUM, "Low": Effort.LOW}

                # Default to homepage for positioning recommendations
                homepage = self.context.get_homepage()
                page_url = homepage.url if homepage else self.context.company_website

                module.recommendations.append(Recommendation(
                    issue=rec.get("issue", ""),
                    recommendation=rec.get("recommendation", ""),
                    impact=impact_map.get(rec.get("impact", "Medium"), Impact.MEDIUM),
                    effort=effort_map.get(rec.get("effort", "Medium"), Effort.MEDIUM),
                    business_impact=rec.get("business_impact", "High impact on conversion."),
                    category="Positioning & Messaging",
                    page_url=page_url,
                    kpi_impact=KPIImpact.CLOSE_RATE
                ))

            # Augment analysis text with JTBD info
            jtbd = result.get("jtbd_analysis", {})
            assets = jtbd.get('recommended_assets', [])
            asset_summary = "\n".join([f"- {a.get('type')}: {a.get('description')}" for a in assets]) if assets else "No specific assets recommended."
            
            module.analysis_text = result.get("analysis", "") + f"\n\n**Jobs to be Done Analysis:**\n- **Functional Job:** {jtbd.get('functional_job', 'N/A')}\n- **Emotional Job:** {jtbd.get('emotional_job', 'N/A')}\n\n**Recommended Assets:**\n{asset_summary}"

        except Exception as e:
            import logging
            logging.exception(f"Error in positioning analysis for {self.context.company_name}")
            print(f"  Error in positioning analysis: {e}")
            return self._fallback_analysis(module, str(e))

        return module

    def _fallback_analysis(self, module: ModuleScore, error_msg: str = None) -> ModuleScore:
        """Provide fallback scores when LLM is unavailable."""
        module.items = [
            ScoreItem("Value Proposition Clarity", "Is the value prop clear?", 20, 10, "Analysis unavailable"),
            ScoreItem("Differentiation", "Is differentiation clear?", 20, 10, "Analysis unavailable"),
            ScoreItem("ICP Alignment & JTBD", "Is ICP targeted?", 15, 7, "Analysis unavailable"),
            ScoreItem("Pain Point Articulation", "Are pain points addressed?", 15, 7, "Analysis unavailable"),
            ScoreItem("Outcome Focus", "Are outcomes emphasized?", 15, 7, "Analysis unavailable"),
            ScoreItem("Consistency", "Is messaging consistent?", 15, 7, "Analysis unavailable"),
        ]
        module.recommendations = [
            Recommendation(
                issue="Value proposition clarity needs review",
                recommendation="Audit homepage H1 and subheadline to ensure they pass the 5-second test — a new visitor should understand what you do, who you serve, and why you're different within 5 seconds",
                impact=Impact.HIGH,
                effort=Effort.LOW,
                category="Positioning & Messaging",
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.BOUNCE_RATE
            ),
            Recommendation(
                issue="Differentiation not assessed",
                recommendation="Create a 'Why Us' section on the homepage that explicitly contrasts your approach against alternatives — avoid generic claims like 'best-in-class'",
                impact=Impact.HIGH,
                effort=Effort.MEDIUM,
                category="Positioning & Messaging",
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.CLOSE_RATE
            ),
        ]
        module.raw_data = {
            "jtbd_analysis": {
                "functional_job": "Fallback Job (LLM Unavailable)",
                "emotional_job": "Fallback Feeling (LLM Unavailable)",
                "recommended_assets": [
                    {"type": "Case Study", "description": "Success stories showing core value"},
                    {"type": "Video Demo", "description": "High-level product walkthrough"}
                ]
            }
        }
        
        if error_msg:
             module.analysis_text = f"Positioning Analysis Failed. Error: {error_msg}"
        else:
             module.analysis_text = "Detailed positioning analysis requires ANTHROPIC_API_KEY to be set."
        
        module.analysis_text += "\n\n**Jobs to be Done Analysis (Fallback):**\n- **Functional Job:** Fallback Job\n- **Emotional Job:** Fallback Feeling\n\n**Recommended Assets (Fallback):**\n- Case Study: Success stories showing core value\n- Video Demo: High-level product walkthrough"
        return module

    def self_audit(self) -> bool:
        """Validate positioning analysis quality."""
        if not super().self_audit():
            return False

        score = self.analysis.module_score
        if not score:
            return False

        # Check that we have all expected score items
        expected_items = 6
        if len(score.items) < expected_items:
            return False

        # Check for meaningful recommendations
        if self.llm.is_available() and len(score.recommendations) < 2:
            return False

        return True

    async def revise(self, feedback: str, suggestions: List[str]) -> ModuleScore:
        """Revise analysis based on critique feedback."""
        # For positioning, we might need to re-analyze with additional context
        # or focus on specific weak areas

        # Get additional content if suggestions mention specific pages
        additional_content = ""
        for suggestion in suggestions:
            if "homepage" in suggestion.lower():
                home = self.context.get_homepage()
                if home:
                    additional_content += f"\nHomepage focus:\n{home.raw_text[:2000]}"

        # Re-run with feedback context
        return await self.run()
