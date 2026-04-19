import logging
import time
from functools import wraps
from typing import Any, Callable

# OpenRouter SDK typing
from openrouter import OpenRouter


logger = logging.getLogger(__name__)


class LLMTrackingContext:
    """
    A utility generic enough to track LLM token counts, costs and execution time.
    Built to support vanilla OpenAI / OpenRouter clients now, and can be easily
    integrated as a Langchain BaseCallbackHandler in future refactors.
    """

    @staticmethod
    def _extract_usage(response: Any) -> dict:
        """Attempt to extract standard usage dictionaries from OpenRouter/OpenAI responses."""
        usage_data = {}
        if hasattr(response, "usage") and response.usage is not None:
            usage_data = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) or getattr(response.usage, "input_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0) or getattr(response.usage, "output_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0),
                # OpenRouter extension includes a cost in 'cost' attribute sometimes
                "cost": getattr(response.usage, "cost", 0.0),
            }
        elif isinstance(response, dict) and "usage" in response:
            usage_info = response["usage"]
            usage_data = {
                "prompt_tokens": usage_info.get("prompt_tokens", 0) or usage_info.get("input_tokens", 0),
                "completion_tokens": usage_info.get("completion_tokens", 0) or usage_info.get("output_tokens", 0),
                "total_tokens": usage_info.get("total_tokens", 0),
                "cost": usage_info.get("cost", 0.0),
            }
        elif isinstance(response, dict) and "usage_metadata" in response:
            usage_info = response["usage_metadata"]
            usage_data = {
                "prompt_tokens": usage_info.get("input_tokens", 0),
                "completion_tokens": usage_info.get("output_tokens", 0),
                "total_tokens": usage_info.get("total_tokens", 0),
                "cost": 0.0,
            }
        elif hasattr(response, "usage_metadata") and isinstance(response.usage_metadata, dict):
            usage_info = response.usage_metadata
            usage_data = {
                "prompt_tokens": usage_info.get("input_tokens", 0),
                "completion_tokens": usage_info.get("output_tokens", 0),
                "total_tokens": usage_info.get("total_tokens", 0),
                "cost": 0.0,
            }
        return usage_data

    @staticmethod
    def log_call(operation_name: str, elapsed_s: float, usage: dict, model: str = "unknown") -> None:
        """Generic logging handler for tracked metrics."""
        prompt_tokens = usage.get('prompt_tokens', 0)
        completion_tokens = usage.get('completion_tokens', 0)
        total_tokens = usage.get('total_tokens', 0)
        cost = usage.get('cost', 0)
        tps = (completion_tokens / elapsed_s) if elapsed_s > 0 else 0

        logger.info(
            f"[LLM Perf] Op: {operation_name} "
            f"| Model: {model} "
            f"| Run Time: {elapsed_s:.3f}s "
            f"| Prompt: {prompt_tokens} "
            f"| Completion: {completion_tokens} "
            f"| Total Tokens: {total_tokens} "
            f"| Speed: {tps:.2f} tk/s "
            f"| Cost: ${cost:.6f}"
        )


class LLMLangchainCallbackStub:
    """
    Demonstrates forward-compatibility. In a future refactor to LangChain, this 
    BaseCallbackHandler stub can be subclassed from langchain_core.callbacks.BaseCallbackHandler
    to capture on_llm_start, on_llm_end, on_llm_error events using LLMTrackingContext.
    """
    def __init__(self):
        self.start_times = {}

    def on_llm_start(self, serialized: dict, prompts: list[str], **kwargs: Any) -> Any:
        run_id = kwargs.get("run_id")
        self.start_times[run_id] = time.time()

    def on_llm_end(self, response: Any, **kwargs: Any) -> Any:
        run_id = kwargs.get("run_id")
        elapsed_s = time.time() - self.start_times.pop(run_id, time.time())
        usage = LLMTrackingContext._extract_usage(response)
        model = response.llm_output.get("model_name", "unknown") if hasattr(response, "llm_output") and response.llm_output else "unknown"
        LLMTrackingContext.log_call("langchain.llm.call", elapsed_s, usage, model)

def intercept_openrouter_chat_send(original_create: Callable[..., Any]) -> Callable[..., Any]:
    """
    Wraps the OpenRouter chat.send method to intercept responses,
    track execution time and retrieve usage metrics automatically.
    """
    @wraps(original_create)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        is_stream = kwargs.get("stream", False)
        model = kwargs.get("model", "unknown")
        
        response = original_create(*args, **kwargs)
        
        if is_stream:
            def stream_generator():
                last_chunk = None
                for chunk in response:
                    last_chunk = chunk
                    yield chunk
                
                # Process end of stream
                elapsed_s = time.time() - start_time
                usage = LLMTrackingContext._extract_usage(last_chunk) if last_chunk else {}
                LLMTrackingContext.log_call("chat.send(stream)", elapsed_s, usage, model)
                
            return stream_generator()
        else:
            elapsed_s = time.time() - start_time
            usage = LLMTrackingContext._extract_usage(response)
            LLMTrackingContext.log_call("chat.send", elapsed_s, usage, model)
            return response

    return wrapper


def intercept_openrouter_embeddings_generate(original_generate: Callable[..., Any]) -> Callable[..., Any]:
    """
    Wraps the OpenRouter embeddings.generate method for tracking purposes.
    """
    @wraps(original_generate)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        model = kwargs.get("model", "unknown")
        
        response = original_generate(*args, **kwargs)
        
        elapsed_s = time.time() - start_time
        usage = LLMTrackingContext._extract_usage(response)
        LLMTrackingContext.log_call("embeddings.generate", elapsed_s, usage, model)
        return response

    return wrapper


def instrument_openrouter_client(client: OpenRouter) -> OpenRouter:
    """
    Monkey-patches an instantiated OpenRouter client instance to add automated
    usage and timing logs overhead-free.
    """
    # Instrument Chat completions
    if hasattr(client, "chat") and hasattr(client.chat, "send"):
        if not getattr(client.chat.send, "_is_instrumented", False):
            patched_chat = intercept_openrouter_chat_send(client.chat.send)
            patched_chat._is_instrumented = True
            client.chat.send = patched_chat
            
    # Instrument Embeddings
    if hasattr(client, "embeddings") and hasattr(client.embeddings, "generate"):
        if not getattr(client.embeddings.generate, "_is_instrumented", False):
            patched_emb = intercept_openrouter_embeddings_generate(client.embeddings.generate)
            patched_emb._is_instrumented = True
            client.embeddings.generate = patched_emb
    
    return client
