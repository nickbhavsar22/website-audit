"""Trust & Credibility Signals Agent."""

import json
import re
from typing import Dict, List

from .base_agent import BaseAgent
from utils.scoring import ModuleScore, ScoreItem, Recommendation, Impact, Effort, KPIImpact


class TrustAgent(BaseAgent):
    """
    Analyzes trust and credibility signals.

    Evaluates:
    - Customer logos
    - Testimonials
    - Case studies
    - Awards/recognition
    - Team/about page
    - Security/compliance
    - Press/media mentions
    - Reviews/ratings
    """

    agent_name = "trust"
    agent_description = "Analyzes trust and credibility signals"
    dependencies = ["website"]
    weight = 1.0

    TRUST_PATTERNS = {
        'customer_logos': r'(customer|client|trusted by|used by|logo)',
        'testimonials': r'(testimonial|quote|said|review)',
        'case_studies': r'(case study|success story|customer story)',
        'awards': r'(award|winner|recognized|certification|certified)',
        'security': r'(soc\s*2|gdpr|hipaa|iso|security|complian)',
        'press': r'(press|media|news|featured in|as seen)',
        'reviews': r'(g2|capterra|trustpilot|rating|star)',
    }

    def _generate_cot_plan(self) -> str:
        """Generate Chain of Thought plan."""
        return f"""
        Plan for Trust Analysis of {self.context.company_name}:
        1. Scan for hard trust signals (Logos, Case Studies, Certifications).
        2. Scan for soft trust signals (Testimonials, Team Photos, 'About Us' story).
        3. Evaluate content for the 'Buying Committee' (User, Influencer, Approver).
        4. Calculate the 'Trust Tax': Are they losing leads due to skepticism?
        5. Verify detected signals against industry baselines.
        """

    async def run(self) -> ModuleScore:
        """Execute trust analysis asynchronously."""
        module = ModuleScore(name="Trust & Credibility", weight=self.weight)

        # Aggregate trust-related content
        all_testimonials = []
        all_images = []
        content_samples = []
        detected_signals = {k: False for k in self.TRUST_PATTERNS.keys()}

        # Prioritize pages (Home > About > Others)
        home_url = self.context.company_website.rstrip('/')
        sorted_pages = sorted(
            self.context.pages.items(),
            key=lambda x: 0 if x[0].rstrip('/') == home_url else (1 if '/about' in x[0] or '/company' in x[0] else 2)
        )

        for url, page in sorted_pages:
            all_testimonials.extend(page.testimonials)
            all_images.extend(page.images[:10])

            # Check for trust patterns
            text_lower = page.raw_text.lower()
            for signal, pattern in self.TRUST_PATTERNS.items():
                if re.search(pattern, text_lower, re.I):
                    detected_signals[signal] = True

            content_samples.append(f"""
--- PAGE: {url} ---
Title: {page.title}
Content: {page.raw_text[:2000]}
""")

        page_content = '\n'.join(content_samples)[:12000]
        testimonials_json = json.dumps(all_testimonials[:10], indent=2)
        images_json = json.dumps([{'src': img.get('src', ''), 'alt': img.get('alt', '')} for img in all_images[:20]], indent=2)

        if not self.llm.is_available():
            return self._fallback_analysis(module, detected_signals, all_testimonials)

        try:
            result = await self.llm.analyze_with_prompt_async(
                "trust",
                company_name=self.context.company_name,
                company_website=self.context.company_website,
                page_content=page_content,
                max_tokens=4000,
                testimonials=testimonials_json,
                images=images_json
            )

            # Build score items
            score_mapping = {
                "customer_logos": ("Customer Logos", 15),
                "testimonials": ("Testimonials", 20),
                "case_studies": ("Case Studies", 20),
                "awards_recognition": ("Awards/Recognition", 10),
                "team_about": ("Team/About", 10),
                "security_compliance": ("Security/Compliance", 10),
                "press_media": ("Press/Media", 10),
                "reviews_ratings": ("Reviews/Ratings", 5),
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
                "trust_elements_found": result.get("trust_elements_found", []),
                "strengths": result.get("strengths", []),
                "weaknesses": result.get("weaknesses", []),
                "detected_signals": detected_signals,
                "testimonial_count": len(all_testimonials),
                "trust_tax": result.get("trust_tax", {}),
                "buying_committee": result.get("buying_committee", {})
            }

            # Build recommendations
            for rec in result.get("recommendations", []):
                impact_map = {"High": Impact.HIGH, "Medium": Impact.MEDIUM, "Low": Impact.LOW}
                effort_map = {"High": Effort.HIGH, "Medium": Effort.MEDIUM, "Low": Effort.LOW}

                # Trust recommendations typically link to homepage or about page
                page_url = self.context.company_website
                for url in self.context.pages.keys():
                    if '/about' in url.lower() or '/company' in url.lower():
                        page_url = url
                        break

                module.recommendations.append(Recommendation(
                    issue=rec.get("issue", ""),
                    recommendation=rec.get("recommendation", ""),
                    impact=impact_map.get(rec.get("impact", "Medium"), Impact.MEDIUM),
                    effort=effort_map.get(rec.get("effort", "Medium"), Effort.MEDIUM),
                    business_impact=rec.get("business_impact", "High impact on trust."),
                    category="Trust & Credibility",
                    page_url=page_url,
                    kpi_impact=KPIImpact.CUSTOMER_TRUST
                ))

            # Augment analysis with Trust Tax info
            trust_tax = result.get("trust_tax", {})
            committee = result.get("buying_committee", {})
            
            module.analysis_text = result.get("analysis", "") + \
                f"\n\n**Financial Impact (Trust Tax):** {trust_tax.get('percentage', 'Unknown')} - {trust_tax.get('revenue_impact', '')}" + \
                f"\n\n**Buying Committee Coverage:**\n" + \
                f"- User: {committee.get('user_score', 'N/A')}\n" + \
                f"- Influencer: {committee.get('influencer_score', 'N/A')}\n" + \
                f"- Approver: {committee.get('approver_score', 'N/A')}"

        except Exception as e:
            print(f"  Error in trust analysis: {e}")
            return self._fallback_analysis(module, detected_signals, all_testimonials)

        return module

    def _fallback_analysis(self, module: ModuleScore, detected_signals: Dict, all_testimonials: List) -> ModuleScore:
        """Provide fallback scores based on detection."""
        module.items = [
            ScoreItem("Customer Logos", "Client logos displayed", 15, 8 if detected_signals['customer_logos'] else 3,
                     "Detected" if detected_signals['customer_logos'] else "Not clearly detected"),
            ScoreItem("Testimonials", "Specific quotes", 20, 10 if all_testimonials else 5,
                     f"Found {len(all_testimonials)} potential testimonials"),
            ScoreItem("Case Studies", "Success stories", 20, 10 if detected_signals['case_studies'] else 5,
                     "Detected" if detected_signals['case_studies'] else "Not clearly detected"),
            ScoreItem("Awards/Recognition", "Industry recognition", 10, 5 if detected_signals['awards'] else 2,
                     "Detected" if detected_signals['awards'] else "Not clearly detected"),
            ScoreItem("Team/About", "Leadership visibility", 10, 5, "Manual review recommended"),
            ScoreItem("Security/Compliance", "Certifications", 10, 5 if detected_signals['security'] else 2,
                     "Detected" if detected_signals['security'] else "Not clearly detected"),
            ScoreItem("Press/Media", "Media mentions", 10, 5 if detected_signals['press'] else 2,
                     "Detected" if detected_signals['press'] else "Not clearly detected"),
            ScoreItem("Reviews/Ratings", "G2, Capterra, etc.", 5, 3 if detected_signals['reviews'] else 1,
                     "Detected" if detected_signals['reviews'] else "Not clearly detected"),
        ]
        module.recommendations = [
            Recommendation(
                issue="Customer proof not verified",
                recommendation="Add a customer logo bar to the homepage with 5-8 recognizable logos and a '100+ companies trust us' headline",
                impact=Impact.HIGH,
                effort=Effort.LOW,
                category="Trust & Credibility",
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.CUSTOMER_TRUST
            ),
            Recommendation(
                issue="Testimonial quality not assessed",
                recommendation="Replace anonymous quotes with attributed testimonials including name, title, company, and headshot",
                impact=Impact.HIGH,
                effort=Effort.MEDIUM,
                category="Trust & Credibility",
                page_url=self.context.company_website,
                kpi_impact=KPIImpact.CLOSE_RATE
            ),
        ]
        module.analysis_text = f"Basic trust signal detection completed. Found {len(all_testimonials)} testimonial-like elements."
        module.raw_data = {
            "detected_signals": detected_signals,
            "testimonial_count": len(all_testimonials)
        }
        return module

    def self_audit(self) -> bool:
        """Validate trust analysis quality."""
        return super().self_audit()
