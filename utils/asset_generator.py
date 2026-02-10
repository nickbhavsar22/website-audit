"""Asset Generation Utility for Audit Recommendations."""

import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from utils.llm_client import LLMClient
from utils.scoring import AuditReport
from orchestrator.context_store import ContextStore

class AssetGenerator:
    def __init__(self, context: ContextStore, llm_client: LLMClient):
        self.context = context
        self.llm_client = llm_client

    def generate_asset(self, asset_type: str, asset_description: str, jtbd: str) -> Optional[str]:
        """
        Generate full content for an asset based on a JTBD recommendation.
        
        Args:
            asset_type: e.g. "Case Study", "Whitepaper"
            asset_description: The specific topic/angle recommended
            jtbd: The Job to be Done description
            
        Returns:
            str: The generated markdown content
        """
        print(f"  Generating {asset_type} for JTBD: {jtbd[:50]}...")
        
        # Summarize context for the LLM
        context_summary = f"Company specializes in {self.context.industry}. "
        if self.context.primary_segment:
            context_summary += f"Primary target segment identified: {self.context.primary_segment} ({self.context.primary_segment_justification})."
        
        # Call LLM
        prompt = self.llm_client.load_prompt("asset_generation")
        formatted_prompt = self.llm_client.format_prompt(
            prompt,
            company_name=self.context.company_name,
            industry=self.context.industry,
            target_segment=self.context.primary_segment or "B2B Customers",
            jtbd=jtbd,
            asset_type=asset_type,
            asset_description=asset_description,
            context_summary=context_summary
        )
        
        content = self.llm_client.complete(formatted_prompt, max_tokens=4000)
        
        return content

    def push_to_gamma(self, content: str, asset_type: str) -> Optional[str]:
        """
        Optional: Push the generated content to Gamma for slide/doc generation.
        """
        try:
            from utils.gamma import GAMMA_API_URL
            import requests
            import time
            
            api_key = os.environ.get("GAMMA_API_KEY")
            if not api_key:
                return None
                
            payload = {
                "inputText": content,
                "format": "document",
                "textMode": "generate",
                "cardSplit": "inputTextBreaks"
            }
            
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": api_key
            }
            
            response = requests.post(GAMMA_API_URL, json=payload, headers=headers)
            if response.ok:
                data = response.json()
                gen_id = data.get('generationId')
                # We could poll here, but for now we'll just return the start info or None
                return f"Gamma generation started: {gen_id}"
            return None
        except Exception as e:
            print(f"  Error pushing to Gamma: {e}")
            return None

    def save_asset_locally(self, content: str, asset_type: str, company_name: str) -> str:
        """Save the generated asset markdown file locally."""
        safe_company = "".join(c if c.isalnum() else "_" for c in company_name)
        safe_type = asset_type.replace(" ", "_")
        filename = f"{safe_company}_{safe_type}_{int(time.time())}.md"
        
        output_dir = Path("output/assets") / safe_company
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / filename
        output_path.write_text(content, encoding='utf-8')
        
        return str(output_path)
