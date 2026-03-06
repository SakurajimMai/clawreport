"""配置常量 — OpenClaw 分身评估系统"""

import os

# ── GitHub API ──────────────────────────────────────────────
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
UPSTREAM_REPO = "openclaw/openclaw"

# 搜索关键词（用于发现非 fork 的类似项目）
SEARCH_QUERIES = [
    "openclaw fork",
    "openclaw alternative",
    "coding agent cli",
    "ai coding assistant terminal",
]

# 最低 star 数过滤阈值
MIN_STARS = 50

# 每个项目最多采样的源码文件数
MAX_SAMPLE_FILES = 10

# 自定义项目列表（JSON 文件路径）
CUSTOM_PROJECTS_FILE = os.path.join(os.path.dirname(__file__), "..", "projects.json")

# Awesome 列表仓库（自动从 README 解析 Main Projects）
AWESOME_LIST_REPO = "machinae/awesome-claws"

# ── LLM API（兼容 OpenAI 格式，可接入 newapi 等项目）─────────
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

# ── 评分维度 ────────────────────────────────────────────────
DIMENSIONS = [
    {
        "id": "code_quality",
        "name_zh": "代码质量",
        "name_en": "Code Quality",
        "desc_zh": "看代码是否'能长期稳定运行'：静态检查、错误处理、结构和可读性是否有基本标准。",
        "desc_en": "Whether the code can run stably long-term: static analysis, error handling, structure and readability standards.",
    },
    {
        "id": "maintainability",
        "name_zh": "可维护性",
        "name_en": "Maintainability",
        "desc_zh": "看团队换人时，项目是否容易接手：模块划分清晰、依赖集中、文档与治理流程齐全。",
        "desc_en": "Whether the project is easy to take over: clear module separation, centralized dependencies, complete documentation.",
    },
    {
        "id": "robustness",
        "name_zh": "健壮性",
        "name_en": "Robustness",
        "desc_zh": "看是否有完整防护链路：测试、输入校验、异常处理、权限边界是否闭环。",
        "desc_en": "Whether there is a complete protection chain: testing, input validation, exception handling, permission boundaries.",
    },
    {
        "id": "sustainability",
        "name_zh": "可持续性",
        "name_en": "Sustainability",
        "desc_zh": "看是否长期有人维护：发布节奏、告警体系、安全扫描是否持续运行。",
        "desc_en": "Whether the project is maintained long-term: release cadence, alerting, security scanning.",
    },
    {
        "id": "portability",
        "name_zh": "可迁移性",
        "name_en": "Portability",
        "desc_zh": "看接口是否标准化、组件能否快速接入新存储或运行环境。",
        "desc_en": "Whether interfaces are standardized and components can quickly integrate with new storage or runtime environments.",
    },
    {
        "id": "extensibility",
        "name_zh": "可扩展性",
        "name_en": "Extensibility",
        "desc_zh": "看是否预留了插件机制、Hook 接口或模块化架构，能否方便地增加新功能或集成第三方服务。",
        "desc_en": "Whether the project provides plugin mechanisms, hook interfaces or modular architecture for easy feature additions and third-party integrations.",
    },
]

# ── 输出路径 ──────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
