"""Prompt Visibility (Share of Voice) Agent."""

from typing import Dict, Any, List
from .base_agent import BaseAgent
from orchestrator.context_store import ContextStore, AgentStatus
from utils.scoring import ModuleScore, ConsultingOutcome, ScoreItem, AuditModule
import time

class PromptVisibilityAgent(BaseAgent):
    """
    Agent responsible for analyzing 'Prompt Visibility' (Share of Voice in LLMs).
    
    It identifies key 'Jobs to be Done' (JTBD) questions for the industry
    and tests how often the client appears in LLM answers vs competitors.
    """

    agent_name = "prompt_visibility"
    agent_description = "Prompt Visibility & Share of Voice Analyst"
    dependencies = ["deep_research"] # Needs context to know industry/competitors
    weight = 1.5 

    async def run(self) -> ModuleScore:
        """Run the prompt visibility analysis."""
        print(f"  Analyzing Prompt Visibility for {self.context.company_name}...")

        # 1. Identify Key Questions
        questions = await self._identify_jtbd_questions()
        print(f"    Identified {len(questions)} key questions.")

        # 2. Test Questions against LLM
        results = []
        for q in questions:
            print(f"    Testing: {q}")
            rankings = await self._test_prompt_visibility(q)
            results.append({
                "question": q,
                "rankings": rankings
            })
            
        # 3. Calculate Score
        score_items = self._score_visibility(results)
        
        return ModuleScore(
            name=self.agent_name,
            weight=self.weight,
            items=score_items,
            analysis_text=self._generate_summary(results),
            raw_data={"results": results}
        )

    async def _identify_jtbd_questions(self) -> List[str]:
        """Ask LLM to generate 5 key buying questions for this industry."""
        
        # Get research for context
        research = self.context.get_analysis("deep_research")
        details = research.raw_data if research else {}
        
        prompt = f"""
        Generate 5 specific "How to" or "Best software for" questions that a prospective buyer would ask an AI when looking for a solution like {self.context.company_name}.
        
        Context:
        - Industry: {self.context.industry}
        - Value Props: {details.get('key_value_props', [])}
        
        Examples:
        - "How to automate SDR outreach?"
        - "Best enterprise CRM for healthcare"
        
        Return ONLY a JSON list of strings.
        """
        
        try:
            questions = await self.llm.complete_json_async(prompt, max_tokens=1000)
            if isinstance(questions, list):
                return questions[:5]
            if isinstance(questions, dict) and "questions" in questions:
                return questions["questions"]
        except:
            pass
            
        # Fallback
        return [
            f"Best software for {self.context.industry}",
            f"How to improve {self.context.industry} workflows",
            f"Alternatives to {self.context.competitors[0] if self.context.competitors else 'leading competitors'}",
            f"Top rated {self.context.industry} tools",
            f"Implementation guide for {self.context.industry} software"
        ]

    async def _test_prompt_visibility(self, question: str) -> List[Dict[str, Any]]:
        """
        Ask the LLM the question and parse the response to see who is mentioned.
        Note: We are asking the AI about *itself* (or a peer model), which is a meta-test of training data.
        """
        
        prompt = f"""
        Answer this user question as a helpful assistant:
        "{question}"
        
        Provide a list of recommended tools or solutions.
        """
        
        response = await self.llm.complete_async(prompt, max_tokens=1000)
        
        # Analyze response for mentions
        # We check for Client Name and Competitors
        
        entities = [self.context.company_name] + self.context.competitors
        rankings = []
        
        # Normalize text for search
        response_lower = response.lower()
        
        found_entities = []
        for entity in entities:
            if entity.lower() in response_lower:
                # Find index to approximate "rank" (earlier is better)
                index = response_lower.find(entity.lower())
                found_entities.append((entity, index))
        
        # Sort by index (appearance order)
        found_entities.sort(key=lambda x: x[1])
        
        # Convert to rank list
        for i, (name, _) in enumerate(found_entities):
            rankings.append({
                "name": name,
                "rank": i + 1,
                "mentioned": True
            })
            
        # Add unmentioned
        mentioned_names = [r["name"] for r in rankings]
        for entity in entities:
            if entity not in mentioned_names:
                rankings.append({
                    "name": entity,
                    "rank": 999,
                    "mentioned": False
                })
                
        return rankings

    def _score_visibility(self, results: List[Dict]) -> List[ScoreItem]:
        """Score based on how often client appears in top 3."""
        total_questions = len(results)
        client_mentions = 0
        client_top_3 = 0

        for res in results:
            rankings = res["rankings"]
            client_rank = next((r for r in rankings if r["name"] == self.context.company_name), None)

            if client_rank and client_rank["mentioned"]:
                client_mentions += 1
                if client_rank["rank"] <= 3:
                    client_top_3 += 1

        # Calculate aggregate score: weight mentions and top-3 placement
        if total_questions > 0:
            mention_ratio = client_mentions / total_questions
            top3_ratio = client_top_3 / total_questions
            # Score out of 100: 40% for mentions, 60% for top-3 placement
            actual = int((mention_ratio * 40) + (top3_ratio * 60))
        else:
            actual = 0

        recommendation = ""
        if client_mentions == 0:
            recommendation = "Critical: Brand not mentioned in any AI-generated responses. Develop authoritative content (documentation, reviews, thought leadership) targeting key buying queries."
        elif client_top_3 < total_questions:
            recommendation = "Optimize brand presence in technical documentation, review sites, and industry publications to improve AI visibility ranking."

        items = [ScoreItem(
            name="Overall Prompt Visibility",
            description="Aggregate visibility across key buying questions",
            actual_points=actual,
            max_points=100,
            notes=f"Mentioned in {client_mentions}/{total_questions} queries, Top 3 in {client_top_3}",
            recommendation=recommendation
        )]

        return items

    def _generate_summary(self, results: List[Dict]) -> str:
        """Generate markdown table of results."""
        summary = "### Share of Voice Analysis (Prompt Visibility)\n\n"
        summary += "How the brand appears in AI-generated answers for key buying questions.\n\n"
        
        # Table Header
        summary += "| Question | Client Rank | Top Competitor |\n"
        summary += "| :--- | :---: | :--- |\n"
        
        for res in results:
            q = res["question"]
            rankings = res["rankings"]
            
            # Client Rank
            client_rank = next((r for r in rankings if r["name"] == self.context.company_name), None)
            c_text = f"#{client_rank['rank']}" if client_rank and client_rank['mentioned'] else "❌"
            
            # Top Competitor
            top_competitor = rankings[0]["name"] if rankings and rankings[0]["mentioned"] else "Generic Advice"
            
            summary += f"| {q} | {c_text} | {top_competitor} |\n"
            
        return summary
