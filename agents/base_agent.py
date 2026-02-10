"""Base agent class for all audit agents."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.context_store import ContextStore, AgentAnalysis, AgentStatus
from utils.llm_client import LLMClient
from utils.scoring import ModuleScore


class BaseAgent(ABC):
    """
    Abstract base class for all audit agents.

    Each agent:
    - Reads from the shared ContextStore
    - Performs analysis using LLM and/or heuristics
    - Writes results back to ContextStore
    - Can request additional data (screenshots, more crawling)
    - Implements self-audit to validate results
    """

    # Class attributes that subclasses should override
    agent_name: str = "base"
    agent_description: str = "Base agent"
    dependencies: List[str] = []  # Other agents that must complete first
    weight: float = 1.0  # Scoring weight for this module

    def __init__(self, context: ContextStore, llm_client: Optional[LLMClient] = None, verbose: bool = False):
        """
        Initialize the agent.

        Args:
            context: Shared context store
            llm_client: Optional LLM client (will create one if not provided)
            verbose: Enable verbose logging
        """
        self.context = context
        self.llm = llm_client or LLMClient()
        self.verbose = verbose
        self._analysis: Optional[AgentAnalysis] = None

    @property
    def analysis(self) -> AgentAnalysis:
        """Get or create the agent's analysis record."""
        if self._analysis is None:
            existing = self.context.get_analysis(self.agent_name)
            if existing:
                self._analysis = existing
            else:
                self._analysis = AgentAnalysis(
                    agent_name=self.agent_name,
                    status=AgentStatus.PENDING
                )
        return self._analysis

    def can_run(self) -> bool:
        """
        Check if all dependencies are satisfied.

        Returns:
            True if the agent can run, False otherwise
        """
        for dep in self.dependencies:
            dep_analysis = self.context.get_analysis(dep)
            if not dep_analysis or dep_analysis.status != AgentStatus.COMPLETED:
                return False
        return True

    def get_missing_dependencies(self) -> List[str]:
        """Get list of dependencies that are not yet completed."""
        missing = []
        for dep in self.dependencies:
            dep_analysis = self.context.get_analysis(dep)
            if not dep_analysis or dep_analysis.status != AgentStatus.COMPLETED:
                missing.append(dep)
        return missing

    @abstractmethod
    async def run(self) -> ModuleScore:
        """
        Execute the agent's analysis asynchronously.

        Returns:
            ModuleScore with the analysis results
        """
        pass

    async def execute(self) -> AgentAnalysis:
        """
        Execute the agent with proper state management.

        This is the main entry point for running an agent.
        It handles status updates and error handling.

        Returns:
            AgentAnalysis with results
        """
        if not self.can_run():
            missing = self.get_missing_dependencies()
            self.analysis.status = AgentStatus.PENDING
            self.analysis.errors.append(f"Dependencies not met: {', '.join(missing)}")
            return self.analysis

        self.analysis.status = AgentStatus.RUNNING
        self.analysis.started_at = datetime.now().isoformat()
        self.context.set_analysis(self.analysis)

        try:
            print(f"  Running {self.agent_name} agent...")
            
            # 1. Chain of Thought: Generate plan first
            self.analysis.hidden_plan = self._generate_cot_plan()
            if self.verbose:
                print(f"    CoT Plan: {self.analysis.hidden_plan[:100]}...")

            # 2. Execute Analysis
            module_score = await self.run()

            self.analysis.module_score = module_score
            self.analysis.analysis_text = module_score.analysis_text
            self.analysis.raw_data = module_score.raw_data

            # Run self-audit
            self.analysis.self_audit_passed = self.self_audit()

            if self.analysis.self_audit_passed:
                self.analysis.status = AgentStatus.COMPLETED
            else:
                self.analysis.status = AgentStatus.NEEDS_REVISION

            self.analysis.completed_at = datetime.now().isoformat()

        except Exception as e:
            self.analysis.status = AgentStatus.FAILED
            self.analysis.errors.append(str(e))
            print(f"  Error in {self.agent_name} agent: {e}")

        self.context.set_analysis(self.analysis)
        return self.analysis

    def _generate_cot_plan(self) -> str:
        """
        Generate a hidden plan (Chain of Thought) before execution.
        Subclasses can override this or we can prompt the LLM here.
        """
        return f"Analyzing {self.agent_name} for {self.context.company_name}..."

    def self_audit(self) -> bool:
        """
        Review the agent's own results for quality.

        Override this method to implement custom validation logic.

        Returns:
            True if results pass quality check, False if revision needed
        """
        # Default implementation: check for basic completeness
        if not self.analysis.module_score:
            return False

        score = self.analysis.module_score

        # Check that we have score items
        if not score.items:
            return False

        # Check that we have analysis text
        if not score.analysis_text or len(score.analysis_text) < 50:
            return False

        # Check legacy business_impact
        # (New constraint: Ensure recommendations have business impact)
        # We enforce this in the specific agents, but base can check if any exist

        return True

    def request_screenshot(self, url: str, selector: Optional[str] = None) -> bool:
        """
        Request a screenshot to be captured.

        Args:
            url: URL to capture
            selector: Optional CSS selector for element screenshot

        Returns:
            True if request was made successfully
        """
        # This will be handled by the orchestrator
        # For now, just return True to indicate the request was noted
        from orchestrator.context_store import ScreenshotData
        screenshot = ScreenshotData(
            url=url,
            screenshot_type="element" if selector else "full_page",
            base64_data="",  # Will be filled by orchestrator
            element_selector=selector or ""
        )
        # Mark as pending
        self.context.add_screenshot(screenshot)
        return True

    def request_additional_data(self, urls: List[str]) -> List[str]:
        """
        Request additional URLs to be crawled.

        Args:
            urls: List of URLs to crawl

        Returns:
            List of URLs that were added to the queue
        """
        return self.context.request_additional_crawl(urls)

    def get_page_content(self, url: str) -> Optional[str]:
        """Helper to get raw text content from a page."""
        page = self.context.get_page(url)
        return page.raw_text if page else None

    def get_all_pages_content(self, max_chars: int = 15000) -> str:
        """Helper to aggregate content from all pages."""
        content_parts = []
        total_chars = 0

        for url, page in self.context.pages.items():
            page_content = f"\n--- PAGE: {url} ---\nTitle: {page.title}\n"
            page_content += f"H1: {', '.join(page.h1_tags)}\n"
            page_content += f"H2: {', '.join(page.h2_tags[:5])}\n"
            page_content += f"Content: {page.raw_text[:2500]}\n"

            if total_chars + len(page_content) > max_chars:
                break

            content_parts.append(page_content)
            total_chars += len(page_content)

        return '\n'.join(content_parts)

    def get_priority_pages_content(self, max_chars: int = 15000) -> str:
        """Helper to get content from priority pages only."""
        priority_patterns = ['', 'about', 'product', 'solutions', 'pricing', 'why', 'platform', 'features']
        content_parts = []
        total_chars = 0

        for url, page in self.context.pages.items():
            url_lower = url.lower()
            is_priority = any(p in url_lower for p in priority_patterns)
            is_home = url.rstrip('/') == self.context.company_website.rstrip('/')

            if is_priority or is_home:
                page_content = f"\n--- PAGE: {url} ---\nTitle: {page.title}\n"
                page_content += f"H1: {', '.join(page.h1_tags)}\n"
                page_content += f"H2: {', '.join(page.h2_tags[:5])}\n"
                page_content += f"Content: {page.raw_text[:3000]}\n"

                if total_chars + len(page_content) > max_chars:
                    break

                content_parts.append(page_content)
                total_chars += len(page_content)

        return '\n'.join(content_parts)

    async def revise(self, feedback: str, suggestions: List[str]) -> ModuleScore:
        """
        Revise the analysis based on critique feedback.

        Args:
            feedback: Overall feedback on what to improve
            suggestions: Specific improvement suggestions

        Returns:
            Revised ModuleScore
        """
        self.analysis.revision_count += 1
        self.analysis.status = AgentStatus.RUNNING

        # Default implementation: just re-run
        # Subclasses can override to incorporate feedback
        return await self.run()

    def get_status_summary(self) -> str:
        """Get a human-readable status summary."""
        status = self.analysis.status.value
        if self.analysis.module_score:
            score = self.analysis.module_score
            outcome = score.outcome.value
            return f"{self.agent_name}: {status} - {outcome}"
        return f"{self.agent_name}: {status}"
