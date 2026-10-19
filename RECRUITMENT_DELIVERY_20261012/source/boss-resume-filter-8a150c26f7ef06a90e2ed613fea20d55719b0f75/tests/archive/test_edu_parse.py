"""测试 doc_parser 学历解析逻辑 - 用旧代码和新代码分别测试"""
import re

requirement_text = """职位描述【高级Java/Python工程师】：
1. Java/Python基础扎实，具有实际开发经验，能够独立完成开发任务；
2. 熟悉mysql、oracle其中一种数据库的使用及优化；
3. 熟练使用Spring Cloud、Dubbo或类似的微服务框架,Dubbo优先；
4. 熟练使用SpringBoot/Spring Mvc/Mybatis等常用java框架；
5.了解缓存技术Redis、消息中间件Kafka；
6. 熟悉activiti、camunda、flowable等相关技术；
7. 有AI开发背景（LLM、Al Agent、智能体、Spring AI、Langchain、智能问答、知识库）的优先；

职位要求：
1. 4-10年工作经验
2. 本科学历
3. 薪资范围：12k-15k
4. 工作地点：南京市雨花区凯润大厦2号楼5层

必要条件（硬性约束）：
1. 具有4年以上工作经验
2. 统招本科学历；"""

from doc_parser import parse_job_requirements

result = parse_job_requirements(requirement_text)
print(f"岗位: {result['job_title']}")
print(f"经验: {result['min_exp']}")
print(f"学历: {result['edu']}")
print(f"必要条件: {result['required_conditions']}")
print(f"技术条件: {result['tech_conditions']}")

# 如果学历不是本科，打印各段内容帮助诊断
if result['edu'] != '本科':
    print("\n=== 诊断信息 ===")
    # 模拟 parse_job_requirements 的分割逻辑
    required_section = ""
    if '必要条件' in requirement_text:
        parts = requirement_text.split('必要条件', 1)
        required_section = parts[1] if len(parts) > 1 else ""
        required_section = re.sub(r'^[\s:：（(]*.*?[）)]?[\s:：,，]*', '', required_section).strip()
    print(f"required_section: {required_section}")
    print(f"'博士' in required_section: {'博士' in required_section}")
    print(f"'本科' in required_section: {'本科' in required_section}")