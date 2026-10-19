"""
测试文本编码问题
"""
import re

# 直接使用正确的文本
text_content = """岗位要求
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

print("Raw text:")
print(repr(text_content))
print()

# 手动执行解析逻辑的步骤
clean_text = text_content.replace('\r', ' ').replace('\t', ' ')
print("Clean text processed:")

# 查找经验信息
exp_match = re.search(r'工作年限[：:]\s*([\d\s\-~至—]+)年', clean_text)
if exp_match:
    print(f"✓ Found experience match: '{exp_match.group(1)}'")
    exp_range = exp_match.group(1).replace(' ', '')
    print(f"After removing spaces: '{exp_range}'")

    range_match = re.search(r'(\d+)[\s\-~至—]+(\d+)', exp_range)
    if range_match:
        min_exp = int(range_match.group(1))
        max_exp = int(range_match.group(2))
        print(f"✓ Range detected: {min_exp} to {max_exp}, using min: {min_exp}")
        final_exp = min_exp
    else:
        single_match = re.search(r'(\d+)', exp_range)
        if single_match:
            final_exp = int(single_match.group(1))
            print(f"✓ Single number: {final_exp}")
        else:
            final_exp = 0
            print("✗ No number found")
else:
    print("✗ No experience pattern matched")
    final_exp = 0

print(f"Final exp value: {final_exp}")

# 查找薪资信息
salary_match = re.search(r'薪资范围[：:]\s*([\d,.]+k[\s\-~至—]+[\d,.]+k)', clean_text, re.IGNORECASE)
if salary_match:
    print(f"✓ Found salary match: '{salary_match.group(1)}'")
    salary_nums = re.findall(r'(\d+\.?\d*)', salary_match.group(1))
    if len(salary_nums) >= 2:
        min_sal = float(salary_nums[0])
        max_sal = float(salary_nums[1])

        min_sal *= 1000
        max_sal *= 1000

        print(f"✓ Salary calculated: {int(min_sal)} - {int(max_sal)}")
        salary_min = int(min_sal)
        salary_max = int(max_sal)
    else:
        print("✗ Could not extract both salary numbers")
        salary_min = None
        salary_max = None
else:
    print("✗ No salary pattern matched")
    salary_min = None
    salary_max = None

# 提取section
gangwei_jinyaun_idx = clean_text.find("岗位要求")
biyao_tiaojian_idx = clean_text.find("必要条件")
zhiwei_yaoqiu_idx = clean_text.find("职位要求")

print(f"Section indices: 岗位要求={gangwei_jinyaun_idx}, 必要条件={biyao_tiaojian_idx}, 职位要求={zhiwei_yaoqiu_idx}")

section_indices = []
if gangwei_jinyaun_idx != -1:
    section_indices.append((gangwei_jinyaun_idx, "岗位要求"))
if biyao_tiaojian_idx != -1:
    section_indices.append((biyao_tiaojian_idx, "必要条件"))
if zhiwei_yaoqiu_idx != -1:
    section_indices.append((zhiwei_yaoqiu_idx, "职位要求"))

section_indices.sort()
print(f"Sorted indices: {section_indices}")

sections = {}
for i, (idx, section_name) in enumerate(section_indices):
    start_pos = idx + len(section_name)
    while start_pos < len(clean_text) and clean_text[start_pos] in [':', '：', ' ', '\n', '\t']:
        start_pos += 1

    end_pos = len(clean_text)
    if i < len(section_indices) - 1:
        end_pos = section_indices[i + 1][0]

    content = clean_text[start_pos:end_pos].strip()

    lines = content.split('\n')
    processed_lines = []
    for line in lines:
        if not any(other_section in line for other_section in ['岗位要求', '必要条件', '职位要求'] if other_section != section_name):
            processed_lines.append(line)
        else:
            break

    sections[section_name] = '\n'.join(processed_lines).strip()

print("\nExtracted sections:")
for name, content in sections.items():
    print(f"'{name}': {repr(content)}")

# 在职位要求部分查找经验
if "职位要求" in sections:
    pos_text = sections["职位要求"]
    print(f"\nIn 职位要求 section:")
    print(f"Text: {repr(pos_text)}")

    exp_line_match = re.search(r'工作年限[：:]\s*([\d\s\-~至—]+)年', pos_text)
    if exp_line_match:
        print(f"✓ Found experience in section: '{exp_line_match.group(1)}'")
    else:
        print("✗ No experience in section")

    salary_line_match = re.search(r'薪资范围[：:]\s*([\d,.]+k[\s\-~至—]+[\d,.]+k)', pos_text, re.IGNORECASE)
    if salary_line_match:
        print(f"✓ Found salary in section: '{salary_line_match.group(1)}'")
    else:
        print("✗ No salary in section")

print(f"\nFinal results: exp={final_exp}, salary={salary_min}-{salary_max}")