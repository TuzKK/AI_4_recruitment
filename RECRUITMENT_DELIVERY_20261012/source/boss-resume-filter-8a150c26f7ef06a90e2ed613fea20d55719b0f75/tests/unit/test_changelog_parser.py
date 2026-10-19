from changelog_parser import (
    extract_changelog_section,
    normalize_version,
    parse_changelog_versions,
    split_version_heading,
)


SAMPLE_CHANGELOG = """# 更新日志

## v2.9.3 — 需求解析精度优化

### 体验优化

- **解析结果更精准**：减少泛化词误判

## v2.9.2 – 模型管理增强

### 问题修复

- 修复模型列表展示问题
"""


def test_normalize_version_strips_v_prefix():
    assert normalize_version("v2.9.3") == "2.9.3"
    assert normalize_version("2.9.3") == "2.9.3"


def test_split_version_heading_supports_chinese_and_short_dash():
    assert split_version_heading("## v2.9.3 — 需求解析精度优化") == ("v2.9.3", "需求解析精度优化")
    assert split_version_heading("## v2.9.2 – 模型管理增强") == ("v2.9.2", "模型管理增强")


def test_parse_changelog_versions_extracts_sections():
    versions = parse_changelog_versions(SAMPLE_CHANGELOG)

    assert [v[0] for v in versions] == ["v2.9.3", "v2.9.2"]
    assert versions[0][1] == "## v2.9.3 — 需求解析精度优化"
    assert "解析结果更精准" in versions[0][2]


def test_extract_changelog_section_accepts_with_or_without_v_prefix():
    without_heading = extract_changelog_section(SAMPLE_CHANGELOG, "2.9.3")
    with_heading = extract_changelog_section(SAMPLE_CHANGELOG, "v2.9.3", include_heading=True)

    assert without_heading is not None
    assert without_heading.startswith("")
    assert "## v2.9.3" not in without_heading
    assert "解析结果更精准" in without_heading
    assert with_heading is not None
    assert with_heading.startswith("## v2.9.3")


def test_extract_changelog_section_returns_none_for_missing_version():
    assert extract_changelog_section(SAMPLE_CHANGELOG, "9.9.9") is None
