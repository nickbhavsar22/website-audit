#!/usr/bin/env python3
"""
Website Audit Tool - Agentic Architecture

A comprehensive marketing audit tool for B2B SaaS companies using
an autonomous multi-agent system with self-auditing capabilities.

Usage:
    python audit.py --client <client-name> [--verbose] [--max-pages 20]
    python audit.py --config path/to/config.txt [--output ./output/] [--verbose]
"""

import argparse
import os
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Load .env file if present
def load_env_file():
    """Load environment variables from .env file."""
    env_paths = [
        Path(__file__).parent / ".env",
        Path.cwd() / ".env"
    ]
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
            print(f"Loaded environment from: {env_path}")
            return True
    return False

load_env_file()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator.context_store import ContextStore
from orchestrator.orchestrator import Orchestrator
from utils.llm_client import LLMClient
from utils.report import generate_html_report
from utils.logo import extract_logo_url, get_logo_as_base64


def parse_config(config_path: str) -> dict:
    """Parse the configuration file."""
    config = {}
    with open(config_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines, comments, and markdown-style content
            if not line or line.startswith('#') or line.startswith('`'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    return config


def setup_context_from_config(config: dict, max_pages: int = 20) -> ContextStore:
    """Create and configure ContextStore from config dict."""
    context = ContextStore()

    context.company_name = config.get('company_name', 'Unknown Company')
    context.company_website = config.get('company_website', '').rstrip('/')
    context.industry = config.get('industry', 'B2B SaaS')
    context.audit_date = config.get('audit_date', datetime.now().strftime('%m-%d-%Y'))
    context.analyst_name = config.get('analyst_name', '')
    context.analyst_company = config.get('analyst_company', 'Bhavsar Growth Consulting')
    context.analyst_website = config.get('analyst_website', 'https://growth.llc')
    context.max_pages = int(config.get('max_pages', max_pages))

    # Parse competitors if provided
    if 'competitors' in config:
        context.competitors = [c.strip() for c in config['competitors'].split(',') if c.strip()]

    return context


def extract_logos(context: ContextStore):
    """Extract and store logos for the report."""
    print("\n" + "-"*50)
    print("  Extracting Logos")
    print("-"*50)
    
    assets_dir = Path(__file__).parent.absolute() / "assets" / "logos"

    # --- Client Logo ---
    # First check for local client override
    client_local_dir = assets_dir / "clients" / context.company_name
    client_logo_found = False
    
    if client_local_dir.exists():
        # Look for images
        images = list(client_local_dir.glob("*.[pj][np][g]*")) # simplistic glob for png, jpg, jpeg
        if images:
            print(f"  Found local client logos in {client_local_dir}")
            # Pick the first one for now, or maybe the largest?
            best_client_logo = images[0]
            print(f"    Using: {best_client_logo.name}")
            
            # For HTML report
            from utils.logo import get_local_logo_as_base64
            res = get_local_logo_as_base64(best_client_logo)
            if res:
                context.client_logo_b64 = res[0]
                client_logo_found = True
                
            # For Gamma, we still prefer a URL if possible because we can't upload local images easily yet.
            # However, if we found a local one, it might be better quality.
            # But Gamma API needs a URL.
            # We'll rely on the scraped URL for Gamma for now, unless we build an uploader.
            pass

    # Fallback to scraping if no local logo found (or to get the URL for Gamma)
    print(f"  Client logo from: {context.company_website}")
    client_logo_url = extract_logo_url(context.company_website)
    if client_logo_url:
        print(f"    Found URL: {client_logo_url}")
        
        # Optimization for Cloudinary (common in SaaS)
        # Zello uses Cloudinary and returns a huge OG image (1200x630) which Gamma likely rejects/crops badly.
        # We try to resize it to a logo-friendly size (e.g. 300px width).
        if "res.cloudinary.com" in client_logo_url and "/image/upload/" in client_logo_url:
            try:
                import re
                # Replace existing transforms (e.g. w_1200,h_630) or insert new ones
                # Standard pattern: .../upload/<transforms>/v... or .../upload/v...
                # We want: .../upload/w_300,c_limit,f_png/v...
                
                parts = client_logo_url.split("/image/upload/")
                base = parts[0] + "/image/upload"
                rest = parts[1]
                
                # Check if there are transforms before 'v<numbers>'
                # This is a heuristic.
                if "/v" in rest:
                    # rest = "w_1200,.../v1234/..."
                    # or "v1234/..."
                    subparts = rest.split("/v", 1)
                    if len(subparts) == 2:
                        version_and_path = "v" + subparts[1]
                        # Discard old transforms, use ours
                        new_transforms = "w_300,c_limit,f_png" 
                        new_url = f"{base}/{new_transforms}/{version_and_path}"
                        print(f"    Optimized Logo URL: {new_url}")
                        client_logo_url = new_url
            except Exception as e:
                print(f"    Optimization failed: {e}")

        context.client_logo_url = client_logo_url
        
        if not client_logo_found:
            result = get_logo_as_base64(client_logo_url)
            if result:
                context.client_logo_b64 = result[0]
    else:
        if not client_logo_found:
             print("    Not found")

    # --- Analyst Logo ---
    # Check for local analyst logo
    analyst_dir = assets_dir / "analyst"
    analyst_logo_found = False
    
    if analyst_dir.exists():
        # Look for logo file. Prioritize filenames containing "logo" or just pick first.
        # User uploaded e.g. "uploaded_media_0...".
        # We'll grab all valid images
        images = []
        for ext in ['*.png', '*.jpg', '*.jpeg', '*.svg', '*.webp']:
            images.extend(analyst_dir.glob(ext))
            
        if images:
            print(f"  Found local analyst logos in {analyst_dir}")
            # Sort or pick "best"?
            # If multiple, let's look for one that might be "horizontal" or "header" if named so.
            # Since names are random upload names, we'll just pick the first PNG if available, else first Image.
            # Actually user said "pull from the best option". Without vision, I assume the first valid one is fine, 
            # or I could try to list them and let user pick? No, automation.
            # Let's prefer PNG for transparency.
            
            best_logo = next((img for img in images if img.suffix == '.png'), images[0])
            print(f"    Using: {best_logo.name}")
            
            from utils.logo import get_local_logo_as_base64
            res = get_local_logo_as_base64(best_logo)
            if res:
                context.analyst_logo_b64 = res[0]
                analyst_logo_found = True
    
    if not analyst_logo_found:
        print(f"  Analyst logo from: {context.analyst_website}")
        analyst_logo_url = extract_logo_url(context.analyst_website)
        if analyst_logo_url:
            print(f"    Found: {analyst_logo_url}")
            result = get_logo_as_base64(analyst_logo_url)
            if result:
                context.analyst_logo_b64 = result[0]
        else:
            print("    Not found")


async def run_audit_pipeline(config: dict, max_pages: int = 20, verbose: bool = False,
                              progress_callback=None, skip_screenshots: bool = False) -> tuple:
    """
    Core audit pipeline usable by both CLI and Streamlit.

    Args:
        config: Dict of configuration values (company_name, company_website, etc.)
        max_pages: Maximum pages to crawl
        verbose: Enable verbose output
        progress_callback: Optional callback(phase, status, detail) for progress updates
        skip_screenshots: Skip screenshot capture

    Returns:
        Tuple of (AuditReport, ContextStore)
    """
    context = setup_context_from_config(config, max_pages)

    if not context.company_website:
        raise ValueError("company_website is required in config")

    extract_logos(context)

    llm_client = LLMClient()

    orchestrator = Orchestrator(context, llm_client, verbose=verbose, progress_callback=progress_callback)

    if skip_screenshots:
        orchestrator.screenshot_manager = None

    report = await orchestrator.run_audit()
    return report, context


def main():
    parser = argparse.ArgumentParser(
        description='Website Audit Tool - Agentic Architecture for B2B SaaS Marketing Audits'
    )

    # Client-based configuration (new)
    parser.add_argument('--client', '-C', help='Client folder name (looks in clients/<name>/config.txt)')

    # Legacy config-based configuration
    parser.add_argument('--config', '-c', help='Path to config.txt file')

    # Common options
    parser.add_argument('--output', '-o', help='Output directory for reports')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--max-pages', '-m', type=int, default=20, help='Maximum pages to crawl (default: 20)')
    parser.add_argument('--no-screenshots', action='store_true', help='Skip screenshot capture')

    parser.add_argument('--doc', action='store_true', help='Generate a Gamma Document report (requires GAMMA_API_KEY)')
    parser.add_argument('--docx', action='store_true', help='Generate a Word Docx Report (Local)')

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Determine config path
    if args.client:
        # Client-based: look in clients/<name>/config.txt
        base_dir = Path(__file__).parent
        config_path = base_dir / "clients" / args.client / "config.txt"
        output_dir = base_dir / "clients" / args.client / "output"
    elif args.config:
        # Legacy config-based
        config_path = Path(args.config)
        output_dir = Path(args.output) if args.output else Path('./output/')
    else:
        parser.error("Either --client or --config is required")

    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)

    # Parse configuration
    print("\n" + "="*60)
    print("  WEBSITE AUDIT TOOL - AGENTIC ARCHITECTURE")
    print("  Bhavsar Growth Consulting")
    print("="*60 + "\n")

    print(f"Loading configuration from: {config_path}")
    config = parse_config(str(config_path))

    # Print audit info from config
    print(f"\nAudit Target: {config.get('company_name', 'Unknown Company')}")
    print(f"Website: {config.get('company_website', '')}")
    print(f"Max Pages: {args.max_pages}")

    # Run the core audit pipeline
    try:
        report, context = asyncio.run(run_audit_pipeline(
            config=config,
            max_pages=args.max_pages,
            verbose=args.verbose,
            skip_screenshots=args.no_screenshots
        ))
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nCritical Error during audit: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Generate HTML report
    print("\n" + "-"*50)
    print("  Generating Report")
    print("-"*50)

    # Create output filename
    safe_name = "".join(c if c.isalnum() or c in '-_' else '-' for c in context.company_name)
    output_filename = f"{safe_name}-audit-{context.audit_date.replace('/', '-')}.html"
    output_path = output_dir / output_filename

    # Prepare additional context for template (pass context for critical_pages, segments, etc.)
    from utils.report import generate_html_report
    report_path = generate_html_report(report, str(output_path), context=context)

    # Generate Gamma Doc if requested
    doc_url = None
    if getattr(args, 'doc', False):
        try:
            from utils.gamma import generate_document
            # Use client_logo_url if stored, else None
            logo_url = getattr(context, 'client_logo_url', None)
            doc_url = generate_document(report, logo_url=logo_url)
        except ImportError:
            print("\nWarning: Could not import utils.gamma. Make sure requests is installed.")
        except Exception as e:
            print(f"\nError generating Gamma doc: {e}")

    # Generate Word Docx if requested
    docx_path = None
    if getattr(args, 'docx', False):
        try:
            from utils.docx_report import generate_docx_report
            docx_filename = f"{report.company_name}_Audit_Report.docx"
            docx_path = str(output_dir / docx_filename)
            generate_docx_report(report, docx_path)
            print(f"Word Doc generated: {docx_path}")
        except Exception as e:
            print(f"\nError generating Word Doc: {e}")

    # Print summary
    print(f"\n{'='*60}")
    print(f"  AUDIT COMPLETE")
    print(f"{'='*60}")
    print(f"\nOverall Outcome: {report.overall_outcome.value} ({report.overall_percentage:.1f}%)")
    print(f"\nReport saved to: {report_path}")
    
    if doc_url:
        print(f"Gamma Document: {doc_url}")
    elif getattr(args, 'doc', False):
        print("Gamma Document generation failed.")

    print(f"\nModule Scores:")
    for module in report.modules:
        weight_str = f" ({module.weight}x)" if module.weight > 1 else ""
        print(f"  - {module.name}{weight_str}: {module.outcome.value} ({module.percentage:.0f}%)")

    print(f"\nTotal Recommendations: {len(report.get_all_recommendations())}")

    quick_wins = report.get_quick_wins(3)
    if quick_wins:
        print(f"\nTop Quick Wins:")
        for i, win in enumerate(quick_wins, 1):
            safe_rec = win.recommendation[:80].encode('ascii', 'ignore').decode('ascii')
            print(f"  {i}. {safe_rec}...")

    # Print additional verbose info
    if args.verbose:
        print(f"\n--- Audit Details ---")
        print(f"Pages crawled: {len(context.pages)}")
        print(f"Screenshots captured: {len(context.screenshots)}")


if __name__ == "__main__":
    main()
