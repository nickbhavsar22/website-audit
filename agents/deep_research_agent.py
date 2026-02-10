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
        website_content = self.get_priority_pages_content(max_chars=20000)
        
        research_data = await self._perform_research(website_content)
        
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

    async def _perform_research(self, website_content: str) -> Dict[str, Any]:
        """Ask LLM to research the company."""
        
        prompt = f"""
        You are a Senior Strategic Consultant conducting deep due diligence on a B2B SaaS company.
        
        Target Company: {self.context.company_name}
        Website: {self.context.company_website}
        
        Context from Website:
        {website_content}
        
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
