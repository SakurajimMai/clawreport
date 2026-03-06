# OpenClaw 分身评估报告 — 项目规划

> AI 自动爬取 GitHub 上所有 OpenClaw 类项目，6 大维度代码质量评估，生成精美静态报告，GitHub Actions 定时更新 + GitHub Pages 部署。

## 系统架构

```
GitHub Actions (cron / 手动)
    ↓
crawler.py  ──→  data/projects_raw.json   # 爬取项目元数据 + 源码样本
    ↓
evaluator.py ──→  data/results.json        # LLM 6 维度评分
    ↓
generator.py ──→  docs/index.html          # Jinja2 渲染静态页面
    ↓
GitHub Pages                                # 自动部署
```

| 环节 | 技术栈                 | 说明                                          |
| ---- | ---------------------- | --------------------------------------------- |
| 爬虫 | PyGithub               | forks 遍历 + 关键词搜索，采集元数据与源码样本 |
| 评估 | OpenAI 兼容 API        | 6 维度量化打分，支持 newapi 等中转            |
| 生成 | Jinja2                 | JSON 数据注入 HTML 模板                       |
| 前端 | Vanilla CSS + JS       | 玻璃拟物化、暗色模式、中英切换                |
| 部署 | GitHub Actions + Pages | 每周一自动运行，`docs/` 目录部署              |

## 项目结构

```
clawreport/
├── .github/workflows/
│   └── evaluate.yml          # GitHub Actions 定时任务
├── src/
│   ├── config.py             # 配置常量（搜索词、维度、路径）
│   ├── crawler.py            # GitHub 爬虫
│   ├── evaluator.py          # AI 评估模块
│   ├── generator.py          # 静态页面生成器
│   └── __init__.py
├── templates/
│   ├── index.html            # Jinja2 页面模板
│   ├── style.css             # 蓝紫玻璃拟物化样式
│   └── script.js             # 交互逻辑
├── data/
│   └── results.json          # 评估结果（脚本生成）
├── docs/                     # GitHub Pages 输出
│   ├── index.html
│   ├── style.css
│   └── script.js
├── requirements.txt
├── .gitignore
├── README.md
└── Plan.md                   # 本文件
```

## 文件说明

| 文件                             | 用途                                                     |
| -------------------------------- | -------------------------------------------------------- |
| `src/config.py`                  | API 配置、6 大评分维度定义、搜索关键词、输出路径         |
| `src/crawler.py`                 | GitHub API 爬虫（forks + 搜索），采集元数据和源码样本    |
| `src/evaluator.py`               | LLM 评估（OpenAI 兼容），6 维度打分 + 中英文评语         |
| `src/generator.py`               | Jinja2 模板渲染，JSON → HTML，复制静态资源到 `docs/`     |
| `templates/index.html`           | 7 大区段模板，含 SEO（OG / Twitter / JSON-LD）及双语支持 |
| `templates/style.css`            | CSS 变量系统、暗色模式、玻璃拟物化、响应式布局           |
| `templates/script.js`            | 暗色切换、中英切换、IntersectionObserver 导航高亮        |
| `.github/workflows/evaluate.yml` | 每周一 cron + `workflow_dispatch` 手动触发               |

## 评估维度（6 大维度，每项满分 10 分）

| 维度     | 评估要点                                    |
| -------- | ------------------------------------------- |
| 代码质量 | 静态检查标准、错误处理、结构可读性          |
| 可维护性 | 模块划分、依赖管理、文档完整度              |
| 健壮性   | 测试覆盖、输入校验、异常处理、权限边界      |
| 可持续性 | 发布节奏、CI/CD 完善度、安全扫描            |
| 可迁移性 | 接口标准化、组件可替换性、环境适配          |
| 可扩展性 | 插件机制、Hook 接口、模块化架构、第三方集成 |

## 部署步骤

### 1. 配置 GitHub Secrets

Settings → Secrets and variables → Actions：

| Secret         | 必填 | 说明                                                           |
| -------------- | ---- | -------------------------------------------------------------- |
| `GH_PAT`       | 是   | GitHub Fine-grained Token（Contents: Read and Write）          |
| `LLM_API_KEY`  | 是   | LLM API 密钥                                                   |
| `LLM_BASE_URL` | 否   | API 地址，默认 `https://api.openai.com/v1`，可改为 newapi 地址 |
| `LLM_MODEL`    | 否   | 模型名称，默认 `gpt-4o`                                        |

### 2. 启用 GitHub Pages

Settings → Pages → Source: **Deploy from a branch** → Branch: `main`, Folder: `/docs`

### 3. 触发运行

Actions → **OpenClaw Evaluation** → **Run workflow**

## 本地开发

```bash
pip install -r requirements.txt

export GITHUB_TOKEN="your_github_pat"
export LLM_API_KEY="your_api_key"
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_MODEL="gpt-4o"

python src/crawler.py      # 爬取项目
python src/evaluator.py    # AI 评估
python src/generator.py    # 生成报告

# 本地预览
cd docs && python -m http.server 8080
```

## 依赖

```
PyGithub    — GitHub REST API
openai      — LLM 调用（兼容所有 OpenAI 格式 API）
Jinja2      — HTML 模板渲染
requests    — HTTP 请求
```
