"""
测试正则表达式
"""
import re

# 原始测试内容
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

# 尝试不同格式的正则表达式
print("Original text snippet:")
print(repr(test_content))
print()

# 测试工作年限匹配
patterns_to_test = [
    r'工作年限[：:]\s*([\d\s\-~至—]+)年',
    r'工作年限[：:]\s*(.*)年',  # 捕获所有直到"年"的字符
    r'工作年限.{0,20}(\d+-?\d+)',  # 捕获紧随其后的数字组合
]

for i, pattern in enumerate(patterns_to_test):
    print(f"Test {i+1}: Pattern: {pattern}")
    matches = re.findall(pattern, test_content)
    search_result = re.search(pattern, test_content)
    if search_result:
        print(f"  Full match: {search_result.group()}")
        print(f"  Captured: {search_result.group(1)}")
    else:
        print("  No match found")
    print()

# 测试薪资范围匹配
salary_patterns = [
    r'薪资范围[：:]\s*([\d,.]+k[\s\-~至—]+[\d,.]+k)',
    r'薪资范围[：:]\s*(.*)',
    r'薪资范围.{0,30}((?:\d+k)[\s\-~至—]+(?:\d+k))',
]

print("Testing salary patterns:")
for i, pattern in enumerate(salary_patterns):
    print(f"Salary Test {i+1}: Pattern: {pattern}")
    search_result = re.search(pattern, test_content)
    if search_result:
        print(f"  Full match: {search_result.group()}")
        if search_result.groups():
            print(f"  Captured: {search_result.group(1)}")
        else:
            print("  No captures")
    else:
        print("  No match found")
    print()

# 让我们也直接检查文本中是否存在这些字符串
print("Direct string checks:")
print(f"Contains '工作年限': {'工作年限' in test_content}")
print(f"Contains '薪资范围': {'薪资范围' in test_content}")
print(f"Contains '5-10': {'5-10' in test_content}")
print(f"Contains '12k-15k': {'12k-15k' in test_content}")

# 检查文本编码问题
print("\nEncoding check:")
try:
    # 尝试解码
    decoded = test_content.encode('utf-8').decode('utf-8')
    print("UTF-8 decode successful")
except Exception:
    print("UTF-8 decode failed")

# 查看具体部分
pos_req_start = test_content.find("职位要求")
if pos_req_start != -1:
    # 提取职位要求部分的后面内容
    after_pos = test_content[pos_req_start:]
    print(f"\nAfter '职位要求': {repr(after_pos[:100])}")