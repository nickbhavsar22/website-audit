"""Competitor Analysis Agent."""

import requests
import asyncio
from bs4 import BeautifulSoup
from typing import Dict, List, Optional

from .base_agent import BaseAgent
from utils.scoring import ModuleScore, ScoreItem, Recommendation, Impact, Effort, KPIImpact


class CompetitorAgent(BaseAgent):
    """
    Analyzes competitive positioning.

    Compares client to competitors on:
    - Messaging and headlines
    - Value propositions
    - Key differentiators
    - Target audience
    - Positioning gaps and opportunities
    """

    agent_name = "competitor"
    agent_description = "Analyzes competitive positioning"
    dependencies = ["website", "positioning"]  # Needs client's positioning first
    weight = 1.0

    async def run(self) -> ModuleScore:
        """Execute competitor analysis asynchronously."""
        module = ModuleScore(name="Competitive Positioning", weight=self.weight)

        competitors = self.context.competitors

        # If no competitors specified, try to discover them
        if not competitors:
            print("  No competitors specified, attempting discovery...")
            discovered = await self.discover_competitors()
            if discovered:
                competitors = discovered
                self.context.competitors = discovered
                print(f"  Discovered {len(discovered)} competitors")
            else:
                module.analysis_text = "No competitors specified and discovery was unsuccessful."
                module.items = [
                    ScoreItem("Competitor Analysis", "Competitive positioning review", 100, 50, "No competitors found")
                ]
                return module

        # Fetch competitor data
        print("  Fetching competitor homepages...")
        competitor_data = []
        for comp_url in competitors[:5]:  # Limit to 5 competitors
            print(f"    - {comp_url}")
            data = await asyncio.to_thread(self._fetch_competitor_homepage, comp_url)
            if data:
                competitor_data.append(data)

        if not competitor_data:
            module.analysis_text = "Could not fetch any competitor websites."
            module.items = [
                ScoreItem("Competitor Analysis", "Competitive positioning review", 100, 50, "Could not fetch competitors")
            ]
            return module

        # Get client homepage content
        client_content = self._get_client_content()

        # Format competitor data for prompt
        comp_text = self._format_competitor_data(competitor_data)

        if not self.llm.is_available():
            return self._fallback_analysis(module, competitor_data)

        try:
            # Get homepage reference for page_url fields
            homepage = self.context.get_homepage()

            # Use the competitors prompt
            template = self.llm.load_prompt("competitors")
            prompt = self.llm.format_prompt(
                template,
                client_name=self.context.company_name,
                client_website=self.context.company_website,
                client_content=client_content,
                competitor_data=comp_text
            )

            result = await self.llm.complete_json_async(prompt, max_tokens=3000)

            # Store competitor data
            module.raw_data = {
                'competitors': result.get('competitors', []),
                'client_positioning': result.get('client_positioning', {}),
                'positioning_gaps': result.get('positioning_gaps', []),
                'positioning_opportunities': result.get('positioning_opportunities', []),
                'competitors_discovered': hasattr(self, '_discovery_result'),
                'discovery_result': getattr(self, '_discovery_result', None)
            }

            module.analysis_text = result.get('comparison_analysis', '')

            # Create score items based on analysis
            client_pos = result.get('client_positioning', {})
            diff_count = len(client_pos.get('key_differentiators', []))
            gaps = result.get('positioning_gaps', [])
            opportunities = result.get('positioning_opportunities', [])

            # Score based on differentiation clarity
            if diff_count >= 3:
                diff_score = 35
                diff_notes = f"Clear differentiation with {diff_count} unique points"
            elif diff_count >= 2:
                diff_score = 25
                diff_notes = f"Moderate differentiation with {diff_count} points"
            else:
                diff_score = 15
                diff_notes = "Weak differentiation vs competitors"

            module.items.append(ScoreItem(
                name="Differentiation Clarity",
                description="How clearly the company differentiates from competitors",
                max_points=35,
                actual_points=diff_score,
                notes=diff_notes,
                recommendation="Strengthen differentiation by identifying and claiming a unique category position that competitors cannot replicate" if diff_count < 3 else "",
                page_url=homepage.url if homepage else self.context.company_website,
            ))

            # Score based on positioning gaps
            if len(gaps) <= 1:
                gap_score = 35
                gap_notes = "Strong positioning with minimal gaps"
            elif len(gaps) <= 3:
                gap_score = 25
                gap_notes = f"{len(gaps)} positioning gaps identified"
            else:
                gap_score = 15
                gap_notes = f"{len(gaps)} significant positioning gaps"

            module.items.append(ScoreItem(
                name="Positioning Completeness",
                description="Coverage of key positioning elements",
                max_points=35,
                actual_points=gap_score,
                notes=gap_notes,
                recommendation=f"Address the {len(gaps)} positioning gaps: {'; '.join(gaps[:2])}" if len(gaps) > 1 else "",
                page_url=homepage.url if homepage else self.context.company_website,
            ))

            # Score based on opportunities
            opp_score = min(len(opportunities) * 10, 30)
            module.items.append(ScoreItem(
                name="Competitive Opportunities",
                description="Identified opportunities for differentiation",
                max_points=30,
                actual_points=opp_score,
                notes=f"{len(opportunities)} opportunities identified" if opportunities else "Limited opportunities found",
                recommendation=f"Pursue top opportunity: {opportunities[0]}" if opportunities else "Conduct competitive research to identify differentiation angles",
                page_url=homepage.url if homepage else self.context.company_website,
            ))

            # Build recommendations
            for rec in result.get('recommendations', []):
                impact_map = {"High": Impact.HIGH, "Medium": Impact.MEDIUM, "Low": Impact.LOW}
                effort_map = {"High": Effort.HIGH, "Medium": Effort.MEDIUM, "Low": Effort.LOW}

                # Competitive positioning recommendations usually link to homepage
                homepage = self.context.get_homepage()
                page_url = homepage.url if homepage else self.context.company_website

                module.recommendations.append(Recommendation(
                    issue=rec.get("issue", ""),
                    recommendation=rec.get("recommendation", ""),
                    impact=impact_map.get(rec.get("impact", "Medium"), Impact.MEDIUM),
                    effort=effort_map.get(rec.get("effort", "Medium"), Effort.MEDIUM),
                    category="Competitive Positioning",
                    page_url=page_url,
                    kpi_impact=KPIImpact.CLOSE_RATE
                ))

        except Exception as e:
            print(f"  Error in competitor analysis: {e}")
            return self._fallback_analysis(module, competitor_data)

        return module

    async def discover_competitors(self) -> List[str]:
        """
        Discover likely competitors using LLM analysis of the company.

        Returns:
            List of competitor website URLs
        """
        if not self.llm.is_available():
            print("    LLM not available for competitor discovery")
            return []

        # Get homepage content for analysis
        homepage_content = self._get_client_content()
        if not homepage_content:
            print("    No homepage content available for discovery")
            return []

        try:
            # Use the competitor discovery prompt
            template = self.llm.load_prompt("competitor_discovery")
            prompt = self.llm.format_prompt(
                template,
                company_name=self.context.company_name,
                company_website=self.context.company_website,
                industry=self.context.industry,
                homepage_content=homepage_content
            )

            result = await self.llm.complete_json_async(prompt, max_tokens=2000)

            # Extract competitor URLs
            competitors = result.get('competitors', [])
            competitor_urls = []

            print(f"    Company identified as: {result.get('product_category', 'Unknown category')}")
            print(f"    Discovery confidence: {result.get('discovery_confidence', 'unknown')}")

            for comp in competitors:
                url = comp.get('website', '')
                name = comp.get('name', 'Unknown')
                reason = comp.get('reason', '')

                if url:
                    # Normalize URL
                    if not url.startswith('http'):
                        url = f"https://{url}"
                    competitor_urls.append(url)
                    print(f"    - {name}: {url}")
                    if reason:
                        print(f"      Reason: {reason}")

            # Store discovery metadata in context for the report
            self._discovery_result = result

            return competitor_urls

        except Exception as e:
            print(f"    Error discovering competitors: {e}")
            return []

    def _fetch_competitor_homepage(self, url: str) -> Optional[Dict]:
        """Fetch and parse a competitor's homepage."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        try:
            if not url.startswith('http'):
                url = f"https://{url}"

            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'lxml')

            data = {
                'url': url,
                'title': '',
                'h1': [],
                'h2': [],
                'meta_description': '',
                'raw_text': ''
            }

            title_tag = soup.find('title')
            data['title'] = title_tag.get_text(strip=True) if title_tag else ""

            meta_desc = soup.find('meta', attrs={'name': 'description'})
            data['meta_description'] = meta_desc.get('content', '') if meta_desc else ""

            data['h1'] = [h.get_text(strip=True) for h in soup.find_all('h1')]
            data['h2'] = [h.get_text(strip=True) for h in soup.find_all('h2')[:10]]

            for script in soup(["script", "style"]):
                script.decompose()
            data['raw_text'] = soup.get_text(separator=' ', strip=True)[:5000]

            return data

        except Exception as e:
            return {'error': str(e), 'url': url}

    def _get_client_content(self) -> str:
        """Get client homepage content for comparison."""
        homepage = self.context.get_homepage()
        if homepage:
            return f"""
Title: {homepage.title}
H1: {', '.join(homepage.h1_tags)}
H2: {', '.join(homepage.h2_tags[:5])}
Content: {homepage.raw_text[:3000]}
"""
        # Use first page if no homepage
        if self.context.pages:
            first_page = list(self.context.pages.values())[0]
            return f"""
Title: {first_page.title}
H1: {', '.join(first_page.h1_tags)}
Content: {first_page.raw_text[:3000]}
"""
        return ""

    def _format_competitor_data(self, competitor_data: List[Dict]) -> str:
        """Format competitor data for the prompt."""
        comp_text = ""
        for i, comp in enumerate(competitor_data, 1):
            if 'error' in comp:
                comp_text += f"\n### Competitor {i}: {comp.get('url', 'Unknown')}\nError: {comp['error']}\n"
            else:
                comp_text += f"""
### Competitor {i}: {comp.get('url', 'Unknown')}
Title: {comp.get('title', '')}
H1: {', '.join(comp.get('h1', []))}
H2: {', '.join(comp.get('h2', [])[:5])}
Meta Description: {comp.get('meta_description', '')}
Content Preview: {comp.get('raw_text', '')[:2000]}
"""
        return comp_text

    def _fallback_analysis(self, module: ModuleScore, competitor_data: List[Dict]) -> ModuleScore:
        """Provide fallback when LLM unavailable."""
        module.items = [
            ScoreItem("Competitor Analysis", "Analysis of competitive positioning", 100, 50, "LLM analysis unavailable")
        ]
        module.analysis_text = f"Analyzed {len(competitor_data)} competitors. Detailed comparison requires LLM access."
        module.raw_data = {'competitors': [{'url': c.get('url', ''), 'title': c.get('title', '')} for c in competitor_data]}
        return module

    def self_audit(self) -> bool:
        """Validate competitor analysis quality."""
        if not super().self_audit():
            return False

        # Should have analyzed at least one competitor
        raw_data = self.analysis.module_score.raw_data
        if not raw_data.get('competitors'):
            return False

        return True
