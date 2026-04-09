"""Optional one-shot LLM call for Phase 0 exit criteria (requires OPENAI_API_KEY)."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


async def main() -> None:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("SKIP: set OPENAI_API_KEY to run LLM smoke.")
        return

    from langchain_openai import ChatOpenAI

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(model=model, api_key=key)
    msg = await llm.ainvoke("Reply with exactly: ok")
    text = msg.content if hasattr(msg, "content") else str(msg)
    print("LLM response:", text)


if __name__ == "__main__":
    asyncio.run(main())
