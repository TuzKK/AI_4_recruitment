"""
增强版BOSS直聘职位信息提取用户指南

如果自动提取失败，使用此脚本快速获取职位信息。
"""

from datetime import datetime

def generate_manual_extration_guide():
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    guide = """=== BOSS直聘职位信息手动提取指南 ===
__GENERATED_AT__

如果自动提取功能无法正常工作，您可以使用以下方法手动获取职位信息：

方法一：浏览器控制台执行JavaScript（推荐）
----------------------------------------
1. 在BOSS直聘职位管理页面按 F12 打开开发者工具
2. 切换到 Console（控制台）标签
3. 将以下代码复制粘贴到控制台并执行：

```javascript
// ===== 开始复制这段代码 =====
(function() {
    console.log("开始提取BOSS直聘职位信息...");

    // 查找职位卡片元素
    const jobCards = document.querySelectorAll('.job-card, .position-card, .job-item, .position-item, [class*="job"], [class*="position"]');

    const jobs = [];

    jobCards.forEach((card, index) => {
        // 提取职位名称
        let jobName = '';
        const nameSelectors = ['.job-title', '.job-name', '.position-name', 'h3', 'h4', 'a', '.name', '.title'];
        for(const selector of nameSelectors) {
            const nameEl = card.querySelector(selector);
            if(nameEl) {
                jobName = nameEl.textContent.trim();
                if(jobName.length > 2) break;
            }
        }

        // 如果上述选择器都没找到，尝试从整个卡片获取
        if(!jobName || jobName.length <= 2) {
            jobName = card.textContent.substring(0, 50).trim();
        }

        // 验证是否为有效职位名称
        const jobKeywords = ['工程师', '经理', '总监', '主管', '专员', '助理', '实习生', '顾问',
                           '设计师', '开发', '技术', '产品', '运营', '市场', '销售', '财务',
                           '人事', '行政', '客服', '测试', '运维', '架构师', '分析师', '策划',
                           'Java', 'Python', 'C++', '前端', '后端', '算法'];

        const isValidJob = jobKeywords.some(keyword => jobName.includes(keyword));

        if(isValidJob) {
            const job = {
                job_id: card.dataset.jobid || card.dataset.positionid || `manual_${index}_${Date.now()}`,
                job_name: jobName,
                department: card.querySelector('.department, .dept, .company')?.textContent?.trim() || '未知部门',
                city: card.querySelector('.city, .location')?.textContent?.trim() || '未知城市',
                salary: card.querySelector('.salary, .pay')?.textContent?.trim() || '面议',
                experience: card.querySelector('.experience, .exp')?.textContent?.trim() || '经验不限',
                education: card.querySelector('.education, .edu')?.textContent?.trim() || '学历不限',
                status: '招聘中'
            };

            jobs.push(job);
            console.log("职位提取成功: " + job.job_name);
        }
    });

    if(jobs.length === 0) {
        console.log("未找到职位信息，尝试从页面所有链接中提取...");
        // 如果卡片方法失败，从链接提取
        const links = document.querySelectorAll('a');
        links.forEach((link, index) => {
            const href = link.href;
            const text = link.textContent.trim();

            if((href.includes('/job_detail/') || href.includes('/job/') || href.includes('securityId=')) &&
               text.length > 2) {

                const jobKeywords = ['工程师', '经理', '总监', '主管', '专员', '助理', '实习生', '顾问',
                                   '设计师', '开发', '技术', '产品', '运营', '市场', '销售', '财务',
                                   '人事', '行政', '客服', '测试', '运维', '架构师', '分析师', '策划'];

                const isValidJob = jobKeywords.some(keyword => text.includes(keyword));

                if(isValidJob) {
                    jobs.push({
                        job_id: "link_" + index + "_" + Date.now(),
                        job_name: text,
                        department: '未知部门',
                        city: '未知城市',
                        salary: '面议',
                        experience: '经验不限',
                        education: '学历不限',
                        status: '招聘中'
                    });
                    console.log("从链接提取职位: " + text);
                }
            }
        });
    }

    const result = {
        status: "success",
        jobs: jobs,
        count: jobs.length,
        timestamp: new Date().toISOString(),
        extraction_method: "manual_js_console"
    };

    console.log("提取完成，共找到 " + jobs.length + " 个职位");
    console.log("结果JSON：");
    console.log(JSON.stringify(result, null, 2));

    // 尝试复制到剪贴板
    try {
        navigator.clipboard.writeText(JSON.stringify(result, null, 2))
            .then(() => console.log("结果已复制到剪贴板"))
            .catch(() => console.log("请手动复制上方的JSON结果"));
    } catch(e) {
        console.log("浏览器不支持自动复制，请手动复制结果");
    }

    return result;
})();
// ===== 结束复制 =====
```

方法二：直接复制页面内容
-------------------------
1. 在职位管理页面全选 (Ctrl+A)
2. 复制 (Ctrl+C)
3. 粘贴到文本编辑器中
4. 手动整理出职位名称和要求

方法三：保存为文档
-------------------
将手动获取的职位要求保存为 Word、PDF 或 TXT 文档，
然后在系统中选择"上传需求文档"选项。

提示
----
- 确保职位管理页面完全加载后再执行脚本
- 如果职位列表是动态加载的，请滚动页面到底部确保所有职位都已加载
- 如仍有问题，请联系技术支持
"""

    print(guide.replace("__GENERATED_AT__", generated_at))

if __name__ == "__main__":
    generate_manual_extration_guide()
