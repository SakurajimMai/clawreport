"""AI 评估模块 — 调用 LLM 对项目进行多维度代码质量评估

兼容所有 OpenAI 格式的 API（含 newapi 等中转项目）"""

import json
import os
from datetime import datetime, timezone

from openai import OpenAI

from config import DATA_DIR, DIMENSIONS, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

SYSTEM_PROMPT = """你是一位资深的开源项目代码审计专家。
你需要根据提供的项目元数据和源码样本，对该项目进行多维度的代码质量评估。

评分规则：
- 每个维度满分 10 分（整数）
- 7-10 分 = 优秀，5-6 分 = 中等，1-4 分 = 需改进
- 必须基于实际代码证据打分，不可凭直觉

输出格式（严格 JSON）：
{
  "scores": {
    "code_quality": <1-10>,
    "maintainability": <1-10>,
    "robustness": <1-10>,
    "sustainability": <1-10>,
    "portability": <1-10>,
    "extensibility": <1-10>
  },
  "total": <六项平均分，保留一位小数>,
  "summary_zh": "<一句话中文定位，如'生产级多渠道助手 | 可持续性基线'>",
  "summary_en": "<一句话英文定位>",
  "recommendation_zh": "<中文选型建议，30字以内>",
  "recommendation_en": "<英文选型建议>",
  "highlights_zh": ["<优势1>", "<优势2>"],
  "highlights_en": ["<strength1>", "<strength2>"],
  "concerns_zh": ["<不足1>"],
  "concerns_en": ["<concern1>"]
}

只输出 JSON，不要任何其他文字。"""


def _build_user_prompt(project: dict) -> str:
    """构造用户 prompt"""
    # 元数据摘要
    meta_lines = [
        f"项目: {project['full_name']}",
        f"描述: {project.get('description', 'N/A')}",
        f"语言: {project['language']}",
        f"Stars: {project['stars']}",
        f"贡献者: {project['contributors']}",
        f"发布次数: {project['release_count']}",
        f"CI/CD: {'有' if project.get('has_ci') else '无'}",
        f"最近推送: {project.get('pushed_at', 'N/A')}",
        f"Topics: {', '.join(project.get('topics', []))}",
    ]

    # 源码样本
    source_lines = []
    for sample in project.get("source_samples", [])[:8]:
        source_lines.append(f"\n--- {sample['path']} ---\n{sample['content']}")

    return (
        "## 项目元数据\n"
        + "\n".join(meta_lines)
        + "\n\n## 源码样本"
        + "\n".join(source_lines)
    )


def evaluate_project(client: OpenAI, project: dict) -> dict | None:
    """调用 LLM 评估单个项目"""
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(project)},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"  ❌ LLM 评估失败 ({project['full_name']}): {e}")
        return None


def main():
    # 读取爬虫数据
    raw_path = os.path.join(DATA_DIR, "projects_raw.json")
    if not os.path.exists(raw_path):
        print("❌ 未找到 projects_raw.json，请先运行 crawler.py")
        return

    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    projects = raw_data["projects"]
    print(f"📊 共 {len(projects)} 个项目待评估")

    # 初始化 LLM 客户端（兼容 newapi 等 OpenAI 格式中转）
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    results = []
    for i, project in enumerate(projects, 1):
        name = project["full_name"]
        print(f"\n[{i}/{len(projects)}] 评估 {name} ...")
        evaluation = evaluate_project(client, project)

        if evaluation:
            result = {
                "name": project.get("name", ""),
                "full_name": name,
                "html_url": project["html_url"],
                "description": project.get("description", ""),
                "language": project["language"],
                "stars": project["stars"],
                "contributors": project["contributors"],
                "created_at": project.get("created_at", ""),
                "release_count": project["release_count"],
                "release_freq_zh": project.get("release_freq_zh", "不定期"),
                "release_freq_en": project.get("release_freq_en", "Irregular"),
                "has_ci": project.get("has_ci", False),
                "is_upstream": project.get("is_upstream", False),
                "scores": evaluation["scores"],
                "total": evaluation["total"],
                "summary_zh": evaluation.get("summary_zh", ""),
                "summary_en": evaluation.get("summary_en", ""),
                "recommendation_zh": evaluation.get("recommendation_zh", ""),
                "recommendation_en": evaluation.get("recommendation_en", ""),
                "highlights_zh": evaluation.get("highlights_zh", []),
                "highlights_en": evaluation.get("highlights_en", []),
                "concerns_zh": evaluation.get("concerns_zh", []),
                "concerns_en": evaluation.get("concerns_en", []),
            }
            results.append(result)
            print(f"  ✅ 总分: {evaluation['total']}")
        else:
            print(f"  ⏭️  跳过")

    # 按总分降序排列
    results.sort(key=lambda r: r["total"], reverse=True)

    # 写入结果
    output_path = os.path.join(DATA_DIR, "results.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "total": len(results),
                "dimensions": [
                    {"id": d["id"], "name_zh": d["name_zh"], "name_en": d["name_en"]}
                    for d in DIMENSIONS
                ],
                "projects": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\n💾 评估结果已保存到 {output_path}")


if __name__ == "__main__":
    main()
