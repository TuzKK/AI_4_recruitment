"""
BOSS 直聘候选人智能提取工具
修复版本 - 可靠的候选人查找
"""
import time
import json
import re
import hashlib
from datetime import datetime
from DrissionPage import ChromiumPage
import pandas as pd
import os


def load_job_config():
    """从外部配置文件加载职位要求"""
    config_file = "job_config.json"

    # 检查是否存在配置文件
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                job_requirements = config.get("job_requirements", {})

                # 对每个职位配置的 keywords 进行去重处理
                for job_name, rule in job_requirements.items():
                    if isinstance(rule, dict) and rule.get('keywords'):
                        seen = set()
                        unique_keywords = []
                        for kw in rule['keywords']:
                            kw_lower = kw.lower()
                            if kw_lower not in seen:
                                seen.add(kw_lower)
                                unique_keywords.append(kw)
                        rule['keywords'] = unique_keywords

                return job_requirements
        except Exception as e:
            print(f"读取配置文件出错：{e}")

    # 如果没有配置文件或读取出错，返回默认配置
    print("未找到配置文件，使用默认配置...")
    return {
        "default": {
            "min_exp": 0,
            "edu": "不限",
            "keywords": []
        }
    }


# 加载职位规则
JOB_RULES = load_job_config()


def filter_candidate(candidate_text, rule):
    """候选人筛选逻辑"""
    try:
        # 检查工作经验
        if rule.get("min_exp", 0) > 0:
            exp_match = re.search(r'(\d+)\s*年', candidate_text.replace(' ', ''))
            if exp_match:
                exp_years = int(exp_match.group(1))
                if rule.get("min_exp", 0) > exp_years:
                    return False
            else:
                if rule.get("min_exp", 0) > 0:
                    return False

        # 检查学历要求
        if rule.get("edu", "不限") != "不限":
            edu_keywords = {"博士": 6, "硕士": 5, "本科": 4, "大专": 3, "高中": 2, "中专": 1}
            candidate_edu_level = max([edu_keywords.get(word, 0) for word in edu_keywords if word in candidate_text])
            required_edu = edu_keywords.get(rule.get("edu", "不限"), 0)

            if required_edu > 0 and candidate_edu_level < required_edu:
                return False

        # 检查必要条件（硬性要求）
        required_conditions = rule.get("required_conditions", [])
        soft_qualities = ["责任感", "责任感强", "高度责任感", "表达能力", "较强的表达能力",
                          "主动性", "主动性强", "执行能力", "执行能力强", "沟通能力",
                          "团队合作", "抗压能力", "学习能力", "责任心"]

        for condition in required_conditions:
            if any(quality in condition for quality in soft_qualities):
                continue
            if "双证齐全" in condition or "学历证书" in condition or "学位证书" in condition:
                continue

            tech_match = re.search(r'熟悉 ([^\s，,]+)[\s，,、和及]?([^\s，,]*)[相关]? 技术', condition)
            if tech_match:
                tech1 = tech_match.group(1)
                tech2 = tech_match.group(2) if tech_match.group(2) else ""
                tech_found = False
                all_tech = [t.strip() for t in re.split(r'[\s，,、和及]', f"{tech1}{tech2}") if t.strip()]
                for tech in all_tech:
                    if tech in candidate_text:
                        tech_found = True
                        break
                if not tech_found:
                    return False
                continue

            hard_skill_keywords = ["Java", "Python", "MySQL", "Oracle", "Redis", "Kafka",
                                   "Spring", "MyBatis", "Dubbo", "微服务", "AI", "证书", "证"]
            if any(kw in condition for kw in hard_skill_keywords):
                condition_keywords = re.findall(r'[一 - 龥 a-zA-Z0-9]+', condition)
                filter_words = ["熟悉", "掌握", "具备", "相关", "技术", "技能", "经验", "优先",
                                "能够", "可以", "了解", "熟练", "使用", "的", "及", "和", "或"]
                filtered_keywords = [kw for kw in condition_keywords
                                   if len(kw) > 1 and kw not in filter_words]
                keyword_found = False
                for keyword in filtered_keywords:
                    if keyword in candidate_text:
                        keyword_found = True
                        break
                if not keyword_found and filtered_keywords:
                    return False

        # 检查关键字
        keywords = rule.get("keywords", [])
        if keywords and not any(keyword in candidate_text for keyword in keywords):
            return False

        return True

    except Exception as e:
        return True


def extract_candidates_by_comprehensive_analysis(page):
    """通过全面分析提取候选人 - 修复版本"""
    print("正在全面分析页面以提取候选人...")

    all_candidates = []
    seen_geek_ids = set()
    max_rounds_without_new = 5

    previous_total = 0
    consecutive_no_new = 0

    # 首先等待页面加载
    print("等待页面初始加载...")
    time.sleep(3)

    for scroll_round in range(20):
        print(f"\n滚动轮次 {scroll_round + 1}/20")

        # 先获取当前页面上的所有候选人，再滚动
        candidates_in_round = []
        current_round_ids = set()

        # 策略 1: 查找所有带有 data-geekid 的元素（不限制标签名）
        print("  策略 1: 查找 data-geekid 元素...")

        # 使用 CSS 选择器查找所有包含 data-geekid 属性的元素
        try:
            all_elements = page.eles('xpath://*[@data-geekid]')
            print(f"  找到 {len(all_elements)} 个带 data-geekid 的元素")

            for element in all_elements:
                geek_id = element.attr('data-geekid')

                if not geek_id or geek_id in seen_geek_ids or geek_id in current_round_ids:
                    continue

                current_round_ids.add(geek_id)

                text = element.text.strip() if element.text else ""

                # 检查是否包含候选人特征信息
                has_candidate_info = (
                    len(text) > 30 and
                    ('经验' in text or '本科' in text or '硕士' in text or
                     'Java' in text or '开发' in text or '工程师' in text or
                     re.search(r'\d+年', text) or re.search(r'\d+岁', text))
                )

                if not has_candidate_info:
                    continue

                # 提取姓名
                name = "未知"
                name_match = re.search(r'^([一 - 龥]{2,4})(?=\s|\\d|岁 | 年)', text)
                if name_match:
                    potential_name = name_match.group(1)
                    invalid_names = ['推荐', '位置', '面议', '优势', '推荐牛人', '编组',
                                   '备份', '立即', '沟通', '聊天', '联系', '在线',
                                   '今日', '最近', '邀请', '投递', '刷新', '收藏',
                                   '点赞', '分享', '高级', '资深', '初级', '中级']
                    if potential_name not in invalid_names:
                        name = potential_name

                candidates_in_round.append({
                    'geek_id': geek_id,
                    'name': name,
                    'summary': text,
                })

        except Exception as e:
            print(f"  策略 1 失败：{e}")

        # 策略 2: 如果策略 1 没有找到，尝试查找包含候选人信息的卡片
        if len(candidates_in_round) < 3:
            print("  策略 2: 查找候选人卡片...")

            # 查找常见的候选人卡片类名
            card_selectors = [
                'tag:div[class*="candidate"]',
                'tag:div[class*="geek"]',
                'tag:div[class*="card"]',
                'tag:div[class*="item"]',
            ]

            for selector in card_selectors:
                try:
                    cards = page.eles(selector)
                    for card in cards:
                        geek_id = card.attr('data-geekid') or card.attr('data-id')

                        if not geek_id or geek_id in seen_geek_ids or geek_id in current_round_ids:
                            continue

                        text = card.text.strip() if card.text else ""

                        has_candidate_info = (
                            len(text) > 30 and
                            ('经验' in text or '本科' in text or '硕士' in text or
                             'Java' in text or '开发' in text or '工程师' in text)
                        )

                        if has_candidate_info:
                            current_round_ids.add(geek_id)
                            name = "未知"
                            name_match = re.search(r'^([一 - 龥]{2,4})(?=\\d|岁 | 年)', text)
                            if name_match:
                                name = name_match.group(1)

                            candidates_in_round.append({
                                'geek_id': geek_id,
                                'name': name,
                                'summary': text,
                            })
                except Exception:
                    continue

        # 添加到总列表
        for c in candidates_in_round:
            all_candidates.append(c)
            seen_geek_ids.add(c['geek_id'])

        new_count = len(candidates_in_round)
        total_count = len(all_candidates)

        print(f"  本轮找到 {new_count} 个新候选人，累计 {total_count} 个")

        # 检查退出条件
        if new_count == 0:
            consecutive_no_new += 1
            if consecutive_no_new >= max_rounds_without_new:
                print(f"连续{consecutive_no_new}轮无新增，停止滚动")
                break
        else:
            consecutive_no_new = 0

        previous_total = total_count

        # 滚动到页面底部
        page.scroll.to_bottom()
        time.sleep(2)

    print(f"\n=== 提取完成 ===")
    print(f"总共找到 {len(all_candidates)} 个候选人")
    return all_candidates


def smart_scan_candidates(page, job_info):
    """智能扫描候选人"""
    print(f"开始智能扫描候选人...")

    raw_candidates = extract_candidates_by_comprehensive_analysis(page)
    print(f"原始提取到 {len(raw_candidates)} 个唯一候选人")

    # 显示前 5 个候选人的摘要
    print("\n前 5 个候选人摘要:")
    for i, c in enumerate(raw_candidates[:5]):
        print(f"  {i+1}. {c['name']} - {c['summary'][:80]}...")

    # 应用筛选规则
    filtered_candidates = []
    for i, candidate in enumerate(raw_candidates):
        if filter_candidate(candidate['summary'], job_info['rule']):
            filtered_candidates.append({
                "geek_id": candidate['geek_id'],
                "name": candidate['name'],
                "summary": candidate['summary'],
                "job_id": job_info['job_id'],
                "job_name": job_info['job_name'],
                "match_rule": job_info['rule_key'],
                "timestamp": datetime.now().isoformat()
            })

        if (i + 1) % 10 == 0:
            print(f"已处理 {i + 1}/{len(raw_candidates)} 个，匹配到 {len(filtered_candidates)} 个")

    print(f"\n筛选后剩余 {len(filtered_candidates)} 个候选人")
    return filtered_candidates


def run_smart_scan():
    """运行智能扫描"""
    print(">>> BOSS 直聘候选人智能提取工具")
    print("="*50)

    page = None
    try:
        print("正在连接到浏览器...")
        page = ChromiumPage()

        print("\n浏览器已打开，请手动导航到候选人推荐页面")
        print("例如：https://www.zhipin.com/web/chat/recommend")
        print("请确保页面完全加载后，等待 15 秒...")
        time.sleep(15)

        job_rules = load_job_config()

        specific_job_rule = None
        specific_job_name = None

        for job_name, rule in job_rules.items():
            if job_name != "default":
                specific_job_rule = rule
                specific_job_name = job_name
                break

        if specific_job_rule and specific_job_name:
            job_info = {
                "job_id": "unknown",
                "job_name": specific_job_name,
                "rule": specific_job_rule,
                "rule_key": specific_job_name
            }
            print(f"使用配置文件中的职位规则：{specific_job_name}")
        else:
            job_info = {
                "job_id": "unknown",
                "job_name": "推荐候选人",
                "rule": job_rules.get("default", {
                    "min_exp": 0,
                    "edu": "不限",
                    "keywords": []
                }),
                "rule_key": "default"
            }
            print("使用默认规则")

        print(f"过滤规则：经验≥{job_info['rule']['min_exp']}年，学历≥{job_info['rule']['edu']}")
        print(f"Keywords: {job_info['rule']['keywords']}")

        candidates = smart_scan_candidates(page, job_info)

        if candidates:
            timestamp = int(time.time())
            output_file = f"candidates_{job_info['job_name']}_{timestamp}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(candidates, f, ensure_ascii=False, indent=2)

            print(f"\n✅ 找到 {len(candidates)} 个匹配候选人")
            print(f"💾 结果已保存到：{output_file}")

            for i, candidate in enumerate(candidates[:10]):
                name = candidate.get('name', '未知')
                summary = candidate['summary'][:80]
                print(f"  {i+1}. {name} - {summary}...")

            if len(candidates) > 10:
                print(f"  ... 还有 {len(candidates) - 10} 个候选人")
        else:
            print("\n❌ 未找到匹配的候选人")
            print("可能原因:")
            print("  1. 页面还没有完全加载")
            print("  2. 过滤条件太严格")
            print("  3. 页面结构与预期不同")

    except Exception as e:
        print(f"程序执行出错：{e}")
        import traceback
        print(traceback.format_exc())

    finally:
        if page:
            print("\n--- 浏览器保持打开 ---")


if __name__ == "__main__":
    run_smart_scan()
