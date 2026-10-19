"""
招聘需求配置生成器
根据您的具体需求生成 job_config.json 文件
"""
import json
import os


def deduplicate_keywords(keywords: list) -> list:
    """对关键词列表进行去重（忽略大小写）"""
    seen = set()
    unique = []
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower not in seen:
            seen.add(kw_lower)
            unique.append(kw)
    return unique


def get_job_requirements():
    """获取用户的招聘需求"""
    print("🎯 招聘需求配置生成器")
    print("="*50)

    job_reqs = {}

    print("请输入招聘需求配置（输入'done'完成）：")

    while True:
        print("\n--- 新增职位配置 ---")
        job_name = input("职位名称 (如：'Java 开发工程师', '产品经理'): ").strip()

        if job_name.lower() == 'done':
            break

        if not job_name:
            print("职位名称不能为空，请重新输入。")
            continue

        print(f"\n配置 {job_name} 的要求：")

        # 最低经验要求
        while True:
            try:
                min_exp_input = input("最低工作经验要求（年，输入 0 表示无限制）: ").strip()
                if min_exp_input == '':
                    min_exp = 0
                else:
                    min_exp = int(min_exp_input)
                    if min_exp < 0:
                        print("工作年限不能为负数，请重新输入。")
                        continue
                break
            except ValueError:
                print("请输入有效的数字。")

        # 最低学历要求
        print("学历要求选项：1-不限，2-高中，3-大专，4-本科，5-硕士，6-博士")
        edu_map = {'1': '不限', '2': '高中', '3': '大专', '4': '本科', '5': '硕士', '6': '博士'}
        while True:
            edu_choice = input("请选择最低学历要求 (输入数字 1-6): ").strip()
            if edu_choice in edu_map:
                edu = edu_map[edu_choice]
                break
            else:
                print("请输入 1-6 之间的数字。")

        # 必备技能关键词
        print("请输入必备技能关键词，多个关键词用逗号分隔（直接回车表示无限制）：")
        keywords_input = input("技能关键词：").strip()
        if keywords_input:
            # 解析关键词并去重（忽略大小写，避免 MyBatis/Mybatis 重复）
            raw_keywords = [kw.strip() for kw in keywords_input.split(',') if kw.strip()]
            keywords = deduplicate_keywords(raw_keywords)
        else:
            keywords = []

        # 保存配置
        job_reqs[job_name] = {
            "min_exp": min_exp,
            "edu": edu,
            "keywords": keywords
        }

        print(f"✅ 已添加 {job_name} 的配置：")
        print(f"   最低经验：{min_exp}年")
        print(f"   最低学历：{edu}")
        print(f"   必备技能：{keywords if keywords else '无限制'}")

    # 添加默认配置
    if "default" not in job_reqs:
        job_reqs["default"] = {
            "min_exp": 0,
            "edu": "不限",
            "keywords": []
        }

    return {"job_requirements": job_reqs}


def save_config(config_data, filename="job_config.json"):
    """保存配置到文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)
    print(f"\n✅ 配置已保存到 {filename}")


def main():
    """主函数"""
    print("欢迎使用招聘需求配置生成器！")
    print("本工具将引导您创建个性化的筛选规则配置文件。\n")

    # 获取用户输入的招聘需求
    config = get_job_requirements()

    if not config["job_requirements"] or len(config["job_requirements"]) <= 1:  # 只有默认配置
        print("\n未添加任何职位配置，使用默认设置...")
        config = {
            "job_requirements": {
                "default": {
                    "min_exp": 0,
                    "edu": "不限",
                    "keywords": []
                }
            }
        }

    # 保存配置文件
    save_config(config)

    print("\n📋 生成的配置内容：")
    print(json.dumps(config, ensure_ascii=False, indent=2))

    print("\n💡 提示：")
    print("- 将生成的 job_config.json 文件放在 bossmaster.py 同目录下")
    print("- 运行 python bossmaster.py 时将自动使用您的配置")
    print("- 如需修改配置，可重新运行此工具或直接编辑配置文件")


if __name__ == "__main__":
    main()
