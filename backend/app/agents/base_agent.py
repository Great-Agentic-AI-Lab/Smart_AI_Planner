"""
Base Agent with LLM Fallback Support
Primary: Google Gemini
Fallback: Perplexity (if configured)
"""
import logging
import json
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
import asyncio

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Base class for all AI agents with automatic LLM fallback.
    
    Fallback chain: Gemini → Perplexity → Error
    """
    
    def __init__(
        self,
        name: str,
        system_prompt: str,
        model: str = "gemini-flash-latest",  # FREE tier model
        temperature: float = 0.7
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.temperature = temperature
        
        # Initialize Gemini (primary)
        from app.config import settings
        self.gemini_client = genai.Client(api_key=settings.google_api_key)
        
        # Initialize Perplexity (fallback) if API key exists
        self.perplexity_available = bool(getattr(settings, 'perplexity_api_key', None))
        if self.perplexity_available:
            self.perplexity_api_key = settings.perplexity_api_key
            logger.info(f"{self.name}: Perplexity fallback enabled")
        
        logger.info(f"{self.name} initialized with model={self.model}")
    
    async def _call_llm(
        self,
        prompt: str,
        parse_json: bool = False,
        timeout: int = 20
    ) -> Dict[str, Any]:
        """
        Call LLM with automatic fallback.
        
        Args:
            prompt: User prompt
            parse_json: Whether to parse response as JSON
            timeout: Request timeout in seconds
            
        Returns:
            {'success': bool, 'data': Any, 'error': str, 'provider': str}
        """
        # Try Gemini first
        result = await self._try_gemini(prompt, parse_json, timeout)
        if result['success']:
            return result
        
        logger.warning(f"{self.name}: Gemini failed, trying fallback...")
        
        # Try Perplexity fallback
        if self.perplexity_available:
            result = await self._try_perplexity(prompt, parse_json, timeout)
            if result['success']:
                return result
        
        # All LLMs failed
        logger.error(f"{self.name}: All LLMs failed")
        return {
            'success': False,
            'data': None,
            'error': 'All LLM providers failed',
            'provider': 'none'
        }
    
    async def _try_gemini(
        self,
        prompt: str,
        parse_json: bool,
        timeout: int
    ) -> Dict[str, Any]:
        """Try Gemini API."""
        try:
            # Combine system prompt + user prompt
            full_prompt = f"{self.system_prompt}\n\n{prompt}"
            
            # Call Gemini with timeout
            response = await asyncio.wait_for(
                self._gemini_request(full_prompt),
                timeout=timeout
            )
            
            # Extract text
            text = response.text.strip()
            
            # Parse JSON if requested
            if parse_json:
                # Remove markdown code blocks if present
                if text.startswith('```json'):
                    text = text.replace('```json', '').replace('```', '').strip()
                elif text.startswith('```'):
                    text = text.replace('```', '').strip()
                
                data = json.loads(text)
            else:
                data = text
            
            logger.info(f"{self.name}: Gemini success")
            return {
                'success': True,
                'data': data,
                'error': None,
                'provider': 'gemini'
            }
        
        except asyncio.TimeoutError:
            logger.error(f"{self.name}: Gemini request timed out")
            return {
                'success': False,
                'data': None,
                'error': 'LLM request timed out',
                'provider': 'gemini'
            }
        except json.JSONDecodeError as e:
            logger.error(f"{self.name}: Gemini JSON parse error: {e}")
            return {
                'success': False,
                'data': None,
                'error': f'JSON parse error: {str(e)}',
                'provider': 'gemini'
            }
        except Exception as e:
            logger.error(f"{self.name}: Gemini error: {e}")
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'provider': 'gemini'
            }
    
    async def _gemini_request(self, prompt: str):
        """Make actual Gemini API request."""
        response = self.gemini_client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=self.temperature,
                max_output_tokens=2048
            )
        )
        return response
    
    async def _try_perplexity(
        self,
        prompt: str,
        parse_json: bool,
        timeout: int
    ) -> Dict[str, Any]:
        """Try Perplexity API as fallback."""
        if not self.perplexity_available:
            return {
                'success': False,
                'data': None,
                'error': 'Perplexity not configured',
                'provider': 'perplexity'
            }
        
        try:
            import httpx
            
            # Perplexity API endpoint
            url = "https://api.perplexity.ai/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {self.perplexity_api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "sonar-pro",  # Use the same working model
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": self.temperature  # optional, can set 0 for deterministic output
                # REMOVE "max_tokens"
            }

            
            # Make request with timeout
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                
                result = response.json()
                text = result['choices'][0]['message']['content'].strip()
                
                # Parse JSON if requested
                if parse_json:
                    if text.startswith('```json'):
                        text = text.replace('```json', '').replace('```', '').strip()
                    elif text.startswith('```'):
                        text = text.replace('```', '').strip()
                    
                    data_parsed = json.loads(text)
                else:
                    data_parsed = text
                
                logger.info(f"{self.name}: Perplexity success")
                return {
                    'success': True,
                    'data': data_parsed,
                    'error': None,
                    'provider': 'perplexity'
                }
        
        except Exception as e:
            logger.error(f"{self.name}: Perplexity error: {e}")
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'provider': 'perplexity'
            }
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Override this method in child agents.
        
        Returns:
            Dict with 'success', 'data', and other fields
        """
        raise NotImplementedError("Child agents must implement execute()")