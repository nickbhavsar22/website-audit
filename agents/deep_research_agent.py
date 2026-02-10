"""Deep Research Agent for gathering comprehensive company context."""

from typing import Dict, Any, List
from .base_agent import BaseAgent
from orchestrator.context_store import ContextStore, AgentStatus
from utils.scoring import ModuleScore, ConsultingOutcome, ScoreItem, AuditModule

class DeepResearchAgent(BaseAgent):
    """
    Agent responsible for deep research on the company.
    
    It gathers context about:
    - Company Background & History
    - Funding & Investment Status
    - Target Audience (ICP)
    - Key Customers
    - Product/Market Fit signals
    """

    agent_name = "deep_research"
    agent_description = "Deep Research Specialist"
    dependencies = []  # Can run early, maybe after initial website crawl or independently
    weight = 1.0

    async def run(self) -> ModuleScore:
        """Run the deep research analysis."""
        print(f"  Performing deep research on {self.context.company_name}...")

        # 1. Gather Context
        # We invoke the LLM to "research" based on its training data + website content
        website_content = self.get_priority_pages_content(max_chars=30000)

        # Extract structured signals from pages before sending to LLM
        structured_signals = self._extract_structured_signals()

        research_data = await self._perform_research(website_content, structured_signals)
        
        # 2. Store results in Context (so other agents can use it)
        # We need to extend ContextStore to hold this, but for now we'll put it in raw_data
        # and maybe update the shared context explanation
        self._update_context_with_research(research_data)

        # 3. Score findings (Self-audit of the research quality)
        score_items = self._evaluate_research_quality(research_data)
        
        # Calculate score
        max_points = 5 * 10 # 5 categories * 10 points
        actual_points = sum(item.actual_points for item in score_items)
        percentage = (actual_points / max_points) * 100

        return ModuleScore(
            name=self.agent_name,
            weight=self.weight,
            items=score_items,
            analysis_text=self._generate_summary(research_data),
            raw_data=research_data
        )

    def _extract_structured_signals(self) -> Dict[str, Any]:
        """Extract structured signals from crawled pages for additional LLM context."""
        signals = {
            "pricing_tiers": [],
            "team_members": [],
            "integration_partners": [],
            "customer_logos_alt": [],
        }

        for url, page in self.context.pages.items():
            url_lower = url.lower()

            # Extract pricing tier names from pricing pages
            if '/pricing' in url_lower:
                for h in page.h2_tags + page.h3_tags:
                    h_lower = h.lower()
                    if any(kw in h_lower for kw in ['plan', 'tier', 'starter', 'pro', 'enterprise', 'business', 'free', 'basic', 'premium']):
                        if h not in signals["pricing_tiers"]:
                            signals["pricing_tiers"].append(h)

            # Extract team members from about/team pages
            if '/team' in url_lower or '/about' in url_lower or '/leadership' in url_lower:
                for img in page.images:
                    alt = img.get('alt', '').strip()
                    if alt and len(alt.split()) <= 5 and alt[0].isupper():
                        if alt not in signals["team_members"]:
                            signals["team_members"].append(alt)

            # Extract integration partners
            if '/integration' in url_lower or '/partners' in url_lower:
                for h in page.h2_tags + page.h3_tags:
                    if h and len(h.split()) <= 4:
                        if h not in signals["integration_partners"]:
                            signals["integration_partners"].append(h)

            # Extract customer logo alt text from any page
            for img in page.images:
                alt = img.get('alt', '').lower()
                if any(kw in alt for kw in ['logo', 'customer', 'client', 'trusted']):
                    clean_alt = img.get('alt', '').strip()
                    if clean_alt and clean_alt not in signals["customer_logos_alt"]:
                        signals["customer_logos_alt"].append(clean_alt)

        # Limit each to reasonable size
        for key in signals:
            signals[key] = signals[key][:20]

        return signals

    async def _perform_research(self, website_content: str, structured_signals: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ask LLM to research the company."""

        signals_context = ""
        if structured_signals:
            parts = []
            if structured_signals.get("pricing_tiers"):
                parts.append(f"Pricing Tiers: {', '.join(structured_signals['pricing_tiers'])}")
            if structured_signals.get("team_members"):
                parts.append(f"Team Members Detected: {', '.join(structured_signals['team_members'][:10])}")
            if structured_signals.get("integration_partners"):
                parts.append(f"Integration Partners: {', '.join(structured_signals['integration_partners'][:10])}")
            if structured_signals.get("customer_logos_alt"):
                parts.append(f"Customer Logos/References: {', '.join(structured_signals['customer_logos_alt'][:10])}")
            if parts:
                signals_context = "\n\nStructured Signals Extracted:\n" + "\n".join(parts)

        prompt = f"""
        You are a Senior Strategic Consultant conducting deep due diligence on a B2B SaaS company.

        Target Company: {self.context.company_name}
        Website: {self.context.company_website}

        Context from Website:
        {website_content}
        {signals_context}

        Your Goal: Construct a comprehensive "Company Profile" based on your internal knowledge and the text provided.
        If specific details (like exact funding amount) are not public or in the text, make a highly educated estimate based on company stage, employee count signals, and industry norms, or state "Unknown" if it's impossible to guess.

        Respond in valid JSON with the following structure:
        {{
            "background": "Brief history and founding story (2-3 sentences)",
            "funding_status": "Bootstrapped, Seed, Series A, etc. (include amounts if known)",
            "icp": {{
                "primary": "Primary Ideal Customer Profile",
                "industries": ["Industry 1", "Industry 2"],
                "roles": ["Role 1", "Role 2"]
            }},
            "products": ["Core Product 1", "Core Product 2"],
            "key_value_props": ["Value 1", "Value 2"],
            "market_position": "Brief assessment of where they sit in the market (e.g. 'Premium Enterprise Solution' vs 'SMB Self-Serve')",
            "competitors": ["Competitor 1", "Competitor 2"]
        }}
        """

        return await self.llm.complete_json_async(prompt, max_tokens=1500)

    def _update_context_with_research(self, data: Dict[str, Any]):
        """Update the shared context with findings."""
        # Update context competitors if not already set
        if not self.context.competitors and data.get("competitors"):
            self.context.competitors = data["competitors"]
            print(f"    [Deep Research] Discovered competitors: {', '.join(self.context.competitors)}")
            
        # We could add more fields to ContextStore later to hold this structured data strictly
        # For now, relying on agents reading this agent's output via get_analysis() is fine.
        pass

    def _evaluate_research_quality(self, data: Dict[str, Any]) -> List[ScoreItem]:
        """Evaluate how much we learned."""
        items = []
        
        # Check completeness
        has_funding = data.get("funding_status") and data["funding_status"] != "Unknown"
        items.append(ScoreItem(
            name="Funding/Stage Identified",
            description="Clarity of company funding",
            actual_points=10 if has_funding else 5,
            max_points=10,
            notes=f"Stage: {data.get('funding_status')}",
            recommendation="Update Crunchbase/About page if this info is public but hard to find." if not has_funding else ""
        ))
        
        has_icp = bool(data.get("icp", {}).get("primary"))
        items.append(ScoreItem(
            name="ICP Clarity",
            description="Clarity of Ideal Customer Profile",
            actual_points=10 if has_icp else 4,
            max_points=10,
            notes=f"Primary ICP: {data.get('icp', {}).get('primary', 'Unclear')}",
            recommendation="Define ICP clearly on homepage." if not has_icp else ""
        ))
        
        items.append(ScoreItem(
            name="Market Position",
            description="Clarity of market positioning",
            actual_points=10 if data.get("market_position") else 5,
            max_points=10,
            notes=str(data.get("market_position")),
            recommendation=""
        ))
        
        return items

    def _generate_summary(self, data: Dict[str, Any]) -> str:
        """Generate a text summary of the research."""
        return f"""
        ### Company Background
        {data.get('background', 'N/A')}
        
        **Funding Stage:** {data.get('funding_status', 'Unknown')}
        **Market Position:** {data.get('market_position', 'Unknown')}
        
        ### Target Audience (ICP)
        - **Primary:** {data.get('icp', {}).get('primary', 'N/A')}
        - **Industries:** {', '.join(data.get('icp', {}).get('industries', []))}
        - **Key Roles:** {', '.join(data.get('icp', {}).get('roles', []))}
        
        ### Core Value Propositions
        {', '.join([f"- {v}" for v in data.get('key_value_props', [])])}
        """
