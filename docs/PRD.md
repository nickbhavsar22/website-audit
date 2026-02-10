# Website Audit Tool - Product Requirements Document

## Version 2.0 - Agentic Architecture

### Overview

The Website Audit Tool is a comprehensive marketing audit system for B2B SaaS companies. Version 2.0 introduces an **agentic architecture** with autonomous agents, shared context, self-audit capabilities, and screenshot integration.

### Architecture

```
website-audit/
├── orchestrator/                 # Central coordination layer
│   ├── orchestrator.py           # Main agent coordinator
│   ├── context_store.py          # Shared state management
│   └── revision_manager.py       # Self-audit revision cycles
├── agents/                       # Autonomous analysis agents
│   ├── base_agent.py             # Abstract base class
│   ├── website_agent.py          # Enhanced web crawler
│   ├── positioning_agent.py      # Messaging analysis
│   ├── seo_agent.py              # Technical SEO
│   ├── conversion_agent.py       # CTA/form analysis
│   ├── content_agent.py          # Content quality
│   ├── trust_agent.py            # Trust signals
│   ├── social_agent.py           # Social media
│   ├── segmentation_agent.py     # Industry/segment coverage
│   ├── resource_hub_agent.py     # Landing page analysis
│   ├── top5_pages_agent.py       # Critical page grading
│   ├── competitor_agent.py       # Competitive analysis
│   └── critique_agent.py         # Quality assurance
├── utils/                        # Shared utilities
│   ├── scraper.py                # Web scraping
│   ├── scoring.py                # Scoring framework
│   ├── report.py                 # HTML generation
│   ├── logo.py                   # Logo extraction
│   ├── llm_client.py             # LLM wrapper
│   └── screenshot.py             # Playwright integration
├── templates/
│   └── report.html               # Report template
├── prompts/                      # LLM prompt templates
├── clients/                      # Per-client configuration
│   └── {client-name}/
│       ├── config.txt
│       └── output/
├── docs/
│   └── PRD.md                    # This document
├── audit.py                      # CLI entry point
└── requirements.txt
```

---

## Agents

### 1. WebsiteAgent (website)
**Purpose:** Enhanced web crawling with segment detection

**Capabilities:**
- Crawls up to 20 pages (configurable)
- Priority path detection (products, solutions, pricing, etc.)
- Segment/industry page discovery
- Page type classification
- Social link extraction

**Dependencies:** None (runs first)

**Weight:** 0x (data collection only)

---

### 2. PositioningAgent (positioning)
**Purpose:** Analyzes positioning and messaging effectiveness

**Evaluates:**
- Value proposition clarity (20 pts)
- Differentiation (20 pts)
- ICP alignment (15 pts)
- Pain point articulation (15 pts)
- Outcome focus (15 pts)
- Messaging consistency (15 pts)

**Dependencies:** website

**Weight:** 2.0x (highest priority)

---

### 3. SEOAgent (seo)
**Purpose:** Technical SEO and performance analysis

**Evaluates:**
- Meta tags (15 pts)
- Heading structure (10 pts)
- Page speed (20 pts)
- Mobile responsiveness (15 pts)
- Image optimization (10 pts)
- URL structure (10 pts)
- Internal linking (10 pts)
- Schema markup (10 pts)

**Dependencies:** website

**Weight:** 1.0x

---

### 4. ConversionAgent (conversion)
**Purpose:** CTA and conversion path analysis

**Evaluates:**
- CTA visibility (20 pts)
- CTA copy quality (15 pts)
- Form optimization (15 pts)
- Trust signals near conversion (15 pts)
- Path clarity (15 pts)
- Multiple entry points (10 pts)
- Friction reduction (10 pts)

**Dependencies:** website

**Weight:** 1.0x

---

### 5. ContentAgent (content)
**Purpose:** Content quality assessment

**Evaluates:**
- Content freshness (15 pts)
- Depth & value (20 pts)
- Readability (15 pts)
- Visual support (15 pts)
- Content variety (15 pts)
- Thought leadership (20 pts)

**Dependencies:** website

**Weight:** 1.0x

---

### 6. TrustAgent (trust)
**Purpose:** Trust and credibility signal analysis

**Evaluates:**
- Customer logos (15 pts)
- Testimonials (20 pts)
- Case studies (20 pts)
- Awards/recognition (10 pts)
- Team/about page (10 pts)
- Security/compliance (10 pts)
- Press/media (10 pts)
- Reviews/ratings (5 pts)

**Dependencies:** website

**Weight:** 1.0x

---

### 7. SocialAgent (social)
**Purpose:** Social media presence evaluation

**Evaluates:**
- Social presence (10 pts)
- Posting frequency (15 pts)
- Engagement rate (25 pts)
- Content mix (15 pts)
- Brand consistency (15 pts)
- Best practices (20 pts)

**Dependencies:** website

**Weight:** 1.0x

---

### 8. SegmentationAgent (segmentation)
**Purpose:** Target segment/industry coverage analysis

**Evaluates:**
- Segment clarity (20 pts)
- Pain point coverage (25 pts)
- Segment-specific messaging (20 pts)
- Industry page quality (20 pts)
- Use case articulation (15 pts)

**Dependencies:** website

**Weight:** 1.0x

---

### 9. ResourceHubAgent (resource_hub)
**Purpose:** Landing page and gated content analysis

**Evaluates:**
- Landing page quality (25 pts)
- Gated content strategy (20 pts)
- Form optimization (20 pts)
- Content offer variety (20 pts)
- Lead magnet effectiveness (15 pts)

**Dependencies:** website, conversion

**Weight:** 1.0x

---

### 10. Top5PagesAgent (top5_pages)
**Purpose:** Critical page grading with screenshots

**Analyzes:**
- Homepage
- Product/Platform page
- Solutions page
- Pricing page
- About page

Each page receives:
- Letter grade (A-F)
- Numeric score (0-100)
- Strengths list
- Weaknesses list
- Recommendations
- Full-page screenshot

**Dependencies:** website, positioning

**Weight:** 1.5x

---

### 11. CompetitorAgent (competitor)
**Purpose:** Competitive positioning analysis

**Provides:**
- Competitor headline extraction
- Value proposition comparison
- Key differentiators
- Target audience analysis
- Positioning gaps
- Positioning opportunities

**Dependencies:** website, positioning

**Weight:** 1.0x

---

### 12. CritiqueAgent (critique)
**Purpose:** Quality assurance and revision coordination

**Responsibilities:**
- Review all agent analyses for quality
- Check for cross-agent consistency
- Request revisions from underperforming agents
- Ensure overall report coherence

**Dependencies:** All other agents

**Weight:** 0x (meta-agent)

---

## Execution Flow

### Phase 1: Website Crawling
- WebsiteAgent crawls up to 20 pages
- Classifies page types
- Extracts social links
- Detects segment mentions

### Phase 2: Primary Analysis (Parallel)
- PositioningAgent
- SEOAgent
- ConversionAgent
- ContentAgent
- TrustAgent
- SocialAgent
- SegmentationAgent

### Phase 3: Secondary Analysis
- ResourceHubAgent
- Top5PagesAgent

### Phase 4: Screenshot Capture
- Full-page screenshots for critical pages
- Element screenshots for issues

### Phase 5: Competitor Analysis
- CompetitorAgent (if competitors configured)

### Phase 6: Critique & Revision
- CritiqueAgent reviews all analyses
- Requests revisions (up to 3 cycles)
- Ensures quality standards

### Phase 7: Report Generation
- Aggregate all scores
- Generate HTML report
- Include screenshots

---

## Shared Context Store

The ContextStore enables agent coordination by providing:

```python
ContextStore:
  # Configuration
  - company_name, company_website, industry
  - competitors, max_pages

  # Crawled Data
  - pages: Dict[url, PageData]

  # Screenshots
  - screenshots: Dict[key, ScreenshotData]

  # Agent Results
  - analyses: Dict[agent_name, AgentAnalysis]

  # Segmentation
  - identified_segments: List[SegmentInfo]

  # Critical Pages
  - critical_pages: List[CriticalPage]

  # Resource Hub
  - landing_pages, gated_content
```

---

## Self-Audit & Revision

### Quality Thresholds
- Minimum analysis length: 100 characters
- Minimum score items: 3
- Minimum recommendations: 2 (when LLM available)
- Maximum empty notes: 2

### Revision Process
1. CritiqueAgent reviews all completed analyses
2. Identifies agents needing improvement
3. Requests specific revisions with suggestions
4. Agents re-run with feedback context
5. Up to 3 revision cycles allowed

---

## CLI Usage

```bash
# Client-based (recommended)
python audit.py --client avtal --verbose

# Config-based (legacy)
python audit.py --config path/to/config.txt --output ./output/

# Options
--client, -C    Client folder name (clients/<name>/config.txt)
--config, -c    Direct path to config.txt
--output, -o    Output directory
--verbose, -v   Enable verbose output
--max-pages, -m Maximum pages to crawl (default: 20)
--no-screenshots Skip screenshot capture
```

---

## Configuration (config.txt)

```
company_name=Acme Corp
company_website=https://acme.com
industry=B2B SaaS
audit_date=02-02-2026
analyst_name=John Doe
analyst_company=Bhavsar Growth Consulting
analyst_website=https://growth.llc
max_pages=20
competitors=competitor1.com, competitor2.com, competitor3.com
```

---

## Report Output

The HTML report includes:

1. **Cover Page** - Company logo, audit metadata
2. **Executive Summary** - Overall grade, strengths, gaps, quick wins
3. **Top 5 Critical Pages** - Screenshots with grades
4. **Target Segment Analysis** - Segment coverage cards
5. **Module Sections** - Detailed scoring per module
6. **Competitive Positioning** - Side-by-side comparison
7. **Prioritized Action Plan** - All recommendations sorted
8. **Internal Systems Placeholders** - GA4, HubSpot, Email
9. **Methodology** - Scoring framework explanation

---

## Dependencies

```
requests>=2.31.0
beautifulsoup4>=4.12.0
httpx>=0.25.0
jinja2>=3.1.0
anthropic>=0.18.0
lxml>=5.0.0
Pillow>=10.0.0
playwright>=1.40.0
```

Post-install:
```bash
playwright install chromium
```

---

## Version History

- **v1.0** - Sequential pipeline architecture
- **v2.0** - Agentic architecture with:
  - Autonomous agents with self-audit
  - Shared context store
  - Screenshot integration
  - 3 new modules (Segmentation, Resource Hub, Top 5 Pages)
  - Critique and revision cycles
  - Enhanced crawling (20 pages, segment detection)
