"""Unit tests for selectors.json loading and _sel() accessor."""
import json
import os
from unittest.mock import patch, mock_open

# Reset module cache to ensure fresh import
import bossmaster


def _reset_selectors_cache():
    """Reset the selectors cache before each test."""
    bossmaster._SELECTORS_CACHE = None


# === load_selectors ===

def test_load_selectors_returns_dict():
    _reset_selectors_cache()
    result = bossmaster.load_selectors()
    assert isinstance(result, dict)


def test_load_selectors_cached():
    _reset_selectors_cache()
    r1 = bossmaster.load_selectors()
    r2 = bossmaster.load_selectors()
    assert r1 is r2  # same object, cached


def test_load_selectors_has_expected_groups():
    _reset_selectors_cache()
    sel = bossmaster.load_selectors()
    expected = ['candidate_card', 'name_extraction', 'greet_button',
                'iframe', 'scroll', 'captcha_detection', 'limit_detection']
    for group in expected:
        assert group in sel, f"Missing group: {group}"


def test_load_selectors_file_not_found_returns_empty():
    _reset_selectors_cache()
    import contextlib, io
    original_open = open
    def fake_open(path, *args, **kwargs):
        if 'selectors.json' in str(path):
            raise FileNotFoundError("not found")
        return original_open(path, *args, **kwargs)
    import builtins
    try:
        builtins.open = fake_open
        bossmaster._SELECTORS_CACHE = None
        with contextlib.redirect_stdout(io.StringIO()):
            result = bossmaster.load_selectors()
        assert result == {}
    finally:
        builtins.open = original_open
        _reset_selectors_cache()


# === _sel ===

def test_sel_returns_value():
    _reset_selectors_cache()
    result = bossmaster._sel('iframe', 'selector')
    assert result == 'tag:iframe'


def test_sel_returns_default_for_missing_key():
    _reset_selectors_cache()
    result = bossmaster._sel('iframe', 'nonexistent_key', 'fallback')
    assert result == 'fallback'


def test_sel_returns_default_for_missing_group():
    _reset_selectors_cache()
    result = bossmaster._sel('nonexistent_group', 'key', 'fallback')
    assert result == 'fallback'


def test_sel_captcha_keywords_is_list():
    _reset_selectors_cache()
    kws = bossmaster._sel('captcha_detection', 'keywords')
    assert isinstance(kws, list)
    assert len(kws) > 0
    assert '请完成安全验证' in kws


def test_sel_limit_detection_keywords_are_split_by_meaning():
    _reset_selectors_cache()
    legacy = bossmaster._sel('limit_detection', 'keywords')
    exhausted = bossmaster._sel('limit_detection', 'exhausted_keywords')
    upgrade = bossmaster._sel('limit_detection', 'upgrade_keywords')
    quota = bossmaster._sel('limit_detection', 'quota_keywords')
    assert legacy == exhausted
    assert '次数已用完' in exhausted
    assert '升级套餐' in upgrade
    assert '今日剩余' in quota
    assert '今日剩余' not in exhausted


def test_sel_captcha_css_selectors_is_list():
    _reset_selectors_cache()
    css = bossmaster._sel('captcha_detection', 'css_selectors')
    assert isinstance(css, list)
    assert '.geetest_panel' in css
    assert '[class*="geetest"]' in css


def test_sel_card_by_id_template():
    _reset_selectors_cache()
    template = bossmaster._sel('candidate_card', 'card_by_id_css')
    assert '{geek_id}' in template
    formatted = template.format(geek_id='abc123')
    assert 'abc123' in formatted


def test_sel_scroll_bottom_texts():
    _reset_selectors_cache()
    texts = bossmaster._sel('scroll', 'bottom_texts')
    assert isinstance(texts, list)
    assert '到底' in texts


def test_sel_greet_button_xpath():
    _reset_selectors_cache()
    xpath = bossmaster._sel('greet_button', 'button_xpath')
    assert '继续沟通' in xpath
    assert '立即沟通' in xpath
