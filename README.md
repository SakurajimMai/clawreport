# OpenClaw 分身评估报告 | OpenClaw Forks Evaluation Report

> AI 自动评估 OpenClaw 生态中各分身项目的代码质量，定时更新。

## 功能

- 🔍 **自动发现** — GitHub API 爬取 OpenClaw forks + 关键词搜索
- 🤖 **AI 评估** — 六维度代码质量打分（兼容 OpenAI / newapi 等）
- 📊 **可视化报告** — 精美的静态 HTML 报告页面
- 🌍 **多语言** — 中文 / English 一键切换
- 🌙 **暗色模式** — 自动保存偏好
- 🔄 **定时更新** — GitHub Actions 每周自动运行
- 🚀 **GitHub Pages** — 自动部署

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 设置环境变量

```bash
export GITHUB_TOKEN="your_github_pat"
export LLM_API_KEY="your_api_key"
export LLM_BASE_URL="https://api.openai.com/v1"  # 或 newapi 地址
export LLM_MODEL="gpt-4o"                         # 或其他模型
```

### 3. 运行

```bash
python src/crawler.py    # 爬取项目
python src/evaluator.py  # AI 评估
python src/generator.py  # 生成报告
```

打开 `docs/index.html` 即可查看报告。

## GitHub Actions 配置

在仓库 Settings → Secrets and variables → Actions 中添加：

建议：用 Fine-grained tokens（新版 token）会更安全，只需给 clawreport 仓库授权 Contents: Read and Write 权限即可。

| Secret         | 说明                              |
| -------------- | --------------------------------- |
| `GH_PAT`       | GitHub Personal Access Token      |
| `LLM_API_KEY`  | LLM API 密钥                      |
| `LLM_BASE_URL` | LLM API 地址（可选，默认 OpenAI） |
| `LLM_MODEL`    | 模型名称（可选，默认 gpt-4o）     |

## GitHub Pages 部署

Settings → Pages → Source 选择 **Deploy from a branch**，Branch 选 `main`，Folder 选 `/docs`。

## 评估维度

| 维度     | 满分 | 评估要点                        |
| -------- | ---- | ------------------------------- |
| 代码质量 | 10   | 静态检查、错误处理、结构可读性  |
| 可维护性 | 10   | 模块划分、依赖管理、文档        |
| 健壮性   | 10   | 测试、输入校验、异常处理        |
| 可持续性 | 10   | 发布节奏、CI/CD、安全扫描       |
| 可迁移性 | 10   | 接口标准化、组件可替换          |
| 可扩展性 | 10   | 插件机制、Hook 接口、模块化架构 |
