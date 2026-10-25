"""Stage-specific API routing without changing scoring rules or shared state."""
import copy

from .llm import JobModel
from .generic_model import GenericJobModel


def needs_plus_review(result, threshold):
    score = result.get('score')
    return bool(result.get('issues')) or score is None or abs(score - threshold) <= 5


class HybridRouting:
    def for_stage(self, stage):
        if stage not in ('precontact', 'full_resume'):
            raise ValueError('Unknown screening stage')
        routed = copy.copy(self)
        routed.model = 'qwen-flash' if stage == 'precontact' else 'qwen-plus'
        return routed

    def assess(self, stage, rubric, text, coverage, threshold):
        routed = self.for_stage(stage)
        try:
            result = super(HybridRouting, routed).assess(stage, rubric, text, coverage, threshold)
        except (ValueError, TypeError, KeyError):
            if stage != 'precontact':
                raise
            result = {'score': None, 'issues': ['Flash response format invalid']}
        result['screening_model'] = routed.model
        if stage == 'precontact' and needs_plus_review(result, threshold):
            routed.model = 'qwen-plus'
            result = super(HybridRouting, routed).assess(stage, rubric, text, coverage, threshold)
            result['screening_model'] = 'qwen-plus'
            result['reviewed_from'] = 'qwen-flash'
        return result


class HybridGenericJobModel(HybridRouting, GenericJobModel):
    pass


class HybridJobModel(HybridRouting, JobModel):
    pass
