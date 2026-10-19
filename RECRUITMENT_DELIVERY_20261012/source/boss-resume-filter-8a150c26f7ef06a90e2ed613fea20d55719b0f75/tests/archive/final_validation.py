"""
测试精确解析器主功能
"""
import json
from precise_parser import generate_config_from_text

# 直接使用正确的内容测试
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

print("Testing precise parser main functionality...")

try:
    config = generate_config_from_text(test_content)

    # 保存配置
    with open('job_config_final_test.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print("✓ Configuration generated successfully!")

    # 输出重要信息
    for job_name, job_info in config["job_requirements"].items():
        if job_name != "default":
            print(f"\nPosition: {job_name}")
            print(f"  Experience: {job_info.get('min_exp', 'N/A')} years")
            print(f"  Exp Range: {job_info.get('min_exp_range', 'N/A')} - {job_info.get('max_exp_range', 'N/A')}")
            print(f"  Salary: {job_info.get('salary_min', 'N/A')} - {job_info.get('salary_max', 'N/A')}")
            print(f"  Education: {job_info.get('edu', 'N/A')}")
            print(f"  Skills Count: {len(job_info.get('keywords', []))}")
            print(f"  Required Conditions: {len(job_info.get('required_conditions', []))}")

            # 验证是否正确提取了关键信息
            assert job_info.get('min_exp_range') == 5, f"Expected min_exp_range=5, got {job_info.get('min_exp_range')}"
            assert job_info.get('max_exp_range') == 10, f"Expected max_exp_range=10, got {job_info.get('max_exp_range')}"
            assert job_info.get('salary_min') == 12000, f"Expected salary_min=12000, got {job_info.get('salary_min')}"
            assert job_info.get('salary_max') == 15000, f"Expected salary_max=15000, got {job_info.get('salary_max')}"

            print("  ✓ All assertions passed! The parser correctly extracts:")
            print("    - Experience range: 5-10 years")
            print("    - Salary range: 12k-15k (12000-15000)")

    print("\n✓ Parser is working correctly! Configuration saved to job_config_final_test.json")

except Exception as e:
    print(f"✗ Error occurred: {e}")
    import traceback
    traceback.print_exc()