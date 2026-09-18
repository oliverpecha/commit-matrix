import os
import time
from litellm import completion

def execute_inference(model_name, sys_prompt, user_prompt, rate_limits, aimd, retries=6):
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
                response_format={"type": "json_object"},
            )
            aimd.release(success=True)
            
            usage = response.get("usage", {})
            rate_limits.record_usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            headers = getattr(response, "_hidden_params", {}).get("response_headers", {})
            if headers:
                rate_limits.update_from_headers(headers)
                
            return response.choices[0].message.content
            
        except Exception as e:
            err_str = str(e)
            aimd.release(success=False)
            is_transient = any(token in err_str.lower() for token in ("503", "429", "unavailable", "quota", "rate limit"))
            if is_transient and retries > 0:
                time.sleep(15 * (7 - retries))
                retries -= 1
                continue
            raise Exception(f"API Error: {err_str}")
    raise Exception("Max retries exceeded")
