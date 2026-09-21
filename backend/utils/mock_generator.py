import random
import json
import re

_CLUSTER_STATE = {"focus": None, "streak": 0}

def generate_dynamic_mock_touches(rubric_content: str) -> dict:
    import random, re
    global _CLUSTER_STATE
    
    # 1. Safely extract all touches keys via Regex
    keys = list(set(re.findall(r'"(touches_[a-z_]+)"', rubric_content)))
    if not keys: 
        keys = ["touches_frontend", "touches_backend", "touches_database", "touches_infrastructure", "touches_auth", "touches_tests", "touches_critical"]
    
    # 2. Shift Focus if the current "Sprint" is over
    if _CLUSTER_STATE["focus"] is None or _CLUSTER_STATE["streak"] <= 0:
        _CLUSTER_STATE["focus"] = random.choice(keys)
        _CLUSTER_STATE["streak"] = random.randint(10, 25) # Stay focused for 10-25 commits
    else:
        _CLUSTER_STATE["streak"] -= 1

    touches = {k: 0 for k in keys}
    active = []
    
    # 3. High probability to hit the current Focus
    focus_key = _CLUSTER_STATE["focus"]
    if focus_key and random.random() < 0.75:
        touches[focus_key] = random.choices([1, 2, 3, 4], weights=[30, 40, 20, 10])[0]
        active.append(focus_key)
        
    # 4. Low background noise for non-focus services
    for k in keys:
        if k != focus_key and random.random() < 0.05:
            touches[k] = random.choices([1, 2], weights=[80, 20])[0]
            active.append(k)
            
    # 5. Floor guard
    if not active and keys:
        fallback = focus_key if random.random() < 0.8 else random.choice(keys)
        touches[fallback] = random.choices([1, 2], weights=[70, 30])[0]
        active.append(fallback)
        
    # 6. Multi-service Blast Radius (Simulating major integrations)
    if random.random() < 0.12 and len(keys) >= 3:
        blast_count = random.randint(2, min(5, len(keys)))
        for k in random.sample(keys, k=blast_count):
            touches[k] = random.choices([2, 3, 4], weights=[10, 50, 40])[0]
            active.append(k)
            
    return touches

_SCORE_STATE = {"phase": "minor"}

def generate_mock_axes(axes_keys):
    import random
    global _SCORE_STATE
    
    # 1. State Transitions (Markov Chain)
    current = _SCORE_STATE["phase"]
    if current == "minor":
        # Transition out of minor faster into standard core delivery
        _SCORE_STATE["phase"] = random.choices(["minor", "core"], weights=[60, 40])[0]
    elif current == "core":
        # Healthy flow: 20% minor chore, 65% sustained core, 15% major architectural spike
        _SCORE_STATE["phase"] = random.choices(["minor", "core", "pivotal"], weights=[20, 65, 15])[0]
    else: # pivotal: allow 20% chance to sustain a mini-streak before exhausting back
        _SCORE_STATE["phase"] = random.choices(["core", "pivotal", "minor"], weights=[70, 20, 10])[0]
        
    phase = _SCORE_STATE["phase"]
    axes = {}
    for k in axes_keys:
        if phase == "minor":
            # Baseline small tasks: mostly 1s and 2s (tot: 4–7)
            axes[k] = random.choices([1, 2, 3, 4], weights=[45, 45, 10, 0])[0]
        elif phase == "core":
            # Solid feature delivery: mostly 2s and 3s with occasional 4 (tot: 8–13)
            axes[k] = random.choices([1, 2, 3, 4], weights=[5, 35, 45, 15])[0]
        else: # pivotal
            # Architectural leaps: high concentration of 3s and 4s (tot: 14–16)
            axes[k] = random.choices([1, 2, 3, 4], weights=[0, 0, 35, 65])[0]
            
    # Introduce 10% chance for random noise to break uniformity
    if random.random() < 0.1:
        axes[random.choice(axes_keys)] = random.randint(1, 4)
        
    return axes
