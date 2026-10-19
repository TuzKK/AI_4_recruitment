# Boss直聘客户端自动化招聘

一个面向招聘团队的 **Boss 直聘客户端自动化招聘系统**。  
项目通过 **RPA + AI** 串起岗位分析、候选人搜索、自动沟通、简历评分和联系方式获取，适合用作内部招聘自动化平台或相关产品原型。

## 适用场景

- 招聘团队希望减少重复的搜索、打招呼和简历初筛工作
- 需要一个可视化看板统一查看招聘进度、候选人漏斗和任务日志
- 希望把 Boss 直聘客户端操作和 AI 简历分析结合起来
- 需要一个可继续二次开发的招聘自动化项目骨架

## 核心能力

- AI 自动分析岗位并生成 JD、关键词和筛选标准
- 基于客户端/RPA 的候选人搜索与自动打招呼
- 多轮候选人沟通与简历收集
- 简历多维度 AI 评分
- 达标候选人自动跟进联系方式
- Web 作战看板、候选人池、职位矩阵、市场情报、系统设置

## 界面特点

当前前端已经重做为更偏“招聘指挥台”的风格，包括：

- 深色控制台式布局
- 统一的导航壳层与模块标题区
- 总览式招聘漏斗与实时日志
- 站内 Toast 提示和自定义确认弹层
- 候选人、职位、市场情报、设置页面的统一视觉语言

## 技术栈

| 层次 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS |
| 后端 | FastAPI + Python 3.11+ |
| 浏览器自动化 | Playwright + playwright-stealth |
| AI/LLM | OpenAI 兼容接口 |
| 数据库 | SQLite + SQLAlchemy |

## 项目结构

```text
Boss/
├── frontend/              # React 前端
│   └── src/
│       ├── pages/         # Dashboard, CreateTask, CandidateList, ...
│       ├── api/           # API 客户端
│       ├── hooks/         # Toast / WebSocket 等前端钩子
│       └── lib/           # 工具函数
│
├── backend/               # Python 后端 + 自动化引擎
│   ├── analyzer/          # 职位分析
│   ├── rpa/               # RPA 浏览器引擎
│   ├── communicator/      # 候选人沟通与联系方式获取
│   ├── resume_analysis/   # 简历 AI 分析
│   ├── pipeline/          # 流水线编排
│   ├── web/               # FastAPI 路由
│   └── database/          # SQLAlchemy ORM
│
└── 使用文档.md             # 更详细的中文使用文档
```

## 快速开始

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

然后在 `backend/.env` 中填入你自己的模型接入信息。

### 2. 安装前端依赖

```bash
cd frontend
npm install
npm run build
```

### 3. 首次登录 Boss 直聘

```bash
cd backend
python main.py setup
```

在弹出的客户端或浏览器中完成登录后，再继续启动服务。

### 4. 启动服务

```bash
cd backend
python main.py serve
```

启动后，浏览器访问本地服务地址即可进入系统首页。

## 推荐使用流程

1. 在“系统设置”中配置模型接入信息
2. 登录 Boss 直聘招聘账号
3. 在“新建任务”中输入岗位名称并让 AI 完成分析
4. 调整关键词、阈值和执行参数
5. 启动任务并在首页观察漏斗与实时日志
6. 在“候选人池”查看结果并导出

## 文档说明

- 仓库首页 `README.md`：适合快速了解项目和上手
- [使用文档.md](./使用文档.md)：适合查看更完整的页面说明和使用流程

## 安全说明

- 不要把真实的 `.env`、账号、模型密钥和本地运行数据提交到仓库
- 当前仓库中的 `.env.example` 仅保留占位符
- 本项目涉及客户端自动化行为，请在合法合规、符合平台规则的前提下使用

## 免责声明

本项目仅供学习、研究和内部流程自动化探索使用。请在使用前自行评估合规性、账号风险和平台政策要求。
