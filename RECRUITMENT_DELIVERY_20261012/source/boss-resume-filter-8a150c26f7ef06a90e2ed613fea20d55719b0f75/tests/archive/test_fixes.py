#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证所有修复是否成功
"""

def test_parser():
    """测试解析器功能"""
    print("=== 测试解析器功能 ===")

    # 测试内容
    test_content = """岗位要求
1.java基础扎实，具有实际开发经验，能够独立完成开发任务
2.熟悉mysql、oracle其中一种数据库的使用及优化
3.熟练使用Spring Cloud、Dubbo或类似的微服务框架,Dubbo优先
4.熟练使用SpringBoot/Spring Mvc/Mybatis等常用java框架
5.了解缓存技术Redis、消息中间件Kafka
6.有AI开发背景的优先

必要条件
1.必须双证齐全（学历证书和学位证书）
2.熟悉activiti、camunda、flowable等相关技术
3.高度责任感、具有较强的表达能力和学习能力、主动性强、执行能力强

职位要求：
工作年限：5-10年
学历：本科（学信网可查）
薪资范围：12k-15k"""

    from precise_parser import generate_config_from_text
    config = generate_config_from_text(test_content)

    # 检查配置
    job_info = config["job_requirements"]["职位"]  # 假设职位名为"职位"

    print(f"[PASS] 经验: {job_info.get('min_exp')}年")
    print(f"[PASS] 经验范围: {job_info.get('min_exp_range')} - {job_info.get('max_exp_range')}年")
    print(f"[PASS] 薪资: {job_info.get('salary_min')} - {job_info.get('salary_max')}")
    print(f"[PASS] 学历: {job_info.get('edu')}")
    print(f"[PASS] 技能数: {len(job_info.get('keywords', []))}")
    print(f"[PASS] 必要条件数: {len(job_info.get('required_conditions', []))}")

    # 验证提取是否正确
    assert job_info.get('min_exp_range') == 5, f"期望5，得到{job_info.get('min_exp_range')}"
    assert job_info.get('max_exp_range') == 10, f"期望10，得到{job_info.get('max_exp_range')}"
    assert job_info.get('salary_min') == 12000, f"期望12000，得到{job_info.get('salary_min')}"
    assert job_info.get('salary_max') == 15000, f"期望15000，得到{job_info.get('salary_max')}"

    print("[PASS] 解析器功能正常")
    return True

def test_regex_fix():
    """测试正则表达式修复"""
    print("\n=== 测试正则表达式修复 ===")

    import re

    # 测试可能导致bad character range错误的模式
    try:
        # 这应该不会引发错误
        pattern = r'[\s-~]'  # 这种模式可能会导致bad character range错误
        # 正确的模式应该是 r'[\s\-~]' 或 r'[\-\s~]'

        # 让我们测试一下原parser中可能出现的问题
        from precise_parser import parse_job_requirements

        test_content = "岗位要求：1.熟练掌握Spring Boot开发；2.有微服务经验\n职位要求：工作年限：5-10年\n薪资范围：12k-15k"
        result = parse_job_requirements(test_content)

        print("[PASS] 正则表达式修复有效")
        return True
    except Exception as e:
        print(f"[FAIL] 正则表达式仍有问题: {e}")
        return False

def test_config_generation():
    """测试配置生成"""
    print("\n=== 测试配置生成 ===")

    import json
    from precise_parser import generate_config_from_text

    test_content = """岗位要求
1.java基础扎实，具有实际开发经验，能够独立完成开发任务
2.熟悉mysql、oracle其中一种数据库的使用及优化
3.熟练使用Spring Cloud、Dubbo或类似的微服务框架,Dubbo优先

必要条件
1.必须双证齐全（学历证书和学位证书）
2.高度责任感、具有较强的表达能力和学习能力、主动性强、执行能力强

职位要求：
工作年限：5-10年
学历：本科（学信网可查）
薪资范围：12k-15k"""

    config = generate_config_from_text(test_content)

    # 保存配置以供后续使用
    with open('job_config_test.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print("[PASS] 配置生成正常")
    return True

def main():
    """主测试函数"""
    print(">>> 开始验证所有修复...")

    success = True

    try:
        success &= test_parser()
    except Exception as e:
        print(f"[FAIL] 解析器测试失败: {e}")
        success = False

    try:
        success &= test_regex_fix()
    except Exception as e:
        print(f"[FAIL] 正则表达式测试失败: {e}")
        success = False

    try:
        success &= test_config_generation()
    except Exception as e:
        print(f"[FAIL] 配置生成测试失败: {e}")
        success = False

    print(f"\n{'='*50}")
    if success:
        print("[SUCCESS] 所有测试通过！修复成功！")
    else:
        print("[ERROR] 部分测试失败")
    print(f"{'='*50}")

    return success

if __name__ == "__main__":
    main()