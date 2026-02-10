"""Social Listening Agent for tracking mentions and sentiment."""

from typing import Dict, Any, List
from .base_agent import BaseAgent
from orchestrator.context_store import ContextStore, AgentStatus, ScreenshotData
from utils.scoring import ModuleScore, ConsultingOutcome, ScoreItem, AuditModule
import re
import asyncio

class SocialListeningAgent(BaseAgent):
    """
    Agent responsible for monitoring social chatter.
    
    Since we don't have direct firehose APIs (Twitter/X Enterprise), 
    we use targeted web searches to find recent public threads and mentions.
    """

    agent_name = "social_listening"
    agent_description = "Social Media & Sentiment Analyst"
    dependencies = []
    weight = 1.0

    async def run(self) -> ModuleScore:
        """Run the social listening analysis."""
        print(f"  Listening for social mentions of {self.context.company_name}...")

        # 1. Search for mentions
        mentions = await asyncio.to_thread(self._search_social_mentions)
        print(f"    Found {len(mentions)} relevant mentions.")
        
        # 2. Analyze Sentiment
        await self._analyze_sentiment(mentions)
        
        # 3. Capture Evidence (Screenshots)
        for m in mentions:
            if m.get('url'):
                 self.request_screenshot(m['url']) # Full page capture of the tweet/post
        
        # 4. Score
        score_items = self._score_sentiment(mentions)
        
        max_points = 20 # Simple scoring
        actual_points = sum(item.actual_points for item in score_items)
        percentage = min(100, (actual_points / max_points) * 100)

        # Determine outcome
        return ModuleScore(
            name=self.agent_name,
            weight=self.weight,
            items=score_items,
            analysis_text=self._generate_summary(mentions),
            raw_data={"mentions": mentions}
        )

    def _search_social_mentions(self) -> List[Dict[str, Any]]:
        """
        Simulate searching social media via specific site searches in LLM or direct tool if available.
        For this implementation, we will use the LLM to 'imagine' the search results based on 
        known recent events or generic simulation if actual search tool isn't plugged in.
        
        *If we had a 'search_web' tool available to the agent code (not just the orbital agent), 
        we would use it here. Assuming we can't call external tools from within the python script 
        easily without a wrapper, we will mock for safety or use a very basic request wrapper if permissible.*
        
        Actually, let's try to infer from the text we have or simply construct a placeholder 
        that informs the user "Live Social Search requires API Key".
        
        Wait, the prompts directory implies we might have some capabilities. 
        For now, we'll check common platforms using requests if possible? 
        No, scraping text from Twitter/LinkedIn pages directly is blocked by auth walls.
        
        Strategic approach: We will construct a 'simulated' listening report for the purpose of the 
        demo/tool unless provided with actual data. 
        OR, we can try to search the company website for social links and see if they have a 'feed'.
        
        Better: Use the `google-api-python-client` if configured, or just `requests` to `reddit.com`.
        Reddit is open. Let's try to hit Reddit JSON API for real data.
        """
        
        mentions = []
        import requests
        
        # clean name for search
        query = self.context.company_name.replace(" ", "+")
        
        # 1. Reddit Search (Public JSON API)
        try:
            url = f"https://www.reddit.com/search.json?q={query}&sort=new&limit=5"
            headers = {'User-agent': 'WebsiteAuditBot/1.0'}
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                for child in data.get('data', {}).get('children', []):
                    post = child['data']
                    mentions.append({
                        "source": "Reddit",
                        "author": post.get('author'),
                        "text": post.get('title') + " " + post.get('selftext', '')[:200],
                        "url": f"https://www.reddit.com{post.get('permalink')}",
                        "date": datetime.fromtimestamp(post.get('created_utc')).strftime('%Y-%m-%d'),
                        "sentiment": "neutral" # placeholder
                    })
        except Exception as e:
            print(f"    Reddit search failed: {e}")

        # If no real data found (or blocked), we might add a placeholder or rely on what we found
        if not mentions:
            # Add a 'simulation' mention for demonstration if real data fails? 
            # No, better to return empty and report "No recent mentions found".
            pass

        return mentions

    async def _analyze_sentiment(self, mentions: List[Dict]):
        """Analyze sentiment of text using LLM."""
        if not mentions:
            return

        tasks = []
        for m in mentions:
            prompt = f"""
            Analyze the sentiment of this social media post about {self.context.company_name}.
            Post: "{m['text']}"
            
            Return ONE word: Positive, Negative, or Neutral.
            """
            tasks.append(self.llm.complete_async(prompt, max_tokens=10))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for m, res in zip(mentions, results):
                if isinstance(res, str):
                    m['sentiment'] = res.strip()
                else:
                    m['sentiment'] = "Neutral"

    def _score_sentiment(self, mentions: List[Dict]) -> List[ScoreItem]:
        items = []
        
        if not mentions:
             items.append(ScoreItem(
                name="Recent Activity",
                description="Frequency of recent social mentions",
                actual_points=0,
                max_points=10,
                notes="No recent mentions found on public channels.",
                recommendation="Encourage more community engagement."
            ))
             return items
             
        positive_count = sum(1 for m in mentions if "Positive" in m['sentiment'])
        negative_count = sum(1 for m in mentions if "Negative" in m['sentiment'])
        
        sentiment_score = 5
        if positive_count > negative_count:
            sentiment_score = 10
        elif negative_count > positive_count:
            sentiment_score = 2
            
        items.append(ScoreItem(
            name="Brand Sentiment",
            description="Overall sentiment of recent mentions",
            actual_points=sentiment_score,
            max_points=10,
            notes=f"Found {len(mentions)} mentions. {positive_count} Positive.",
            recommendation="Monitor channels closely."
        ))
        
        return items

    def _generate_summary(self, mentions: List[Dict]) -> str:
        """Generate feed view."""
        if not mentions:
            return "No recent social mentions found."
            
        summary = "### Social Media Feed\n\n"
        for m in mentions:
            icon = "🔴" if "Negative" in m['sentiment'] else "🟢" if "Positive" in m['sentiment'] else "⚪"
            summary += f"**{m['source']}** - {m['date']} {icon}\n"
            summary += f"> {m['text'][:150]}...\n\n"
            summary += f"[View Original]({m['url']})\n\n---\n\n"
            
        return summary
from datetime import datetime
