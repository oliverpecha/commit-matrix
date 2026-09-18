from backend.services.inference.llm_gateway import execute_inference
from backend.services.inference.schema_enforcer import RubricSpec, parse_and_validate

def run_inference(sys_prompt, user_prompt, model_name, rate_limits, aimd):
    rubric_spec = RubricSpec(sys_prompt)
    raw_content = execute_inference(model_name, sys_prompt, user_prompt, rate_limits, aimd)
    return parse_and_validate(raw_content, rubric_spec)
