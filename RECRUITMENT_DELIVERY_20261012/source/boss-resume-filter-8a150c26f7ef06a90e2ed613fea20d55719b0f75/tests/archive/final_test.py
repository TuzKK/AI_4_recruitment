"""
最终测试：使用正确的中文字符
"""
import re

# 使用正确的中文字符的测试内容
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

print("Test content with correct Chinese characters:")
print(repr(test_content))
print()

# 测试工作年限匹配
exp_match = re.search(r'工作年限[：:]\s*([\d\s\-~至—]+)年', test_content)
if exp_match:
    print(f"✓ Found experience: '{exp_match.group(1)}'")
    exp_range = exp_match.group(1).replace(' ', '')
    range_match = re.search(r'(\d+)[\s\-~至—]+(\d+)', exp_range)
    if range_match:
        print(f"  Range: {int(range_match.group(1))} - {int(range_match.group(2))} years")
else:
    print("✗ No experience match")

# 测试薪资范围匹配
salary_match = re.search(r'薪资范围[：:]\s*([\d,.]+k[\s\-~至—]+[\d,.]+k)', test_content, re.IGNORECASE)
if salary_match:
    print(f"✓ Found salary: '{salary_match.group(1)}'")
    salary_nums = re.findall(r'(\d+\.?\d*)', salary_match.group(1))
    if len(salary_nums) >= 2:
        min_sal = float(salary_nums[0])
        max_sal = float(salary_nums[1])
        min_sal *= 1000
        max_sal *= 1000
        print(f"  Calculated: {int(min_sal)} - {int(max_sal)}")
else:
    print("✗ No salary match")

# 测试完整的解析函数
import json
from precise_parser import parse_job_requirements

print("\nTesting the actual parser:")
result = parse_job_requirements(test_content)
print(f"Experience: {result['min_exp']} years")
print(f"Range: {result.get('min_exp_range', 'None')} - {result.get('max_exp_range', 'None')}")
print(f"Salary: {result.get('salary_min', 'None')} - {result.get('salary_max', 'None')}")

# 检查配置生成
from precise_parser import generate_config_from_text
config = generate_config_from_text(test_content)
for job_name, job_info in config["job_requirements"].items():
    if job_name != "default":
        print(f"\nConfig experience: {job_info['min_exp']}")
        if job_info.get('min_exp_range') and job_info.get('max_exp_range'):
            print(f"Config range: {job_info['min_exp_range']} - {job_info['max_exp_range']}")
        print(f"Config salary: {job_info.get('salary_min', 'None')} - {job_info.get('salary_max', 'None')}")