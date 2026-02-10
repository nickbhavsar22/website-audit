"""Centralized LLM client wrapper for all agents."""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import time
import asyncio

logger = logging.getLogger(__name__)

class LLMClient:
    """
    Centralized LLM client for making API calls.

    Supports multiple providers: 'anthropic' (default), 'gemini'.
    """

    @staticmethod
    def _get_secret(key):
        """Get secret from env vars or Streamlit secrets."""
        value = os.environ.get(key)
        if not value:
            try:
                import streamlit as st
                value = st.secrets.get(key)
            except Exception:
                pass
        return value

    def __init__(self, api_key: Optional[str] = None, provider: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the LLM client.

        Args:
            api_key: API key for the chosen provider.
            provider: 'anthropic' or 'gemini'. Defaults to LLM_PROVIDER env var or 'anthropic'.
            model: Model name. Defaults depend on provider.
        """
        self.provider = provider or os.environ.get('LLM_PROVIDER', 'anthropic').lower()
        self.api_key = api_key
        self.model = model
        self._client = None

        # Set defaults based on provider
        if self.provider == 'gemini':
            self.api_key = self.api_key or self._get_secret('GEMINI_API_KEY')
            self.model = self.model or "gemini-flash-latest"
        else: # anthropic
            self.api_key = self.api_key or self._get_secret('ANTHROPIC_API_KEY')
            self.model = self.model or "claude-sonnet-4-5-20250929"

    @property
    def client(self):
        """Lazy initialization of the API client."""
        if self._client is None:
            if self.provider == 'gemini':
                self._init_gemini()
            else:
                self._init_anthropic()
        return self._client

    def _init_anthropic(self):
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set.")
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

    def _init_gemini(self):
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set.")
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            # We don't store a 'client' object for Gemini exactly, but we can store the library or model
            self._client = genai
        except ImportError:
            raise ImportError("google-generativeai package not installed. Run: pip install google-generativeai")

    def is_available(self) -> bool:
        """Check if the LLM client is available."""
        return bool(self.api_key)

    def load_prompt(self, prompt_name: str, base_path: Optional[Path] = None) -> str:
        """
        Load a prompt template from the prompts directory.
        """
        if base_path is None:
            base_path = Path(__file__).parent.parent / "prompts"

        prompt_path = base_path / f"{prompt_name}.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding='utf-8')
        return ""

    def complete(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
        system: Optional[str] = None
    ) -> str:
        """
        Complete the prompt using the configured provider.
        """
        # Rate limit protection
        if self.provider == 'gemini':
            time.sleep(4)
        else: # Anthropic
            time.sleep(3) # Basic spacing

        try:
            if self.provider == 'gemini':
                return self._complete_gemini(prompt, max_tokens, temperature, system)
            else:
                return self._complete_anthropic(prompt, max_tokens, temperature, system)
        except Exception as e:
            # Simple retry once for rate limits
            if "429" in str(e) or "rate_limit" in str(e).lower() or "overloaded" in str(e).lower():
                logger.warning("Rate limit hit. Sleeping 10s and retrying...")
                time.sleep(10)
                if self.provider == 'gemini':
                    return self._complete_gemini(prompt, max_tokens, temperature, system)
                else:
                    return self._complete_anthropic(prompt, max_tokens, temperature, system)
            raise e

    def _complete_anthropic(self, prompt: str, max_tokens: int, temperature: float, system: Optional[str]) -> str:
        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature
        }
        if system:
            kwargs["system"] = system

        response = self.client.messages.create(**kwargs)
        return response.content[0].text

    def _complete_gemini(self, prompt: str, max_tokens: int, temperature: float, system: Optional[str]) -> str:
        genai = self.client
        
        # Configure generation config
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature
        )
        
        # Instantiate model
        model_name = self.model
        if "gemini" not in model_name:
             model_name = "gemini-1.5-flash"
             
        # Support system instructions if available in library version, else prepend
        # 'system_instruction' is supported in newer google-generativeai
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system if system else None
            )
        except TypeError:
            # Fallback if system_instruction param not supported
            model = genai.GenerativeModel(model_name=model_name)
            if system:
                prompt = f"System Instruction: {system}\n\nUser Request: {prompt}"

        try:
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )
            return response.text
        except Exception as e:
            # Handle block errors or safety ratings
            if hasattr(e, 'response'):
                 # Try to retrieve text anyway if possible, or return error
                 pass
            return f"Gemini Error: {e}"

    def complete_json(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
        system: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a JSON completion from the LLM.
        """
        # If Gemini, explicitly ask for JSON in prompt if not present, because it handles it well but specific instructions help
        if self.provider == 'gemini' and "JSON" not in prompt:
             prompt += "\n\nRespond strictly in valid JSON format."
             
        response_text = self.complete(prompt, max_tokens, temperature, system)
        return self.parse_json_response(response_text)

    def parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON from an LLM response, handling code blocks.
        """
        # Clean potential markdown
        cleaned_text = response_text.strip()
        if "```json" in cleaned_text:
            cleaned_text = cleaned_text.split("```json")[1].split("```")[0]
        elif "```" in cleaned_text:
            cleaned_text = cleaned_text.split("```")[1]

        cleaned_text = cleaned_text.strip()

        try:
            result = json.loads(cleaned_text)
            if result == {} or result is None:
                logger.warning("LLM returned empty JSON response")
            return result if isinstance(result, dict) else {"data": result}
        except json.JSONDecodeError:
            # Fallback cleanup
            if cleaned_text.startswith("```"):
                cleaned_text = cleaned_text.replace("```", "")
            try:
                result = json.loads(cleaned_text)
                if result == {} or result is None:
                    logger.warning("LLM returned empty JSON response after cleanup")
                return result if isinstance(result, dict) else {"data": result}
            except Exception as e:
                # Return raw text wrapped if parsing fails, or empty dict?
                # Agents expect dict.
                logger.warning("Error parsing JSON: %s\nOutput: %s...", e, response_text[:100])
                return {}

    def validate_response(self, response: Dict[str, Any], expected_fields: Dict[str, type]) -> tuple:
        """
        Validate that an LLM response contains expected fields.

        Args:
            response: The parsed JSON response dict
            expected_fields: Dict mapping field_name -> expected type
                e.g. {"scores": dict, "analysis": str}

        Returns:
            Tuple of (response, missing_fields_list)
        """
        missing_fields = []
        for field_name, field_type in expected_fields.items():
            value = response.get(field_name)
            if value is None:
                missing_fields.append(field_name)
            elif isinstance(value, str) and not value.strip():
                missing_fields.append(field_name)
            elif isinstance(value, (dict, list)) and len(value) == 0:
                missing_fields.append(field_name)
            elif not isinstance(value, field_type):
                missing_fields.append(field_name)

        if missing_fields:
            logger.warning("LLM response missing fields: %s", ', '.join(missing_fields))

        return (response, missing_fields)

    def format_prompt(self, template: str, **kwargs) -> str:
        """
        Format a prompt template with variables.
        """
        result = template
        for key, value in kwargs.items():
            placeholder = "{" + key + "}"
            if isinstance(value, (list, dict)):
                value = json.dumps(value, indent=2)
            result = result.replace(placeholder, str(value))
        return result

    def analyze_with_prompt(
        self,
        prompt_name: str,
        max_tokens: int = 2000,
        **variables
    ) -> Dict[str, Any]:
        """
        Load a prompt, format it with variables, and get JSON response.
        """
        template = self.load_prompt(prompt_name)
        if not template:
            raise ValueError(f"Prompt template not found: {prompt_name}")

        prompt = self.format_prompt(template, **variables)
        return self.complete_json(prompt, max_tokens)

    async def complete_async(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
        system: Optional[str] = None
    ) -> str:
        """
        Asynchronously complete the prompt.
        """
        # Rate limit protection (async sleep)
        if self.provider == 'gemini':
            await asyncio.sleep(4)
        else: # Anthropic
            await asyncio.sleep(2) # Slightly faster for async

        try:
            if self.provider == 'gemini':
                return await self._complete_gemini_async(prompt, max_tokens, temperature, system)
            else:
                return await self._complete_anthropic_async(prompt, max_tokens, temperature, system)
        except Exception as e:
            # Simple retry once for rate limits
            error_str = str(e).lower()
            if "429" in error_str or "rate_limit" in error_str or "overloaded" in error_str:
                logger.warning("Rate limit hit. Sleeping 10s and retrying...")
                await asyncio.sleep(10)
                if self.provider == 'gemini':
                    return await self._complete_gemini_async(prompt, max_tokens, temperature, system)
                else:
                    return await self._complete_anthropic_async(prompt, max_tokens, temperature, system)
            raise e

    async def _complete_anthropic_async(self, prompt: str, max_tokens: int, temperature: float, system: Optional[str]) -> str:
        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature
        }
        if system:
            kwargs["system"] = system

        # Use the async client if available, or wrap sync call if strictly necessary, 
        # but optimal is to use Anthropic's AsyncAnthropic.
        # Check if we have an async client initialized
        if not hasattr(self, '_async_client') or self._async_client is None:
             self._init_anthropic_async()
             
        response = await self._async_client.messages.create(**kwargs)
        return response.content[0].text

    def _init_anthropic_async(self):
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set.")
        try:
            import anthropic
            self._async_client = anthropic.AsyncAnthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

    async def _complete_gemini_async(self, prompt: str, max_tokens: int, temperature: float, system: Optional[str]) -> str:
        # Gemini Python SDK added async definition support recently (generate_content_async)
        genai = self.client
        
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature
        )
        
        model_name = self.model
        if "gemini" not in model_name:
             model_name = "gemini-1.5-flash"
             
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system if system else None
            )
        except TypeError:
            model = genai.GenerativeModel(model_name=model_name)
            if system:
                prompt = f"System Instruction: {system}\n\nUser Request: {prompt}"

        try:
            response = await model.generate_content_async(
                prompt,
                generation_config=generation_config
            )
            return response.text
        except Exception as e:
            if hasattr(e, 'response'):
                 pass
            return f"Gemini Error: {e}"

    async def complete_json_async(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
        system: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a JSON completion asynchronously.
        """
        if self.provider == 'gemini' and "JSON" not in prompt:
             prompt += "\n\nRespond strictly in valid JSON format."
             
        response_text = await self.complete_async(prompt, max_tokens, temperature, system)
        return self.parse_json_response(response_text)

    async def analyze_with_prompt_async(
        self,
        prompt_name: str,
        max_tokens: int = 2000,
        **variables
    ) -> Dict[str, Any]:
        """
        Async version of analyze_with_prompt.
        """
        template = self.load_prompt(prompt_name)
        if not template:
            raise ValueError(f"Prompt template not found: {prompt_name}")

        prompt = self.format_prompt(template, **variables)
        return await self.complete_json_async(prompt, max_tokens)

    async def batch_complete_async(
        self,
        prompts: List[str],
        max_tokens: int = 2000,
        system: Optional[str] = None
    ) -> List[str]:
        """
        Complete multiple prompts in parallel.
        """
        tasks = [self.complete_async(p, max_tokens, system=system) for p in prompts]
        return await asyncio.gather(*tasks)
