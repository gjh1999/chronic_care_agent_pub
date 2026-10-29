# app/core/llm/client.py

from openai import OpenAI
from app.config.settings import settings


class LLMClient:
    def __init__(self):
        # self.base_url = settings.LLM_BASE_URL.rstrip("/")
        # self.api_key = settings.LLM_API_KEY
        # self.model = settings.LLM_MODEL
        # self.timeout = settings.LLM_TIMEOUT
        # self.enable_thinking = settings.LLM_ENABLE_THINKING
        # self.stream = settings.LLM_STREAM
        self.base_url = settings.llm_base_url.rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout
        self.enable_thinking = settings.llm_enable_thinking
        self.stream = settings.llm_stream

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )

    def invoke(
        self,
        prompt: str,
        system_prompt: str = "你是一个专业的医疗健康助手",
        print_reasoning: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        """
        调用阿里云百炼 DashScope OpenAI 兼容 Chat Completions API。

        - API Key、Base URL、模型名等从 .env / settings 中读取
        - enable_thinking=True 时，Qwen 深度思考模型会在流式输出中返回 reasoning_content
        - 本方法最终只返回完整回复 content，适合 LangGraph / Agent 节点调用
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        kwargs = {"extra_body": {"enable_thinking": self.enable_thinking}, "stream": self.stream}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )

        if self.stream:
            answer_parts: list[str] = []
            is_answering = False

            for chunk in completion:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                reasoning_content = getattr(delta, "reasoning_content", None)
                if reasoning_content is not None:
                    if print_reasoning and not is_answering:
                        print(reasoning_content, end="", flush=True)
                    continue

                content = getattr(delta, "content", None)
                if content:
                    if not is_answering:
                        is_answering = True
                    answer_parts.append(content)

            return "".join(answer_parts).strip()

        # 非流式模式：兼容测试或不需要流式输出的场景
        return completion.choices[0].message.content.strip()

    def invoke_stream(
        self,
        prompt: str,
        system_prompt: str = "你是一个专业的医疗健康助手",
        max_tokens: int | None = None,
        on_token=None,
    ) -> str:
        """流式调用:每收到一段 content 就回调 on_token,最终返回完整文本。用于 SSE 逐字输出。"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        kwargs = {"extra_body": {"enable_thinking": self.enable_thinking}, "stream": True}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )

        parts: list[str] = []
        for chunk in completion:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                parts.append(content)
                if on_token:
                    on_token(content)
        return "".join(parts).strip()


llm_client = LLMClient()
