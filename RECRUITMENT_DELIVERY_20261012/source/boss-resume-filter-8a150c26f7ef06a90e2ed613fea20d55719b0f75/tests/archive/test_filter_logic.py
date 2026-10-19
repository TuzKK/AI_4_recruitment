"""
测试过滤逻辑
"""
import json
import re

# 读取配置
with open('job_config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

job_rule = config['job_requirements']['职位']

print("=== 当前过滤规则 ===")
print(f"min_exp: {job_rule['min_exp']}")
print(f"edu: {job_rule['edu']}")
print(f"keywords: {job_rule['keywords']}")
print(f"keyword 数量：{len(job_rule['keywords'])}")

# 模拟一些候选人摘要文本
test_candidates = [
    "Java 开发工程师，5 年经验，本科，熟悉 Spring Boot, MySQL, Redis",
    "Python 开发，3 年经验，硕士，熟悉 Django, PostgreSQL",
    "高级 Java 工程师，8 年经验，本科，精通 Spring Cloud, Dubbo, Kafka, MySQL",
    "前端开发，4 年经验，本科，熟悉 Vue, React, TypeScript",
]

print("\n=== 测试过滤 ===")

def filter_candidate(candidate_text, rule):
    try:
        # 检查工作经验
        if rule.get("min_exp", 0) > 0:
            exp_match = re.search(r'(\d+)\s*年', candidate_text.replace(' ', ''))
            if exp_match:
                exp_years = int(exp_match.group(1))
                if rule.get("min_exp", 0) > exp_years:
                    return False
            else:
                if rule.get("min_exp", 0) > 0:
                    return False

        # 检查学历要求
        if rule.get("edu", "不限") != "不限":
            edu_keywords = {"博士": 6, "硕士": 5, "本科": 4, "大专": 3, "高中": 2, "中专": 1}
            candidate_edu_level = max([edu_keywords.get(word, 0) for word in edu_keywords if word in candidate_text])
            required_edu = edu_keywords.get(rule.get("edu", "不限"), 0)

            if required_edu > 0 and candidate_edu_level < required_edu:
                return False

        # 检查关键字 - 关键过滤逻辑
        keywords = rule.get("keywords", [])
        if keywords and not any(keyword in candidate_text for keyword in keywords):
            return False

        return True
    except Exception as e:
        return True

for i, text in enumerate(test_candidates):
    result = filter_candidate(text, job_rule)
    print(f"\n候选人 {i+1}: {'通过' if result else '过滤'}")
    print(f"文本：{text}")

    # 检查 keyword 匹配
    matched_keywords = [kw for kw in job_rule['keywords'] if kw in text]
    print(f"匹配的 keywords: {matched_keywords}")

# 测试一个实际的候选人
print("\n=== 测试实际候选人数据 ===")
try:
    with open('candidates_职位_1777454371.json', 'r', encoding='utf-8') as f:
        candidates = json.load(f)

    passed = 0
    failed = 0

    for c in candidates[:20]:
        summary = c.get('summary', '')
        result = filter_candidate(summary, job_rule)

        if result:
            passed += 1
        else:
            failed += 1
            # 检查失败原因
            if job_rule['keywords']:
                matched = [kw for kw in job_rule['keywords'] if kw in summary]
                if not matched:
                    print(f"过滤（无匹配 keyword）: {c['name']} - {summary[:50]}...")

    print(f"\n通过：{passed}, 过滤：{failed}")
except Exception as e:
    print(f"错误：{e}")
