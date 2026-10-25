"""Repair only an unambiguous JSON envelope; never infer missing evidence."""
import json


def normalize_fields(raw, rubric):
    if not isinstance(raw, dict) or 'claims' in raw or 'requirements' in raw:
        return raw
    criteria = [item['key'] for item in rubric.get('criteria', [])]
    requirements = [item['key'] for item in rubric.get('requirements', [])]
    keys = criteria + requirements
    if not criteria or len(set(keys)) != len(keys) or not all(
            key in raw and isinstance(raw[key], dict) for key in keys):
        return raw
    if set(raw) - set(keys) - {'reason'}:
        return raw
    return {'claims': {key: raw[key] for key in criteria},
            'requirements': {key: raw[key] for key in requirements},
            'reason': raw.get('reason', '')}


def wrap_format(model):
    ask = model._ask
    def wrapped(system, user):
        result = ask(system, user)
        payload = json.loads(user)
        return normalize_fields(result, payload.get('rubric', {}))
    model._ask = wrapped
    return model
