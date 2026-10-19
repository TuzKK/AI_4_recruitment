"""
筛选规则测试脚本
测试各种候选人场景，验证筛选逻辑的正确性
"""
import json
import os
import sys

# 导入 bossmaster 中的筛选函数
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bossmaster import filter_candidate, check_required_condition


def test_required_conditions():
    """测试必要条件检查"""
    print("=" * 60)
    print("测试必要条件检查")
    print("=" * 60)

    # 测试字符串形式的必要条件
    test_cases = [
        {
            "name": "字符串条件 - 统招本科",
            "condition": "统招本科",
            "text1": "统招本科，5 年 Java 经验",
            "text2": "成教本科，5 年 Java 经验",
            "expected1": True,
            "expected2": False
        },
        {
            "name": "OR 条件 - 工作流引擎",
            "condition": {"type": "or", "items": ["activiti", "camunda", "flowable"]},
            "text1": "熟悉 activiti 工作流引擎",
            "text2": "熟悉 Spring Boot，不了解工作流",
            "text3": "有 camunda 项目经验",
            "expected1": True,
            "expected2": False,
            "expected3": True
        },
        {
            "name": "AND 条件 - 多技能要求",
            "condition": {"type": "and", "items": ["Java", "MySQL", "Redis"]},
            "text1": "精通 Java，熟悉 MySQL 和 Redis",
            "text2": "精通 Java 和 MySQL",
            "text3": "熟悉 Java、MySQL、Redis、Kafka",
            "expected1": True,
            "expected2": False,
            "expected3": True
        }
    ]

    for tc in test_cases:
        print(f"\n[测试] {tc['name']}")
        print(f"  条件：{tc['condition']}")

        # 测试第一个文本
        result1 = check_required_condition(tc['text1'], tc['condition'])
        status1 = "PASS" if result1['passed'] == tc['expected1'] else "FAIL"
        print(f"  {status1} 文本 1: '{tc['text1'][:40]}...' -> {'通过' if result1['passed'] else '淘汰'} (期望：{'通过' if tc['expected1'] else '淘汰'})")

        # 测试第二个文本
        result2 = check_required_condition(tc['text2'], tc['condition'])
        status2 = "PASS" if result2['passed'] == tc['expected2'] else "FAIL"
        print(f"  {status2} 文本 2: '{tc['text2'][:40]}...' -> {'通过' if result2['passed'] else '淘汰'} (期望：{'通过' if tc['expected2'] else '淘汰'})")

        # 测试第三个文本（如果有）
        if 'text3' in tc:
            result3 = check_required_condition(tc['text3'], tc['condition'])
            status3 = "PASS" if result3['passed'] == tc['expected3'] else "FAIL"
            print(f"  {status3} 文本 3: '{tc['text3'][:40]}...' -> {'通过' if result3['passed'] else '淘汰'} (期望：{'通过' if tc['expected3'] else '淘汰'})")


def test_full_filter():
    """测试完整的筛选逻辑"""
    print("\n" + "=" * 60)
    print("测试完整筛选逻辑")
    print("=" * 60)

    # 加载配置文件
    config_file = "job_config.json"
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 支持新旧两种格式
        if "jobs" in config:
            job_rules = config["jobs"]
        else:
            job_rules = config.get("job_requirements", {})

        # 获取默认规则
        default_rule = job_rules.get("default", {})
        job_rule = job_rules.get("高级 Java 工程师", default_rule)

        print(f"\n使用规则：高级 Java 工程师")
        print(f"  最低经验：{job_rule.get('min_exp', 0)}年")
        print(f"  最低学历：{job_rule.get('edu', '不限')}")
        print(f"  必要条件：{job_rule.get('required_conditions', [])}")

        test_candidates = [
            {
                "name": "合格候选人 - 工作流经验",
                "text": "5 年 Java 开发经验，统招本科，熟悉 Spring Cloud、MySQL、Redis，有 activiti 工作流项目经验，了解微服务架构",
                "expected_pass": True,
                "expected_score_min": 70
            },
            {
                "name": "不合格 - 缺少工作流经验",
                "text": "5 年 Java 开发经验，统招本科，熟悉 Spring Cloud、MySQL、Redis，了解微服务架构",
                "expected_pass": False,
                "expected_score_min": 0
            },
            {
                "name": "不合格 - 非统招本科",
                "text": "5 年 Java 开发经验，成教本科，熟悉 Spring Cloud、MySQL、Redis、activiti",
                "expected_pass": False,
                "expected_score_min": 0
            },
            {
                "name": "不合格 - 经验不足",
                "text": "统招本科，2 年 Java 经验，熟悉 Spring Boot、MySQL",
                "expected_pass": False,
                "expected_score_min": 0
            },
            {
                "name": "强烈推荐 - 高匹配度",
                "text": "8 年 Java 架构师经验，985 本科，精通 Spring Cloud、Spring Boot、MySQL、Redis、Kafka，主导过 activiti 工作流项目，熟悉 AI 和大模型应用",
                "expected_pass": True,
                "expected_score_min": 75
            },
            {
                "name": "待定 - 低匹配度但满足硬性条件",
                "text": "4 年开发经验，统招本科，熟悉 Java 基础，了解数据库操作，有 camunda 简单使用经验",
                "expected_pass": True,
                "expected_score_min": 60
            }
        ]

        for tc in test_candidates:
            passed, score, details = filter_candidate(tc['text'], job_rule)
            status = "PASS" if passed == tc['expected_pass'] and score >= tc['expected_score_min'] else "FAIL"

            print(f"\n{status} {tc['name']}")
            print(f"  结果：{'通过' if passed else '淘汰'}, 分数：{score}")
            print(f"  期望：{'通过' if tc['expected_pass'] else '淘汰'}, 最低分数：{tc['expected_score_min']}")

            if not passed:
                print(f"  淘汰原因：{details.get('reason', '未知')}")
            else:
                print(f"  技能匹配：{details.get('skill_matched_count', 0)}/{details.get('skill_total', 0)}")
                if details.get('skill_matches'):
                    print(f"  匹配技能：{', '.join(details['skill_matches'][:5])}")


def test_edge_cases():
    """测试边界情况"""
    print("\n" + "=" * 60)
    print("测试边界情况")
    print("=" * 60)

    from bossmaster import parse_experience_years

    # 测试中文数字解析
    print("\n[中文数字解析测试]")
    zh_cases = [
        ("3 年经验", 3),
        ("十年经验", 10),
        ("三年以上", 3),
        ("十二年开发经验", 12),
        ("两年工作经验", 2),
        ("五年以上 Java 经验", 5),
        ("八年后端经验", 8),
    ]

    for text, expected in zh_cases:
        result = parse_experience_years(text)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status} '{text}' -> {result} (期望：{expected})")

    default_rule = {
        "min_exp": 3,
        "edu": "本科",
        "keywords": ["Java", "Spring", "MySQL"]
    }

    edge_cases = [
        {
            "name": "空格和换行处理",
            "text": "3 年   Java\n开发经验，本科毕业",
            "description": "文本中包含多余空格和换行",
            "expected_pass": True
        },
        {
            "name": "大小写敏感",
            "text": "3 年 java 开发经验，熟悉 SPRING 和 mysql",
            "description": "技能关键词使用小写",
            "expected_pass": True
        },
        {
            "name": "同义词匹配",
            "text": "3 年后端开发经验，熟悉 Spring 框架和 MySQL 数据库",
            "description": "使用'后端'而非'Java'",
            "expected_pass": False  # 没有 Java 关键词
        },
        {
            "name": "中文数字支持",
            "text": "三年 Java 经验，本科",
            "description": "使用中文数字'三年'而非'3 年'",
            "expected_pass": True
        },
        {
            "name": "中文数字十二年",
            "text": "十二年 Java 开发经验，硕士学历",
            "description": "使用中文数字'十二年'",
            "expected_pass": True
        }
    ]

    print("\n[边界情况测试]")
    for tc in edge_cases:
        passed, score, details = filter_candidate(tc['text'], default_rule)
        status = "PASS" if passed == tc['expected_pass'] else "FAIL"
        print(f"\n{status} {tc['name']}")
        print(f"  描述：{tc['description']}")
        print(f"  文本：{tc['text']}")
        print(f"  结果：{'通过' if passed else '淘汰'}, 分数：{score}")


def main():
    """主函数"""
    print("BOSS 简历筛选器 - 筛选规则测试")
    print("=" * 60)

    test_required_conditions()
    test_full_filter()
    test_edge_cases()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
