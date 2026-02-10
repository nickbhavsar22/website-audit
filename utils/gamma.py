"""Gamma App Integration for Slide Generation."""

import os
import requests
import time
from typing import Optional
from utils.scoring import AuditReport

# API Endpoint
GAMMA_API_URL = "https://public-api.gamma.app/v1.0/generations"

def _construct_document_prompt(report: AuditReport, logo_url: str = None) -> str:
    """
    Construct a detailed prompt for Gamma Document generation.
    Uses Markdown to structure a vertical report with HTML-level parity.
    """
    company = report.company_name
    grade = report.overall_grade.value
    outcome = report.overall_outcome.value
    
    prompt_parts = []
    
    # --- Section 1: Title & Executive Summary ---
    title_section = f"""
    # Marketing Audit: {company}
    ### Analyzed by {report.analyst_name} | {report.audit_date}
    
    <Instructions>
    - Format: Document / Report.
    - Style: Professional, Editorial, High-End Consulting.
    - Theme: Clean White or Dark Blue (Professional).
    - Image Style: Realistic, Business-focused.
    - Detail Level: High. Use tables or lists for score breakdowns.
    </Instructions>
    
    # Executive Summary
    
    ## The Verdict: {grade} - {outcome}
    
    We analyzed {company} across {len(report.modules)} key dimensions to identify strategic friction points and growth opportunities.
    
    **Strategic Friction:**
    >{report.strategic_friction.description if report.strategic_friction else "Not explicitly identified."}
    
    **Primary Symptom:** {report.strategic_friction.primary_symptom if report.strategic_friction else "N/A"}
    
    **Business Impact:** {report.strategic_friction.business_impact if report.strategic_friction else "High risk of missed revenue."}
    """
    if logo_url:
        title_section += f"\n\n![Client Logo]({logo_url})"
        
    prompt_parts.append(title_section)

    # --- Section 2: Strategic Prioritization Matrix ---
    # Group recommendations by Matrix Placement
    matrix = report.get_matrix_recommendations()
    # Matrix keys are values of MatrixPlacement enum: "Quick Win", etc.
    
    def format_matrix_list(recs):
        if not recs: return "_None identified._"
        return "\n".join([f"- **{r.recommendation}**\n  *Impact: {r.business_impact}*" for r in recs[:5]])

    prompt_parts.append(f"""
    # Strategic Prioritization
    
    We successfully identified {len(report.get_all_recommendations())} actionable opportunities. Below is the strategic triage of these initiatives.
    
    ## Quick Wins (High Impact, Low Effort)
    _Immediate value creation with minimal resource drag._
    {format_matrix_list(matrix.get('Quick Win', []))}
    
    ## Strategic Bets (High Impact, High Effort)
    _Long-term competitive moats requiring dedicated resources._
    {format_matrix_list(matrix.get('Strategic Bet', []))}
    
    ## Low Hanging Fruit (Low Impact, Low Effort)
    _Housekeeping items to clean up when capacity permits._
    {format_matrix_list(matrix.get('Low Hanging Fruit', []))}
    """)

    # --- Section 3: Detailed Module Analysis ---
    for module in report.modules:
        # Full Scorecard
        score_rows = []
        for item in module.items:
            # Format: **Name**: Actual/Max - Note
            row = f"- **{item.name}** ({item.actual_points}/{item.max_points}): {item.notes}"
            score_rows.append(row)
        score_block = "\n".join(score_rows)

        # Full Recommendations with "So What?"
        rec_rows = []
        for r in module.recommendations:
            # Format: **Recommendation** - "So What?"
            row = f"- **{r.recommendation}**\n  *Business Impact: {r.business_impact}* (Effort: {r.effort.value})"
            rec_rows.append(row)
        rec_block = "\n".join(rec_rows) if rec_rows else "_No specific recommendations._"
            
        section_content = f"""
        # {module.name}
        
        ## Grade: {module.grade.value} ({module.outcome.value})
        
        ### Executive Insight
        {module.analysis_text}
        
        ### Scorecard Breakdown
        {score_block}
        
        ### Strategic Recommendations
        {rec_block}
        """
        prompt_parts.append(section_content)

    # --- Section 4: Closing ---
    prompt_parts.append(f"""
    # Next Steps
    
    1. **Execute Quick Wins**: Assign owners to the 'Quick Win' initiatives identified above.
    2. **Deep Dive**: Review the 'Strategic Bets' with leadership to align on budget.
    3. **Monitor**: Re-run this audit in 90 days to track impact on the Authority Grade.
    """)

    return "\n---\n".join(prompt_parts)


def generate_document(report: AuditReport, logo_url: str = None) -> Optional[str]:
    """
    Generate a detailed document using Gamma App API.
    
    Args:
        report: The AuditReport object.
        logo_url: Optional URL to the client's logo (must be publicly accessible).
        
    Returns:
        str: URL to the generated document, or None if failed.
    """
    api_key = os.environ.get("GAMMA_API_KEY")
    if not api_key:
        print("Error: GAMMA_API_KEY not found in environment variables.")
        return None

    print(f"  Generating detailed document for {report.company_name} via Gamma...")
    
    # Construct detailed text
    prompt_text = _construct_document_prompt(report, logo_url)
    
    payload = {
        "inputText": prompt_text,
        "format": "document",  # CHANGED from "presentation"
        "textMode": "generate", 
        "cardSplit": "inputTextBreaks" 
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key
    }
    
    try:
        response = requests.post(GAMMA_API_URL, json=payload, headers=headers)
        
        if not response.ok:
            print(f"  Gamma API Error: {response.status_code}")
            print(f"  Response: {response.text}")
            return None
            
        data = response.json()
        generation_id = data.get('generationId')
        
        if not generation_id:
             print(f"  Error: No generationId returned. Response: {data}")
             return None

        # Poll for completion
        print(f"  Generation started (ID: {generation_id}). Waiting for completion...")
        
        max_retries = 40 
        for i in range(max_retries):
            time.sleep(3) 
            
            status_url = f"{GAMMA_API_URL}/{generation_id}"
            status_resp = requests.get(status_url, headers=headers)
            
            if not status_resp.ok:
                continue
                
            status_data = status_resp.json()
            status = status_data.get('status')
            
            if status in ['COMPLETED', 'completed']:
                url = status_data.get('gammaUrl') or status_data.get('url')
                print(f"  Generation complete!")
                return url
            elif status in ['FAILED', 'failed']:
                print(f"  Generation failed: {status_data}")
                return None
            else:
                if i % 5 == 0:
                    print(f"  Status: {status}...")
        
        print("  Timeout waiting for document generation.")
        return None
        
    except Exception as e:
        print(f"  Unexpected error generating document: {e}")
        return None
