"""静态页面生成器 — 将 JSON 评估数据渲染为 HTML 报告"""

import json
import os
import shutil

from jinja2 import Environment, FileSystemLoader

from config import DATA_DIR, DIMENSIONS, DOCS_DIR, TEMPLATES_DIR


def load_results() -> dict:
    """加载评估结果"""
    results_path = os.path.join(DATA_DIR, "results.json")
    if not os.path.exists(results_path):
        print("❌ 未找到 results.json，请先运行 evaluator.py")
        return None
    with open(results_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_dimension_rankings(projects: list) -> dict:
    """按每个维度分别排名"""
    rankings = {}
    for dim in DIMENSIONS:
        dim_id = dim["id"]
        sorted_list = sorted(
            projects, key=lambda p: p["scores"].get(dim_id, 0), reverse=True
        )
        rankings[dim_id] = [
            {
                "name": p["name"],
                "full_name": p["full_name"],
                "score": p["scores"].get(dim_id, 0),
            }
            for p in sorted_list
        ]
    return rankings


def _build_comparison_table(projects: list) -> dict:
    """构建分身专项对比表（以上游项目为基线）"""
    # 找到上游项目
    upstream = next((p for p in projects if p.get("is_upstream")), None)
    if not upstream:
        upstream = projects[0] if projects else None

    if not upstream:
        return {"baseline": None, "forks": [], "dimensions": []}

    baseline_scores = upstream["scores"]
    forks = []
    for p in projects:
        if p["full_name"] == upstream["full_name"]:
            continue
        diffs = {}
        for dim in DIMENSIONS:
            dim_id = dim["id"]
            score = p["scores"].get(dim_id, 0)
            base = baseline_scores.get(dim_id, 0)
            diffs[dim_id] = {"score": score, "diff": score - base}
        forks.append({"name": p["name"], "full_name": p["full_name"], "diffs": diffs})

    return {
        "baseline": {
            "name": upstream["name"],
            "scores": baseline_scores,
        },
        "forks": forks,
        "dimensions": [{"id": d["id"], "name_zh": d["name_zh"], "name_en": d["name_en"]} for d in DIMENSIONS],
    }


def generate():
    """生成静态 HTML 报告"""
    data = load_results()
    if not data:
        return

    projects = data["projects"]
    evaluated_at = data.get("evaluated_at", "")

    # 准备模板数据
    top3 = projects[:3]
    dimension_rankings = _build_dimension_rankings(projects)
    comparison = _build_comparison_table(projects)

    # 选型建议：取前 3 名项目分配场景
    recommendations = []
    if len(projects) >= 1:
        recommendations.append({
            "scenario_zh": "生产部署（当前）",
            "scenario_en": "Production Deployment",
            "project": projects[0]["name"],
            "reason_zh": projects[0].get("recommendation_zh", "综合评分最高"),
            "reason_en": projects[0].get("recommendation_en", "Highest overall score"),
            "badge_zh": "推荐首选",
            "badge_en": "Recommended",
        })
    if len(projects) >= 2:
        # 找健壮性最高的
        robust_best = max(projects, key=lambda p: p["scores"].get("robustness", 0))
        recommendations.append({
            "scenario_zh": "安全关键场景",
            "scenario_en": "Security-Critical",
            "project": robust_best["name"],
            "reason_zh": robust_best.get("recommendation_zh", "健壮性评分最高"),
            "reason_en": robust_best.get("recommendation_en", "Highest robustness score"),
            "badge_zh": "安全首选",
            "badge_en": "Most Secure",
        })
    if len(projects) >= 3:
        # 找可迁移性最高的
        port_best = max(projects, key=lambda p: p["scores"].get("portability", 0))
        recommendations.append({
            "scenario_zh": "长期个人代理（可扩展）",
            "scenario_en": "Long-term Personal Agent",
            "project": port_best["name"],
            "reason_zh": port_best.get("recommendation_zh", "可迁移性评分最高"),
            "reason_en": port_best.get("recommendation_en", "Highest portability score"),
            "badge_zh": "扩展性强",
            "badge_en": "Most Extensible",
        })

    template_data = {
        "evaluated_at": evaluated_at[:10] if evaluated_at else "N/A",
        "total_projects": len(projects),
        "projects": projects,
        "top3": top3,
        "dimensions": DIMENSIONS,
        "dimension_rankings": dimension_rankings,
        "comparison": comparison,
        "recommendations": recommendations,
        "results_json": json.dumps(data, ensure_ascii=False),
    }

    # 渲染模板
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=True,
    )
    template = env.get_template("index.html")
    html = template.render(**template_data)

    # 输出到 docs/
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    # 复制静态文件
    for static_file in ("style.css", "script.js"):
        src = os.path.join(TEMPLATES_DIR, static_file)
        dst = os.path.join(DOCS_DIR, static_file)
        if os.path.exists(src):
            shutil.copy2(src, dst)

    print(f"✅ 报告已生成到 {DOCS_DIR}/")


if __name__ == "__main__":
    generate()
