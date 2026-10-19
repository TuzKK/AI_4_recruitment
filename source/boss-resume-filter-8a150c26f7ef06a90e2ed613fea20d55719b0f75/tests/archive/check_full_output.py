"""
检查解析器完整输出
"""
from precise_parser import parse_job_requirements

# 测试内容
test_content = """岗位要求
1.java基础扎实，具有实际开发经验，能够独立完成开发任务
2.熟悉mysql、oracle其中一种数据库的使用及优化
3.熟练使用Spring Cloud、Dubbo或类似的微服务框架,Dubo优先
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

result = parse_job_requirements(test_content)

print("Full parsing result:")
print(f"Job Title: {result['job_title']}")
print(f"Min Exp: {result['min_exp']}")
print(f"Min Exp Range: {result.get('min_exp_range')}")
print(f"Max Exp Range: {result.get('max_exp_range')}")
print(f"Salary Min: {result.get('salary_min')}")
print(f"Salary Max: {result.get('salary_max')}")
print(f"Education: {result['edu']}")

# 检查generate_config_from_text是否使用了薪资信息
from precise_parser import generate_config_from_text
config = generate_config_from_text(test_content)

print("\\nConfig result:")
job_info = config["job_requirements"]["职位"]  # 假设职位名为"职位"
print(f"Config Min Exp: {job_info.get('min_exp')}")
print(f"Config Salary Min: {job_info.get('salary_min')}")
print(f"Config Salary Max: {job_info.get('salary_max')}")