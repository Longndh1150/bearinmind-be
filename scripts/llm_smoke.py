"""Optional one-shot LLM call for Phase 0 exit criteria.

Uses generic OpenAI-compatible env vars:
- LLM_API_KEY
- LLM_BASE_URL (optional)
- LLM_MODEL
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


async def main() -> None:
    key = os.getenv("LLM_API_KEY")
    if not key:
        print("SKIP: set LLM_API_KEY to run LLM smoke.")
        return

    from langchain_openai import ChatOpenAI

    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    base_url = os.getenv("LLM_BASE_URL", "").strip() or None

    llm = ChatOpenAI(model=model, api_key=key, base_url=base_url)
    msg = await llm.ainvoke("Reply with exactly: ok")
    text = msg.content if hasattr(msg, "content") else str(msg)
    print("LLM response:", text)


if __name__ == "__main__":
    asyncio.run(main())
