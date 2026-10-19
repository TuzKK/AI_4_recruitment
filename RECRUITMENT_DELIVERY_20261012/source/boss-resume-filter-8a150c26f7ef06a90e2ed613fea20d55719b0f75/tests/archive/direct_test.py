"""
直接测试精确解析器功能
"""
import json

# 读取样本招聘信息
with open('sample_job_requirements.txt', 'r', encoding='utf-8') as f:
    sample_content = f.read()

# 导入并测试解析器
from precise_parser import generate_config_from_text

print("Testing precise parser with sample job requirements...")

# 生成配置
config = generate_config_from_text(sample_content)

# 保存配置文件（会覆盖现有的）
with open('job_config_test.json', 'w', encoding='utf-8') as f:
    json.dump(config, f, ensure_ascii=False, indent=2)

print("Configuration generated successfully!")

# 检查配置文件内容
print("\nGenerated config keys:")
for key in config.get("job_requirements", {}).keys():
    print(f"- {key}")

# 检查非默认配置项
for job_name, job_info in config["job_requirements"].items():
    if job_name != "default":
        print(f"\nJob: {job_name}")
        print(f"Experience: {job_info.get('min_exp', 'Not found')} years")
        print(f"Exp Range: {job_info.get('min_exp_range', 'Not found')} - {job_info.get('max_exp_range', 'Not found')}")
        print(f"Salary: {job_info.get('salary_min', 'Not found')} - {job_info.get('salary_max', 'Not found')}")
        print(f"Education: {job_info.get('edu', 'Not found')}")
        print(f"Skills count: {len(job_info.get('keywords', []))}")
        print(f"Required conditions: {len(job_info.get('required_conditions', []))}")
        print(f"Personal qualities: {len(job_info.get('personal_qualities', []))}")
        print(f"Job requirements: {len(job_info.get('job_requirements', []))}")

print("\nCheck job_config_test.json for full details.")