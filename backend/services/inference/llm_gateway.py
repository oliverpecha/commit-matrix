import logging
import os
import time
from litellm import completion
from litellm.exceptions import RateLimitError, Timeout, APIConnectionError, AuthenticationError, BadRequestError
try:
    from litellm import supports_response_schema
except ImportError:
    def supports_response_schema(*args, **kwargs): return False

logger = logging.getLogger(__name__)

def execute_inference(model_name, sys_prompt, user_prompt, rate_limits, aimd, retries=6, response_schema=None, max_tokens=1024, timeout=30):
    use_schema = False
    if response_schema and supports_response_schema(model_name):
        use_schema = True
        fmt = {"type": "json_schema", "json_schema": {"name": "commit_schema", "strict": True, "schema": response_schema}}
        logger.info(f"[llm_gateway] Active inference mode: native json_schema (model={model_name})")
    else:
        fmt = {"type": "json_object"}
        logger.info(f"[llm_gateway] Active inference mode: prompted json_object fallback (model={model_name})")

    while retries > 0:
        try:
            aimd.acquire()
            rate_limits.wait_if_needed()
            
            response = completion(
                model=model_name,
                api_key=os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"),
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=fmt,
                max_tokens=max_tokens,
                timeout=timeout
            )
            aimd.release(success=True)
            
            usage = response.get("usage", {})
            rate_limits.record_usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            headers = getattr(response, "_hidden_params", {}).get("response_headers", {})
            if headers:
                rate_limits.update_from_headers(headers)
                
            return response.choices[0].message.content
            
        except (AuthenticationError, BadRequestError) as e:
            aimd.release(success=False, congestion=False)
            logger.error(f"[llm_gateway] Non-retryable error ({type(e).__name__}): {e}. Failing fast with zero retries.")
            raise Exception(f"Fatal API Error: {str(e)}")
        except (RateLimitError, Timeout, APIConnectionError) as e:
            err_str = str(e)
            aimd.release(success=False, congestion=True)
            logger.warning(f"[llm_gateway] Transient error ({type(e).__name__}): {err_str}. Backing off and retrying ({retries-1} retries left)...")
            if retries > 1:
                time.sleep(15 * (7 - retries))
                retries -= 1
                continue
            raise Exception(f"API Error: {err_str}")
        except Exception as e:
            err_str = str(e)
            is_transient = any(token in err_str.lower() for token in ("503", "429", "unavailable", "quota", "rate limit"))
            aimd.release(success=False, congestion=is_transient)
            is_transient = any(token in err_str.lower() for token in ("503", "429", "unavailable", "quota", "rate limit"))
            if is_transient and retries > 1:
                time.sleep(15 * (7 - retries))
                retries -= 1
                continue
            raise Exception(f"API Error: {err_str}")
    raise Exception("Max retries exceeded")
