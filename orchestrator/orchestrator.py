"""Main orchestrator for coordinating audit agents."""

import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type
from datetime import datetime

logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))

from .context_store import ContextStore, AgentStatus, ScreenshotData
from .revision_manager import RevisionManager
from utils.llm_client import LLMClient
from utils.scoring import AuditReport
from utils.screenshot import ScreenshotManager


class Orchestrator:
    """
    Main coordinator for the agentic audit system.

    Manages:
    - Agent execution order based on dependencies
    - Screenshot capture requests
    - Revision cycles via CritiqueAgent
    - Final report generation
    """

    def __init__(
        self,
        context: ContextStore,
        llm_client: Optional[LLMClient] = None,
        verbose: bool = False,
        progress_callback=None
    ):
        """
        Initialize the orchestrator.

        Args:
            context: Shared context store with configuration
            llm_client: LLM client for agents
            verbose: Enable verbose output
            progress_callback: Optional callback(phase, status, detail) for progress updates
        """
        self.context = context
        self.llm = llm_client or LLMClient()
        self.verbose = verbose
        self.progress_callback = progress_callback
        self.revision_manager = RevisionManager(max_revisions=context.max_revisions)
        self.screenshot_manager: Optional[ScreenshotManager] = None
        self._agents: Dict[str, 'BaseAgent'] = {}

    def register_agent(self, agent_class: Type['BaseAgent']):
        """
        Register an agent class with the orchestrator.

        Args:
            agent_class: Agent class to register
        """
        agent = agent_class(self.context, self.llm)
        self._agents[agent.agent_name] = agent

    def register_all_agents(self):
        """Register all standard agents."""
        from agents.website_agent import WebsiteAgent
        from agents.positioning_agent import PositioningAgent
        from agents.seo_agent import SEOAgent
        from agents.conversion_agent import ConversionAgent
        from agents.content_agent import ContentAgent
        from agents.trust_agent import TrustAgent
        from agents.social_agent import SocialAgent
        from agents.segmentation_agent import SegmentationAgent
        from agents.resource_hub_agent import ResourceHubAgent
        from agents.top5_pages_agent import Top5PagesAgent
        from agents.competitor_agent import CompetitorAgent
        from agents.critique_agent import CritiqueAgent
        from agents.deep_research_agent import DeepResearchAgent
        from agents.prompt_visibility_agent import PromptVisibilityAgent
        from agents.social_listening_agent import SocialListeningAgent

        agent_classes = [
            WebsiteAgent,
            PositioningAgent,
            SEOAgent,
            ConversionAgent,
            ContentAgent,
            TrustAgent,
            SocialAgent,
            SegmentationAgent,
            ResourceHubAgent,
            Top5PagesAgent,
            CompetitorAgent,
            CritiqueAgent,
            DeepResearchAgent,
            PromptVisibilityAgent,
            SocialListeningAgent,
        ]

        for agent_class in agent_classes:
            self.register_agent(agent_class)

    def get_runnable_agents(self) -> List['BaseAgent']:
        """Get agents that can run (dependencies satisfied)."""
        runnable = []
        for agent in self._agents.values():
            if agent.can_run():
                analysis = self.context.get_analysis(agent.agent_name)
                if not analysis or analysis.status == AgentStatus.PENDING:
                    runnable.append(agent)
        return runnable

    def get_execution_order(self) -> List[str]:
        """
        Determine execution order based on dependencies.

        Returns topologically sorted list of agent names.
        """
        # Build dependency graph
        in_degree = {name: 0 for name in self._agents.keys()}
        graph = {name: [] for name in self._agents.keys()}

        for name, agent in self._agents.items():
            for dep in agent.dependencies:
                if dep in graph:
                    graph[dep].append(name)
                    in_degree[name] += 1

        # Topological sort
        queue = [name for name, degree in in_degree.items() if degree == 0]
        order = []

        while queue:
            current = queue.pop(0)
            order.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return order

    async def capture_pending_screenshots(self):
        """Capture any pending screenshot requests."""
        if self.screenshot_manager is None:
            try:
                self.screenshot_manager = ScreenshotManager()
            except ImportError:
                logger.warning("Playwright not available, skipping screenshots")
                return

        pending = [
            s for s in self.context.screenshots.values()
            if not s.base64_data and not s.notes.startswith("Error")
        ]

        for screenshot in pending:
            logger.info("Capturing screenshot: %s", screenshot.url)
            try:
                if screenshot.element_selector:
                    result = await self.screenshot_manager.capture_element(
                        screenshot.url, screenshot.element_selector
                    )
                else:
                    result = await self.screenshot_manager.capture_full_page(screenshot.url)

                screenshot.base64_data = result.base64_data
                screenshot.width = result.width
                screenshot.height = result.height
                screenshot.captured_at = result.captured_at
                if result.error:
                    screenshot.notes = f"Error: {result.error}"

            except Exception as e:
                screenshot.notes = f"Error: {e}"

    def capture_screenshots_sync(self):
        """Synchronous wrapper for screenshot capture."""
        import asyncio

        async def _capture():
            await self.capture_pending_screenshots()
            if self.screenshot_manager:
                await self.screenshot_manager.close()

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(_capture())

    def _link_screenshots_to_critical_pages(self):
        """Link captured screenshots to their corresponding critical pages."""
        def normalize_url(url: str) -> str:
            """Normalize URL for comparison."""
            return url.rstrip('/').lower()

        for cp in self.context.critical_pages:
            cp_url_normalized = normalize_url(cp.url)

            # Look through all screenshots for a match
            for key, screenshot in self.context.screenshots.items():
                screenshot_url_normalized = normalize_url(screenshot.url)

                # Check if URLs match and screenshot has data
                if screenshot_url_normalized == cp_url_normalized and screenshot.base64_data:
                    cp.screenshot = screenshot
                    logger.debug("Linked screenshot to %s page", cp.page_type)
                    break

        # Report on linking status
        linked_count = sum(1 for cp in self.context.critical_pages if cp.screenshot and cp.screenshot.base64_data)
        total_count = len(self.context.critical_pages)
        logger.info("Screenshots linked: %d/%d critical pages", linked_count, total_count)

    async def run_phase(self, phase_name: str, agent_names: List[str]):
        """
        Run a specific phase of agents asynchronously.

        Args:
            phase_name: Name of the phase for logging
            agent_names: List of agent names to run
        """
        if self.progress_callback:
            self.progress_callback(phase=phase_name, status="started", detail=f"Running {len(agent_names)} agents")

        logger.info("Phase: %s", phase_name)

        tasks = []
        for name in agent_names:
            if name not in self._agents:
                continue

            agent = self._agents[name]
            if not agent.can_run():
                missing = agent.get_missing_dependencies()
                logger.debug("Skipping %s - dependencies not met: %s", name, missing)
                continue

            analysis = self.context.get_analysis(name)
            if analysis and analysis.status == AgentStatus.COMPLETED:
                logger.debug("Skipping %s - already completed", name)
                continue

            tasks.append(agent.execute())

        if tasks:
            await asyncio.gather(*tasks)

            # Print scores after completion
            for name in agent_names:
                if name in self._agents:
                    agent = self._agents[name]
                    if agent.analysis and agent.analysis.module_score:
                        score = agent.analysis.module_score
                        outcome = score.outcome.value
                        logger.debug("%s Score: %s/%s (%s)", name, score.actual_points, score.max_points, outcome)

        if self.progress_callback:
            self.progress_callback(phase=phase_name, status="completed", detail="Completed")

    async def run_audit(self) -> AuditReport:
        """
        Execute the full audit workflow asynchronously.

        Returns:
            AuditReport with all module scores
        """
        logger.info("WEBSITE AUDIT - AGENTIC SYSTEM")
        logger.info("Target: %s | Website: %s | Date: %s",
                     self.context.company_name, self.context.company_website, self.context.audit_date)

        # Register all agents
        self.register_all_agents()

        # Phase 1: Website Crawling
        await self.run_phase("Website Crawling", ['website'])

        # Phase 1.5: Deep Research (needs website content, builds context for others)
        await self.run_phase("Deep Research", ['deep_research'])

        # Phase 2: Primary Analysis (parallel-capable)
        analysis_agents = [
            'positioning', 'seo', 'conversion', 'content',
            'trust', 'social', 'segmentation',
            'prompt_visibility', 'social_listening'
        ]
        await self.run_phase("Primary Analysis", analysis_agents)

        # Phase 3: Secondary Analysis
        secondary_agents = ['resource_hub', 'top5_pages']
        await self.run_phase("Secondary Analysis", secondary_agents)

        # Capture any pending screenshots
        if self.progress_callback:
            self.progress_callback(phase="Screenshots", status="started", detail="Capturing page screenshots")
        logger.info("Capturing Screenshots")
        await self.capture_pending_screenshots()

        # Link screenshots to critical pages
        self._link_screenshots_to_critical_pages()

        # Phase 4: Competitor Analysis (always run - will discover if not provided)
        await self.run_phase("Competitor Analysis", ['competitor'])

        # Phase 5: Critique and Revision
        if self.progress_callback:
            self.progress_callback(phase="Quality Review", status="started", detail="Running critique and revision cycles")
        await self.run_revision_cycles()

        # Phase 6: Strategic Synthesis (The "Lead Consultant" Phase)
        if self.progress_callback:
            self.progress_callback(phase="Synthesis", status="started", detail="Synthesizing audit findings")
        logger.info("Phase: Lead Consultant Synthesis")
        strategic_friction = self.synthesize_findings()

        # Build final report
        report = self.build_report()
        report.strategic_friction = strategic_friction

        if self.progress_callback:
            self.progress_callback(phase="Complete", status="completed", detail="Audit finished")

        return report

    def synthesize_findings(self):
        """
        Analyze cross-agent patterns to identify the Strategic Friction Point.
        This acts as the 'Lead Consultant' connecting the dots.
        """
        logger.info("Synthesizing audit findings...")
        from utils.scoring import StrategicFrictionPoint, ConsultingOutcome
        
        # Get all completed analyses
        analyses = {name: self.context.get_analysis(name) for name in self._agents}
        
        # Extract scores/outcomes
        scores = {}
        for name, analysis in analyses.items():
            if analysis and analysis.module_score:
                scores[name] = analysis.module_score.outcome

        # Default friction point if logic below doesn't match
        friction = StrategicFrictionPoint(
            title="General Performance Gap",
            description="The audit identified multiple areas for improvement across SEO, Trust, and Positioning.",
            primary_symptom="Lower than expected growth",
            business_impact="Inefficient marketing spend"
        )

        # Logic 1: The "Leaky Bucket" (Good SEO/Traffic, Low Review/Trust)
        seo_good = scores.get('seo') in [ConsultingOutcome.AUTHORITY, ConsultingOutcome.LEADER]
        trust_bad = scores.get('trust') in [ConsultingOutcome.GAP_AUTHORITY, ConsultingOutcome.GAP_CONVERSION]
        
        if seo_good and trust_bad:
            logger.info("Identified Pattern: The Leaky Bucket")
            friction = StrategicFrictionPoint(
                title="The 'Leaky Bucket' Effect",
                description="You are successfully driving traffic (High SEO/Visibility), but failing to convert it due to a critical lack of Trust signals.",
                primary_symptom="High Rank, Low Revenue",
                business_impact="You are paying a 'Trust Tax' on every visitor, wasting ad spend and organic potential."
            )
            return friction

        # Logic 2: The "Invisible Expert" (Good Content/Trust, Bad SEO)
        content_good = scores.get('content') in [ConsultingOutcome.AUTHORITY, ConsultingOutcome.LEADER]
        seo_bad = scores.get('seo') in [ConsultingOutcome.GAP_VISIBILITY, ConsultingOutcome.RISK_DILUTION]

        if content_good and seo_bad:
            logger.info("Identified Pattern: The Invisible Expert")
            friction = StrategicFrictionPoint(
                title="The Invisible Expert",
                description="Your content and authority are world-class, but your technical foundation prevents buyers from finding you.",
                primary_symptom="Great Product, No Traffic",
                business_impact="Your expertise is being drowned out by inferior competitors with better distribution."
            )
            return friction
        
        # Logic 3: The "Commodity Trap" (Good Traffic, Weak Positioning)
        pos_bad = scores.get('positioning') in [ConsultingOutcome.RISK_COMMODITY, ConsultingOutcome.GAP_AUTHORITY]
        
        if seo_good and pos_bad:
            logger.info("Identified Pattern: The Commodity Trap")
            friction = StrategicFrictionPoint(
                title="The Commodity Trap",
                description="You are visible, but your messaging fails to differentiate you from cheaper competitors.",
                primary_symptom="Price-based Sales Battles",
                business_impact="You are forced to compete on price rather than value, eroding margins."
            )
            return friction
            
        logger.info("Synthesis Complete: %s", friction.title)
        return friction

    async def run_revision_cycles(self):
        """Run critique and revision cycles asynchronously."""
        logger.info("Critique & Revision Phase")

        critique_agent = self._agents.get('critique')
        if not critique_agent:
            logger.warning("Critique agent not available")
            return

        for cycle in range(self.context.max_revisions):
            self.revision_manager.start_new_cycle()
            logger.info("Revision Cycle %d/%d", cycle + 1, self.context.max_revisions)

            # Run critique
            await critique_agent.execute()

            # Check for revision requests
            pending = self.revision_manager.get_pending_revisions()
            if not pending:
                logger.info("No revisions needed - all agents passed critique")
                break

            # Process revision requests (can be parallelized too)
            revision_tasks = []
            for request in pending:
                agent_name = request.agent_name
                if agent_name in self._agents:
                    agent = self._agents[agent_name]
                    logger.info("Revising %s: %s", agent_name, request.reason)
                    
                    # We need to wrap the revision logic since it returns a score which we need to record
                    async def process_revision(agt, req):
                        revised_score = await agt.revise(req.reason, req.suggested_improvements)
                        success = agt.self_audit()
                        self.revision_manager.record_revision_result(
                            agent_name=agt.agent_name,
                            success=success,
                            improvements_made=req.suggested_improvements if success else [],
                            remaining_issues=[] if success else ["Revision did not resolve issues"]
                        )
                    
                    revision_tasks.append(process_revision(agent, request))

            if revision_tasks:
                await asyncio.gather(*revision_tasks)

            if not self.revision_manager.should_continue_revising(self.context):
                break

        # Print revision summary
        summary = self.revision_manager.get_cycle_summary()
        logger.info("Revision Summary: total=%d, successful=%d",
                     summary['total_revisions_completed'], summary['successful_revisions'])

    def build_report(self) -> AuditReport:
        """Build the final audit report from all agent analyses."""
        report = AuditReport(
            company_name=self.context.company_name,
            company_website=self.context.company_website,
            audit_date=self.context.audit_date,
            analyst_name=self.context.analyst_name,
            analyst_company=self.context.analyst_company,
            client_logo=self.context.client_logo_b64,
            analyst_logo=self.context.analyst_logo_b64
        )

        # Add module scores from each agent
        # Order matters for report display
        agent_order = [
            'positioning', 'seo', 'conversion', 'content',
            'trust', 'social', 'segmentation', 'resource_hub',
            'prompt_visibility', 'social_listening',
            'top5_pages', 'competitor'
        ]

        for agent_name in agent_order:
            analysis = self.context.get_analysis(agent_name)
            if analysis and analysis.module_score:
                report.modules.append(analysis.module_score)

        return report

    def get_status_summary(self) -> Dict:
        """Get a summary of the audit status."""
        completed = []
        pending = []
        failed = []

        for name, agent in self._agents.items():
            analysis = self.context.get_analysis(name)
            if analysis:
                if analysis.status == AgentStatus.COMPLETED:
                    completed.append(name)
                elif analysis.status == AgentStatus.FAILED:
                    failed.append(name)
                else:
                    pending.append(name)
            else:
                pending.append(name)

        return {
            'completed': completed,
            'pending': pending,
            'failed': failed,
            'total_agents': len(self._agents),
            'pages_crawled': len(self.context.pages),
            'screenshots': len(self.context.screenshots),
            'revision_summary': self.revision_manager.get_cycle_summary()
        }
