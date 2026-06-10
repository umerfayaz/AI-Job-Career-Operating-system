# Finger print Policy control for stretegic_agent to run with brain3 and brain4 Loops


import json, hashlib

def fingerprint_policy(actions: dict) ->str:
    normalized =  json.dumps(actions, sort_keys=True)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

