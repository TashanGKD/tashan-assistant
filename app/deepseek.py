import json
import httpx

from .config import settings

class DeepSeekClient:
    @property
    def enabled(self) -> bool:
        return bool(settings.deepseek_api_key)

    async def respond(
        self,
        instructions: str,
        input_items,
        *,
        effort: str,
        max_output_tokens: int = 1600,
    ) -> str:
        if not self.enabled:
            return self._demo_answer(input_items)

        payload = {
            "model": settings.deepseek_model,
            "instructions": instructions,
            "input": input_items,
            "reasoning": {"effort": effort},
            "max_output_tokens": max_output_tokens,
        }
        headers = {
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{settings.deepseek_base_url.rstrip('/')}/responses",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        chunks: list[str] = []
        for item in data.get("output", []):
            if item.get("type") != "message":
                continue
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    chunks.append(part.get("text", ""))

        text = "".join(chunks).strip()
        return text or "这次没有生成有效回答。请补充完整报错和你刚执行的操作。"

    async def extract_case(self, transcript: str, instructions: str) -> dict:
        if not self.enabled:
            return self._demo_extract(transcript)

        payload = {
            "model": settings.deepseek_model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": transcript},
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "max_tokens": 1000,
        }
        headers = {
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{settings.deepseek_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"]

        return json.loads(raw)

    def _demo_answer(self, input_items) -> str:
        text = ""
        if isinstance(input_items, str):
            text = input_items
        else:
            for item in input_items:
                if item.get("role") == "user":
                    text += "\n" + str(item.get("content", ""))

        low = text.lower()
        if "command not found" in low or "找不到命令" in text:
            return (
                "先确认安装是否成功，以及可执行文件是否进入 PATH。\n\n"
                "在终端执行：\n\n```bash\nwhich <命令>\n# Windows 使用：\nwhere <命令>\n```\n\n"
                "把安装命令和完整报错贴出来，我继续定位。"
            )
        if "mcp" in low or "connection refused" in low:
            return (
                "先不要继续改 Prompt，先确认 MCP 服务是否真的启动：\n\n"
                "1. 检查服务进程；\n2. 检查客户端配置中的地址和端口；\n"
                "3. 找到日志里第一条 `connection refused` 对应的地址。\n\n"
                "把配置片段和那几行报错贴来。"
            )
        if any(x in low for x in ["pip", "conda", "module", "python"]):
            return (
                "先排除最常见的 Python 环境混用。\n\n```bash\n"
                'python -c "import sys; print(sys.executable)"\n'
                "python -m pip -V\n```\n\n"
                "两条输出应该指向同一套环境。把输出贴来即可继续。"
            )
        return (
            "请尽量补齐这 4 项：\n\n"
            "1. 你想完成什么；\n2. 你刚刚做了哪一步；\n"
            "3. 完整报错或异常现象；\n4. 使用的工具与版本。\n\n"
            "已有报错时直接原样粘贴，不要只发最后一行。"
        )

    def _demo_extract(self, transcript: str) -> dict:
        low = transcript.lower()
        if any(x in low for x in ["pip", "conda", "module", "command not found", "path"]):
            category, subcategory = "环境配置", "依赖与路径"
        elif "mcp" in low or "tool" in low or "工具" in transcript:
            category, subcategory = "工具调用", "MCP/工具配置"
        elif "rag" in low or "知识库" in transcript:
            category, subcategory = "知识库与RAG", "检索流程"
        elif "prompt" in low or "提示词" in transcript:
            category, subcategory = "Prompt设计", "任务描述"
        else:
            category, subcategory = "课程概念", "待细分"

        compact = " ".join(transcript.split())[:180]
        return {
            "category": category,
            "subcategory": subcategory,
            "problem_summary": compact,
            "root_cause": "",
            "solution_summary": "",
            "faq_candidate": False,
        }
