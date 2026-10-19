"""
BOSS职位管理页面职位信息提取辅助脚本
提供给用户直接在浏览器控制台运行的JS代码
"""
print("=== BOSS直聘职位信息提取工具 ===")
print()
print("请在BOSS直聘的职位管理页面执行以下操作：")
print()
print("1. 打开浏览器开发者工具：按 F12")
print("2. 切换到 Console（控制台）标签页")
print("3. 复制并粘贴以下JavaScript代码到控制台：")
print()
print("// ===== 开始复制以下代码 =====")
print("""
// 提取BOSS直聘职位管理页面的职位信息
function extractBossJobs() {
    console.log("开始提取职位信息...");

    // 存储职位信息的数组
    var jobs = [];

    // 查找职位卡片的各种可能选择器
    var selectors = [
        '.job-card', '.job-item', '.position-card', '.position-item',
        '[class*="job"]', '[class*="position"]', '.info-primary',
        'li', '.item'
    ];

    // 尝试每个选择器
    for (var i = 0; i < selectors.length; i++) {
        var elements = document.querySelectorAll(selectors[i]);
        console.log("选择器 '" + selectors[i] + "' 找到 " + elements.length + " 个元素");

        if (elements.length > 0) {
            for (var j = 0; j < elements.length; j++) {
                var element = elements[j];

                // 检查元素是否包含职位相关关键词
                var text = element.innerText || element.textContent;

                // 定义职位关键词
                var jobKeywords = ['工程师', '经理', '总监', '主管', '专员', '助理', '实习生', '顾问',
                                  '设计师', '开发', '技术', '产品', '运营', '市场', '销售', '财务',
                                  '人事', '行政', '客服', '测试', '运维', '架构师', '分析师', '策划',
                                  'Java', 'Python', 'C++', '前端', '后端', '算法'];

                var hasJobKeyword = false;
                for (var k = 0; k < jobKeywords.length; k++) {
                    if (text.indexOf(jobKeywords[k]) !== -1) {
                        hasJobKeyword = true;
                        break;
                    }
                }

                // 如果包含职位关键词，提取信息
                if (hasJobKeyword) {
                    // 尝试获取职位名称
                    var jobTitle = '';

                    // 检查是否有特定的职位标题元素
                    var titleSelectors = ['.job-title', '.job-name', '.position-name', 'h3', 'h4', '.name', '.title', 'a'];
                    for (var t = 0; t < titleSelectors.length; t++) {
                        var titleElement = element.querySelector(titleSelectors[t]);
                        if (titleElement) {
                            jobTitle = titleElement.innerText || titleElement.textContent;
                            if (jobTitle.trim().length > 2) {
                                break;
                            }
                        }
                    }

                    // 如果没找到标题，使用元素文本的前几个词
                    if (!jobTitle || jobTitle.trim().length <= 2) {
                        jobTitle = text.substring(0, 50).trim();
                    }

                    // 获取ID（如果有data属性）
                    var jobId = element.getAttribute('data-jobid') ||
                               element.getAttribute('data-positionid') ||
                               element.getAttribute('data-id') ||
                               'job_' + j + '_' + Date.now();

                    // 获取其他信息
                    var department = element.querySelector('.department, .dept, .company')?.innerText || '未知部门';
                    var salary = element.querySelector('.salary, .pay')?.innerText || '面议';
                    var city = element.querySelector('.city, .location')?.innerText || '未知城市';
                    var experience = element.querySelector('.experience, .exp')?.innerText || '经验不限';
                    var education = element.querySelector('.education, .edu')?.innerText || '学历不限';

                    var jobInfo = {
                        job_id: jobId,
                        job_name: jobTitle,
                        department: department,
                        city: city,
                        salary: salary,
                        experience: experience,
                        education: education,
                        status: '招聘中'
                    };

                    // 验证职位信息有效性
                    if (jobInfo.job_name && jobInfo.job_name.length >= 2) {
                        jobs.push(jobInfo);
                        console.log("提取到职位: " + jobInfo.job_name);
                    }
                }
            }

            // 如果找到了职位就停止尝试其他选择器
            if (jobs.length > 0) {
                break;
            }
        }
    }

    // 如果上面方法都没找到，尝试从所有链接中查找职位相关链接
    if (jobs.length === 0) {
        console.log("尝试从页面链接中查找职位信息...");
        var links = document.querySelectorAll('a');
        for (var l = 0; l < links.length; l++) {
            var link = links[l];
            var href = link.href;
            var text = link.innerText || link.textContent;

            // 检查是否是职位链接
            if ((href.indexOf('/job_detail/') !== -1 || href.indexOf('/job/') !== -1 || href.indexOf('securityId=') !== -1) &&
                text.length > 2) {

                // 检查文本是否像职位名称
                var jobKeywords = ['工程师', '经理', '总监', '主管', '专员', '助理', '实习生', '顾问',
                                  '设计师', '开发', '技术', '产品', '运营', '市场', '销售', '财务',
                                  '人事', '行政', '客服', '测试', '运维', '架构师', '分析师', '策划'];

                var hasJobKeyword = false;
                for (var k = 0; k < jobKeywords.length; k++) {
                    if (text.indexOf(jobKeywords[k]) !== -1) {
                        hasJobKeyword = true;
                        break;
                    }
                }

                if (hasJobKeyword) {
                    var jobInfo = {
                        job_id: 'link_' + l,
                        job_name: text,
                        department: '未知部门',
                        city: '未知城市',
                        salary: '面议',
                        experience: '经验不限',
                        education: '学历不限',
                        status: '招聘中'
                    };

                    jobs.push(jobInfo);
                    console.log("从链接提取职位: " + jobInfo.job_name);
                }
            }
        }
    }

    console.log("总共找到 " + jobs.length + " 个职位");

    // 将结果格式化为JSON
    var result = {
        status: "success",
        jobs: jobs,
        count: jobs.length,
        timestamp: new Date().toISOString()
    };

    console.log("提取完成，结果如下：");
    console.log(JSON.stringify(result, null, 2));

    // 将结果复制到剪贴板（在某些浏览器中可能不起作用）
    try {
        navigator.clipboard.writeText(JSON.stringify(result, null, 2)).then(function() {
            console.log("结果已复制到剪贴板");
        }).catch(function(err) {
            console.log("无法自动复制到剪贴板，请手动复制上面的JSON结果");
        });
    } catch(e) {
        console.log("浏览器不支持自动复制，请手动复制上面的JSON结果");
    }

    return result;
}

// 执行函数
extractBossJobs();
""")
print("// ===== 结束复制 =====")
print()
print("4. 按 Enter 键执行代码")
print("5. 控制台会显示提取到的职位信息")
print("6. 复制显示的JSON格式结果")
print("7. 将其保存到一个文本文件中")
print("8. 在我们的Web界面中，可以暂时使用'上传需求文档'功能")
print("   将这份信息作为职位要求使用")
print()
print("这种方法绕过了Playwright自动化限制，直接在浏览器中执行JavaScript，")
print("应该能够成功提取您页面上显示的职位信息。")