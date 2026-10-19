"""
BOSS直聘候选人获取 - 当前页面监听模式（测试版）
用于验证功能是否正常工作
"""
import time
import json
import random
import re
import hashlib
from datetime import datetime
from DrissionPage import ChromiumPage
import pandas as pd


# 本地岗位规则库
JOB_RULES = {
    "后端开发工程师": {
        "min_exp": 3,
        "edu": "本科",
        "keywords": ["Python", "Django", "Java", "Spring", "MySQL", "Redis"]
    },
    "前端开发工程师": {
        "min_exp": 2,
        "edu": "本科",
        "keywords": ["React", "Vue", "JavaScript", "HTML", "CSS", "TypeScript"]
    },
    "产品经理": {
        "min_exp": 5,
        "edu": "本科",
        "keywords": ["B端", "SAAS", "产品设计", "项目管理", "需求分析"]
    },
    "Java开发工程师": {
        "min_exp": 2,
        "edu": "本科",
        "keywords": ["Java", "Spring", "MyBatis", "SpringBoot", "MySQL", "Redis"]
    },
    "Python开发工程师": {
        "min_exp": 2,
        "edu": "本科",
        "keywords": ["Python", "Django", "Flask", "Tornado", "SQLAlchemy"]
    },
    "算法工程师": {
        "min_exp": 3,
        "edu": "硕士",
        "keywords": ["机器学习", "深度学习", "TensorFlow", "PyTorch", "算法"]
    }
}


def extract_job_info_from_page(page):
    """
    从当前页面提取职位信息
    """
    print("正在从当前页面提取职位信息...")

    try:
        # 获取当前URL
        current_url = page.url
        print(f"当前页面URL: {current_url}")

        # 尝试从URL中提取jobId（支持多种URL格式）
        job_id = "unknown"
        job_id_patterns = [
            r'jobId=(\d+)',
            r'/job/(.+?)(?:\?|$)',
            r'/job_detail/(.+?)(?:\?|$)',
            r'jid=(.+?)(?:&|$)'
        ]

        for pattern in job_id_patterns:
            job_id_match = re.search(pattern, current_url)
            if job_id_match:
                job_id = job_id_match.group(1)
                print(f"提取到职位ID: {job_id}")
                break

        # 获取职位名称 - 增加对聊天推荐页面的支持
        job_name = ""
        title_selectors = [
            '.job-name-text', '.job-title', '.position-name',
            'h1', 'h2', '.name', '.title',
            # 聊天推荐页面可能的选择器
            '.job-info .name', '.job-title-text', '.position-title',
            '.job-card .name', '[data-job-title]'
        ]

        for selector in title_selectors:
            try:
                title_element = page.ele(selector)
                if title_element:
                    job_name = title_element.text.strip()
                    if job_name and len(job_name) > 2:
                        break
            except Exception:
                continue

        # 如果通过选择器没找到，尝试从页面其他地方获取
        if not job_name or len(job_name) <= 2:
            # 尝试从页面标题获取
            try:
                title = page.title
                if title and ('-' in title or '|' in title):
                    parts = re.split(r'[-|]', title)
                    for part in parts:
                        part = part.strip()
                        if any(keyword in part for keyword in ['工程师', '经理', '总监', '主管', '专员', '助理', '顾问', '设计师', '推荐']):
                            job_name = part
                            break
            except Exception:
                pass

        # 如果还是没找到，尝试从URL路径获取
        if not job_name or len(job_name) <= 2:
            path_parts = current_url.split('/')
            for part in path_parts:
                if part and len(part) > 2 and any(keyword in part for keyword in ['engineer', 'manager', 'developer', 'intern', 'tech', 'product']):
                    job_name = part
                    break

        # 作为最后手段，尝试从页面上的职位相关文字中提取
        if not job_name or len(job_name) <= 2:
            try:
                # 搜索页面上所有可能包含职位信息的元素
                all_elements = page.eles('text:工程师') + page.eles('text:开发') + page.eles('text:经理') + page.eles('text:技术')

                for element in all_elements:
                    text = element.text.strip()
                    if len(text) > 2 and len(text) < 20:
                        job_name = text
                        break
            except Exception:
                pass

        # 如果仍未找到，使用URL中的有用部分
        if not job_name or len(job_name) <= 2:
            # 尝试从URL中提取有意义的部分
            if '/chat/recommend' in current_url:
                job_name = "推荐候选人"
            elif '/geek/recommend' in current_url:
                job_name = "推荐候选人"
            else:
                # 从URL路径的最后几段中找寻可能的职位名
                path_parts = current_url.split('/')
                for part in reversed(path_parts[-3:]):  # 检查最后3段
                    if part and len(part) > 2 and not any(x in part.lower() for x in ['job', 'detail', 'page', 'web', 'geek', 'chat', 'recommend']):
                        job_name = part
                        break

        print(f"提取到职位名称: {job_name}")

        # 获取对应的筛选规则
        rule = None
        matched_key = None

        # 精确匹配
        if job_name in JOB_RULES:
            rule = JOB_RULES[job_name]
            matched_key = job_name
        else:
            # 模糊匹配 - 改进匹配逻辑
            best_match_score = 0
            for key in JOB_RULES:
                score = 0
                # 计算相似度
                if job_name in key:
                    score += 2
                if key in job_name:
                    score += 1
                # 检查共同关键词
                for keyword in ['工程师', '开发', '前端', '后端', 'java', 'python', '算法', '产品', '设计', '测试', '运维', '架构']:
                    if keyword in job_name and keyword in key:
                        score += 3
                        break

                if score > best_match_score:
                    best_match_score = score
                    rule = JOB_RULES[key]
                    matched_key = key

        if rule and best_match_score > 0:
            print(f"找到匹配的筛选规则: {matched_key} (匹配度: {best_match_score})")
            return {
                "job_id": job_id,
                "job_name": job_name,
                "rule": rule,
                "rule_key": matched_key
            }
        else:
            print("未找到该岗位的筛选规则，使用默认规则")
            return {
                "job_id": job_id,
                "job_name": job_name,
                "rule": {
                    "min_exp": 1,
                    "edu": "不限",
                    "keywords": []
                },
                "rule_key": "default"
            }

    except Exception as e:
        print(f"从页面提取职位信息时出错: {e}")
        import traceback
        print(traceback.format_exc())
        return None


def my_filter_logic(summary_info, rule):
    """
    候选人筛选逻辑
    """
    try:
        # 提取经验信息
        exp_match = re.search(r'(\d+)\s*年', summary_info.replace(' ', ''))
        if exp_match:
            exp_years = int(exp_match.group(1))
            if rule.get("min_exp", 0) > exp_years:
                print(f"  └─ 筛选未通过: 经验不足 ({exp_years}年 < {rule.get('min_exp', 0)}年)")
                return False  # 经验不足
        else:
            # 如果找不到明确的年份，但规则要求至少1年以上经验，则跳过
            if rule.get("min_exp", 0) > 1:
                print(f"  └─ 筛选未通过: 未找到明确经验年限")
                return False

        # 检查学历要求
        edu_keywords = {
            "博士": 4,
            "硕士": 3,
            "本科": 2,
            "大专": 1,
            "高中": 0,
            "中专": 0
        }

        candidate_edu_level = 0
        candidate_edu_text = ""
        for edu_word, level in edu_keywords.items():
            if edu_word in summary_info:
                candidate_edu_level = level
                candidate_edu_text = edu_word
                break

        required_edu_level = edu_keywords.get(rule.get("edu", "不限"), 0)
        if required_edu_level > 0 and required_edu_level > candidate_edu_level:
            print(f"  └─ 筛选未通过: 学历不够 ({candidate_edu_text} < {rule.get('edu', '不限')})")
            return False  # 学历不够

        # 检查关键字
        keywords = rule.get("keywords", [])
        if keywords:
            # 检查候选人信息中是否包含任一关键词
            matched_keywords = [keyword for keyword in keywords if keyword in summary_info]
            if not matched_keywords:
                print(f"  └─ 筛选未通过: 不包含必要技能关键词 {keywords}")
                return False  # 不包含必要技能
            else:
                print(f"  └─ 技能匹配: 找到关键词 {matched_keywords}")

        # 如果都通过了，返回True
        print(f"  └─ 筛选通过 ✓")
        return True

    except Exception as e:
        print(f"筛选逻辑执行出错: {e}")
        return True  # 如果出错，默认通过以避免遗漏


def start_candidate_scanning(page, job_info):
    """
    开始扫描候选人卡片
    """
    print(f"开始扫描职位 '{job_info['job_name']}' 的候选人...")

    processed_geeks = set()
    candidates_found = []

    scroll_count = 0
    max_scrolls = 10  # 减少滚动次数以便快速测试
    consecutive_empty_scrolls = 0  # 连续空滚动计数
    max_consecutive_empty = 2  # 最多允许2次连续空滚动

    try:
        while scroll_count < max_scrolls and consecutive_empty_scrolls < max_consecutive_empty:
            print(f"正在进行第 {scroll_count + 1} 次滚动...")

            # 获取当前可见的所有候选人卡片 - 使用更广泛的选择器
            card_selectors = [
                'div.job-geek-item', 'div.geek-item', 'div.recommend-list-item',
                'div.geek-card', 'div.recommend-card', 'div.candidate-card',
                '[data-jobid]', '[data-geekid]', '[data-gid]',
                '[class*="geek-item"]', '[class*="recommend"]', '[class*="candidate"]',
                '[class*="job-geek"]', '[class*="geek-card"]'
            ]

            cards = []
            for selector in card_selectors:
                try:
                    elements = page.eles(selector)
                    if elements:
                        # 过滤掉明显不是候选人卡片的元素
                        filtered_elements = []
                        for elem in elements:
                            # 检查元素是否包含候选人相关信息
                            elem_text = elem.text[:300]  # 增加文本长度以更好识别
                            if any(keyword in elem_text for keyword in ['经验', '年', '本科', '硕士', '大专', '岁', '在职', '离职', '期望', '沟通', '聊一聊', '已沟通']):
                                filtered_elements.append(elem)

                        if filtered_elements:
                            cards.extend(filtered_elements)
                            print(f"使用选择器 '{selector}' 找到 {len(filtered_elements)} 个符合条件的候选人卡片")
                            break  # 找到卡片后就跳出
                except Exception as e:
                    continue

            if not cards:
                print("未找到候选人卡片，继续滚动...")

                # 尝试通过文本内容检测候选人卡片
                try:
                    all_divs = page.eles('tag:div')
                    potential_cards = []
                    for div in all_divs:
                        div_text = div.text[:200]
                        # 使用更宽松的条件检测候选人卡片
                        if (len(div_text) > 10 and  # 至少有一定长度
                            any(kw in div_text for kw in ['聊一聊', '立即沟通', '不合适', '待沟通', '已沟通']) and
                            any(kw in div_text for kw in ['年', '经验', '本科', '硕士', '大专', '在职', '离职'])):
                            # 检查是否有重复的ID避免重复计数
                            div_id = div.attr('id') or div.attr('data-id') or div.attr('data-geekid') or div.text[:30]
                            if div_id not in [pc.text[:30] for pc in potential_cards]:
                                potential_cards.append(div)

                    if potential_cards:
                        cards = potential_cards
                        print(f"通过文本匹配找到 {len(cards)} 个候选人卡片")
                    else:
                        consecutive_empty_scrolls += 1
                        print(f"未检测到候选人卡片，连续空滚动次数: {consecutive_empty_scrolls}")

                except Exception as e:
                    print(f"尝试文本匹配时出错: {e}")
                    consecutive_empty_scrolls += 1
            else:
                consecutive_empty_scrolls = 0  # 重置连续空滚动计数
                print(f"当前批次找到 {len(cards)} 个候选人卡片")

                for idx, card in enumerate(cards):
                    try:
                        # 获取候选人唯一标识
                        geek_id = (
                            card.attr('data-geekid') or
                            card.attr('data-id') or
                            card.attr('data-gid') or
                            card.attr('data-gid') or
                            hashlib.md5(card.text[:50].encode()).hexdigest()[:12] if card.text else
                            f"card_{idx}_{len(processed_geeks)}_{int(time.time()) % 1000}"
                        )

                        if geek_id in processed_geeks:
                            continue

                        # 获取候选人完整信息
                        summary_info = card.text

                        print(f"正在分析候选人 #{idx+1}: {summary_info[:50]}...")

                        # 应用筛选逻辑
                        is_pass = my_filter_logic(summary_info, job_info['rule'])

                        if is_pass:
                            print(f"✓ 发现匹配候选人：{summary_info[:50]}...")

                            # 解析候选人详细信息
                            candidate_info = {
                                "geek_id": geek_id,
                                "summary": summary_info,
                                "job_id": job_info['job_id'],
                                "job_name": job_info['job_name'],
                                "match_rule": job_info['rule_key'],
                                "timestamp": datetime.now().isoformat(),
                                "details": parse_candidate_details(summary_info)
                            }

                            candidates_found.append(candidate_info)

                        processed_geeks.add(geek_id)

                    except Exception as e:
                        print(f"处理候选人卡片时出错: {e}")
                        continue

            # 滚动页面加载更多
            page.scroll.to_bottom()
            scroll_count += 1

            # 等待页面加载 - 对于前几次滚动，使用较短的等待时间
            if scroll_count <= 3:
                # 前3次滚动快速检测
                wait_time = random.uniform(1.5, 3)
            else:
                # 后续滚动稍微增加等待时间
                wait_time = random.uniform(2, 4)

            print(f"等待 {wait_time:.2f} 秒让页面加载...")
            time.sleep(wait_time)

        print(f"扫描完成，共找到 {len(candidates_found)} 个匹配的候选人")
        if consecutive_empty_scrolls >= max_consecutive_empty:
            print(f"达到连续 {max_consecutive_empty} 次未检测到新卡片，提前结束扫描")

        return candidates_found

    except Exception as e:
        print(f"扫描候选人过程中出错: {e}")
        import traceback
        print(traceback.format_exc())
        return []


def parse_candidate_details(summary_info):
    """
    解析候选人详细信息
    """
    details = {}

    # 提取姓名（通常在开头部分）
    lines = summary_info.split('\n')
    if lines:
        first_line = lines[0].strip()
        # 姓名通常是比较短的中文字符串
        name_match = re.search(r'^([^\d\s]{2,4})[\s\n]', first_line + '\n')
        if name_match:
            details['name'] = name_match.group(1)
        else:
            # 尝试从第一行中提取可能的姓名
            chinese_chars = ''.join(re.findall(r'[一-鿿]{2,4}', first_line))
            if len(chinese_chars) >= 2:
                details['name'] = chinese_chars[:4]

    # 提取年龄
    age_match = re.search(r'(\d{1,2})\s*岁', summary_info)
    if age_match:
        details['age'] = age_match.group(1)

    # 提取工作经验
    exp_match = re.search(r'(\d+)\s*年\s*经验|经验\s*(\d+)\s*年|(\d+)\s*年', summary_info)
    if exp_match:
        exp_year = exp_match.group(1) or exp_match.group(2) or exp_match.group(3)
        if exp_year:
            details['experience_years'] = int(exp_match.group(1) or exp_match.group(2) or exp_match.group(3))

    # 提取学历
    edu_pattern = r'(博士|硕士|本科|大专|高中|中专)'
    edu_match = re.search(edu_pattern, summary_info)
    if edu_match:
        details['education'] = edu_match.group(1)

    # 提取当前职位和公司
    # 匹配 "职位 - 公司" 或 "公司 - 职位" 格式
    company_pos_patterns = [
        r'(.{2,20})\s*[,-]\s*(.{2,30})\s*·\s*(.{2,20})',
        r'(.{2,30})\s*·\s*(.{2,20})',
        r'就职于\s*(.{2,30})\s*(.{2,20})'
    ]

    for pattern in company_pos_patterns:
        match = re.search(pattern, summary_info)
        if match:
            groups = match.groups()
            # 判断哪个是公司，哪个是职位
            for i, item in enumerate(groups):
                if item and len(item) > 1:
                    if any(kw in item for kw in ['公司', '集团', '科技', '网络', '有限', '股份', '银行', '证券', '基金', '保险']):
                        details['company'] = item
                    elif any(kw in item for kw in ['工程师', '经理', '总监', '主管', '专员', '助理', '开发', '测试', '运维', '产品', '设计', '运营']):
                        details['position'] = item
            break

    # 提取技能关键词
    # 使用常见的技能关键词进行匹配
    tech_keywords = [
        'Python', 'Java', 'C++', 'JavaScript', 'Go', 'SQL', 'MySQL', 'Redis', 'Docker',
        'Kubernetes', 'React', 'Vue', 'Angular', 'Spring', 'Node.js', 'Flutter', 'Swift',
        'Android', 'iOS', '机器学习', '深度学习', 'AI', '数据分析', '算法', '架构', '运维'
    ]

    found_skills = []
    for skill in tech_keywords:
        if skill in summary_info:
            found_skills.append(skill)

    if found_skills:
        details['skills'] = found_skills

    return details


def run_test():
    """
    运行测试
    """
    print("="*60)
    print("BOSS直聘候选人获取 - 当前页面监听模式（测试版）")
    print("="*60)

    page = None
    try:
        # 连接到浏览器
        print("正在连接到浏览器...")
        page = ChromiumPage()

        print("\n浏览器已打开，请手动导航到候选人推荐页面")
        print("URL应类似: https://www.zhipin.com/web/geek/recommend?jobId=xxxx")

        # 等待10秒让用户导航
        print("等待10秒供您导航到目标页面...")
        time.sleep(10)

        # 提取职位信息
        job_info = extract_job_info_from_page(page)
        if not job_info:
            print("无法提取到职位信息，程序退出")
            return

        # 确认开始扫描
        print(f"\n准备开始扫描职位 '{job_info['job_name']}' 的候选人...")
        print(f"筛选规则: 最低经验 {job_info['rule']['min_exp']} 年，最低学历 {job_info['rule']['edu']}")
        if job_info['rule']['keywords']:
            print(f"技能要求: {', '.join(job_info['rule']['keywords'])}")

        # 开始扫描候选人（减少滚动次数用于测试）
        candidates = start_candidate_scanning(page, job_info)

        if candidates:
            # 保存结果
            timestamp = int(time.time())
            output_file = f"test_candidates_{job_info['job_name']}_{timestamp}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(candidates, f, ensure_ascii=False, indent=2)

            print(f"\n扫描完成！")
            print(f"找到 {len(candidates)} 个匹配候选人")
            print(f"结果已保存到: {output_file}")

            # 显示匹配的候选人统计
            print(f"\n匹配详情:")
            for i, candidate in enumerate(candidates[:5]):  # 显示前5个候选人的详细信息
                details = candidate.get('details', {})
                name = details.get('name', '未知')
                exp = details.get('experience_years', '未知')
                edu = details.get('education', '未知')
                skills = ', '.join(details.get('skills', [])) if details.get('skills') else '未识别'

                print(f"  {i+1}. 姓名: {name}, 经验: {exp}年, 学历: {edu}, 技能: {skills}")

            if len(candidates) > 5:
                print(f"  ... 还有 {len(candidates) - 5} 个候选人")

            # 也可以保存为Excel
            try:
                df_data = []
                for candidate in candidates:
                    details = candidate.get('details', {})
                    df_data.append({
                        "候选人ID": candidate['geek_id'],
                        "姓名": details.get('name', '未知'),
                        "摘要信息": candidate['summary'],
                        "经验年限": details.get('experience_years', '未知'),
                        "学历": details.get('education', '未知'),
                        "当前公司": details.get('company', '未知'),
                        "当前职位": details.get('position', '未知'),
                        "技能": ', '.join(details.get('skills', [])) if details.get('skills') else '',
                        "职位ID": candidate['job_id'],
                        "职位名称": candidate['job_name'],
                        "匹配规则": candidate['match_rule'],
                        "时间戳": candidate['timestamp']
                    })

                df = pd.DataFrame(df_data)
                excel_file = f"test_candidates_{job_info['job_name']}_{timestamp}.xlsx"
                df.to_excel(excel_file, index=False)
                print(f"Excel格式结果已保存到: {excel_file}")
            except Exception as ex:
                print(f"保存Excel时出错: {ex}")

        else:
            print("未找到匹配的候选人")
            print("提示: 可能是筛选条件过于严格，或当前页面没有加载足够的候选人数据")

    except Exception as e:
        print(f"程序执行出错: {e}")
        import traceback
        print(traceback.format_exc())

    finally:
        if page:
            print("\n浏览器保持打开，您可以在其中继续操作")


if __name__ == "__main__":
    run_test()