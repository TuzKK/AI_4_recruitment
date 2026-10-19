import json

# 读取所有候选人文件
files = [
    'candidates_职位_1777454371.json',  # 第一轮 - 36 人
    'candidates_职位_1777456806.json',  # 第二轮 - 16 人
    'candidates_职位_1777456931.json',  # 第三轮 - 16 人
    'candidates_职位_1777457199.json',  # 第四轮 - 14 人
]

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        candidates = json.load(file)

    # 统计有效的候选人（有实际信息的）
    valid = 0
    invalid = 0
    for c in candidates:
        summary = c.get('summary', '')
        # 检查是否有实际候选人信息
        if len(summary) > 50 and '推荐牛人' not in summary and '该职位要' not in summary:
            valid += 1
        else:
            invalid += 1

    print(f'{f}: 总计{len(candidates)}人，有效{valid}人，无效{invalid}人')
