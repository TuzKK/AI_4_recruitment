"""
测试多轮滚动逻辑问题
"""

# 模拟滚动逻辑
processed_elements = set()
all_candidates = []

# 模拟每轮找到的元素 ID
round_data = [
    ['id1', 'id2', 'id3', 'id4', 'id5'],  # 第 1 轮
    ['id1', 'id2', 'id3', 'id4', 'id5', 'id6', 'id7'],  # 第 2 轮 - 多了 2 个
    ['id1', 'id2', 'id3', 'id4', 'id5', 'id6', 'id7', 'id8'],  # 第 3 轮 - 多了 1 个
    ['id1', 'id2', 'id3', 'id4', 'id5', 'id6', 'id7', 'id8'],  # 第 4 轮 - 无新增
]

previous_total = 0
consecutive_no_new = 0

for scroll_round, round_ids in enumerate(round_data):
    candidates_in_round = []

    for element_id in round_ids:
        if element_id in processed_elements:
            continue
        processed_elements.add(element_id)
        candidates_in_round.append(element_id)

    all_candidates.extend(candidates_in_round)
    current_total = len(all_candidates)

    print(f'第{scroll_round + 1}轮：新增{len(candidates_in_round)}人，累计{current_total}人')
    print(f'  本轮找到的新 ID: {candidates_in_round}')

    # 检查是否还在找到新候选人
    if current_total == previous_total and scroll_round >= 1:
        consecutive_no_new += 1
        if consecutive_no_new >= 2:
            print('连续两轮无新增，提前退出')
            break
    else:
        consecutive_no_new = 0

    previous_total = current_total

print(f'\n最终结果：{len(all_candidates)}个候选人')
print(f'expected: 8 个')
