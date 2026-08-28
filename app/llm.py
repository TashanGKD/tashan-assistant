import json

import httpx

from .config import settings


class LLMClient:
    @property
    def enabled(self) -> bool:
        return all(
            value.strip()
            for value in (
                settings.llm_api_url,
                settings.llm_api_key,
                settings.llm_model,
            )
        )

    async def respond(
        self,
        instructions: str,
        input_items,
        *,
        max_output_tokens: int = 1600,
    ) -> str:
        messages = [{"role": "system", "content": instructions}]
        if isinstance(input_items, str):
            messages.append({"role": "user", "content": input_items})
        else:
            messages.extend(input_items)

        content = await self._complete(messages, max_output_tokens=max_output_tokens)
        return content or "这次没有生成有效回答。请补充完整报错和你刚执行的操作。"

    async def extract_case(self, transcript: str, instructions: str) -> dict:
        content = await self._complete(
            [
                {"role": "system", "content": instructions},
                {"role": "user", "content": transcript},
            ],
            max_output_tokens=1000,
            response_format={"type": "json_object"},
        )
        return json.loads(self._strip_json_fence(content))

    async def _complete(
        self,
        messages: list[dict],
        *,
        max_output_tokens: int,
        response_format: dict | None = None,
    ) -> str:
        if not self.enabled:
            raise RuntimeError(
                "LLM_API_URL, LLM_API_KEY and LLM_MODEL must all be configured"
            )

        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "max_tokens": max_output_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                settings.llm_api_url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return "".join(
                str(part.get("text", ""))
                for part in content
                if isinstance(part, dict)
            ).strip()
        return str(content or "").strip()

    @staticmethod
    def _strip_json_fence(content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3:
                return "\n".join(lines[1:-1]).strip()
        return stripped
