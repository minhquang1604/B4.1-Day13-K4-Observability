from __future__ import annotations

import os
from dataclasses import dataclass
from openai import OpenAI

from .incidents import STATE
from .tracing import observe

@dataclass
class RealUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class RealResponse:
    text: str
    usage: RealUsage
    model: str


class OpenAILLM:
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model
        # We assume OPENAI_API_KEY is present in the env or .env file
        self.client = OpenAI()

    @observe(name="llm_generate", as_type="generation")
    def generate(self, prompt: str) -> RealResponse:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        answer = response.choices[0].message.content or ""
        
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        
        # Inject the cost spike incident dynamically just like FakeLLM
        if STATE.get("cost_spike"):
            output_tokens *= 4
            
        return RealResponse(
            text=answer, 
            usage=RealUsage(input_tokens, output_tokens), 
            model=self.model
        )
