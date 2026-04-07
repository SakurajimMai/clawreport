"""AI 评估模块 — 调用 LLM 对项目进行多维度代码质量评估

兼容所有 OpenAI 格式的 API（含 newapi 等中转项目）"""

import json
import os
import re
import time
from datetime import datetime, timezone

from openai import OpenAI

from config import DATA_DIR, DIMENSIONS, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

REQUIRED_SCORE_IDS = tuple(d["id"] for d in DIMENSIONS)
MAX_REQUEST_ATTEMPTS = max(1, int(os.getenv("LLM_MAX_RETRIES", "3")))
RETRY_BACKOFF_SECONDS = max(0.0, float(os.getenv("LLM_RETRY_BACKOFF_SECONDS", "2")))

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


def _is_grok_model(model: str) -> bool:
    return model.strip().lower().startswith("grok")


def _build_chat_completion_kwargs(messages: list[dict], **extra) -> dict:
    """统一构造 chat/completions 请求参数。"""
    kwargs = {
        "model": LLM_MODEL,
        "messages": messages,
        "stream": False,
    }
    kwargs.update(extra)

    if _is_grok_model(LLM_MODEL):
        kwargs.setdefault("reasoning_effort", "none")

    return kwargs


def _is_retryable_exception(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {429, 500, 502, 503, 504}:
        return True

    message = str(exc).lower()
    retry_markers = (
        "bad gateway",
        "gateway timeout",
        "temporarily unavailable",
        "connection reset",
        "timed out",
        "server disconnected",
        "502",
        "503",
        "504",
    )
    return any(marker in message for marker in retry_markers)


def _describe_exception(exc: Exception) -> str:
    status_code = getattr(exc, "status_code", None)
    message = str(exc).strip()
    if status_code:
        return f"HTTP {status_code}: {message[:300]}"
    return f"{type(exc).__name__}: {message[:300]}"


def _create_chat_completion(client: OpenAI, request_name: str, messages: list[dict], **extra):
    """统一执行 chat/completions 请求，并对瞬时 5xx 做重试。"""
    last_error = None
    for attempt in range(1, MAX_REQUEST_ATTEMPTS + 1):
        try:
            return client.chat.completions.create(
                **_build_chat_completion_kwargs(messages, **extra)
            )
        except Exception as exc:
            last_error = exc
            if not _is_retryable_exception(exc) or attempt >= MAX_REQUEST_ATTEMPTS:
                raise

            delay = RETRY_BACKOFF_SECONDS * attempt
            print(
                f"   ⚠️ {request_name} 请求失败，准备重试 "
                f"({attempt}/{MAX_REQUEST_ATTEMPTS})：{_describe_exception(exc)}"
            )
            if delay > 0:
                time.sleep(delay)

    raise last_error


def _extract_response_content(response) -> str:
    """统一提取模型响应文本。"""
    if isinstance(response, str):
        return response

    if hasattr(response, "choices"):
        content = response.choices[0].message.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
                else:
                    text = getattr(item, "text", "")
                    if text:
                        parts.append(text)
            return "".join(parts)
        return "" if content is None else str(content)

    return str(response)


def _clean_response_text(content: str) -> str:
    """去掉 markdown 包裹和推理标签。"""
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    return re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.IGNORECASE).strip()


def _extract_json_object(text: str) -> str | None:
    match = re.search(r"\{[\s\S]*\}", text)
    return match.group(0) if match else None


def _parse_json_payload(content: str) -> dict | None:
    """兼容 SSE 错误流和混合文本，提取首个 JSON 对象。"""
    cleaned = _clean_response_text(content)
    candidates = []

    for line in cleaned.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("data:"):
            payload = stripped.split(":", 1)[1].strip()
            if payload and payload != "[DONE]":
                candidates.append(payload)
                extracted = _extract_json_object(payload)
                if extracted and extracted != payload:
                    candidates.append(extracted)

    candidates.append(cleaned)
    extracted = _extract_json_object(cleaned)
    if extracted and extracted != cleaned:
        candidates.append(extracted)

    seen = set()
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload

    return None


def _is_error_payload(content: str, payload: dict | None) -> bool:
    if isinstance(payload, dict) and payload.get("error"):
        return True
    lowered = content.lower()
    return "event: error" in lowered or lowered.startswith("error:")


def _format_error_message(payload: dict | None, fallback: str) -> str:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("type")
            if message:
                return str(message)
            return json.dumps(error, ensure_ascii=False)
        if error:
            return str(error)
    return fallback.strip()[:200] or "未知错误"


def _normalize_number(value) -> int | float:
    number = round(float(value), 1)
    return int(number) if number.is_integer() else number


def _validate_evaluation(payload: dict, project_name: str) -> dict | None:
    """验证评估结构，避免下游直接访问缺失字段。"""
    scores = payload.get("scores")
    if not isinstance(scores, dict):
        print(f"  ❌ 评估结果缺少 scores ({project_name})")
        print(f"     响应预览: {json.dumps(payload, ensure_ascii=False)[:500]}")
        return None

    missing = [dim_id for dim_id in REQUIRED_SCORE_IDS if dim_id not in scores]
    if missing:
        print(f"  ❌ 评估结果缺少评分维度 ({project_name}): {', '.join(missing)}")
        print(f"     响应预览: {json.dumps(payload, ensure_ascii=False)[:500]}")
        return None

    normalized_scores = {}
    for dim_id in REQUIRED_SCORE_IDS:
        try:
            score = float(scores[dim_id])
        except (TypeError, ValueError):
            print(f"  ❌ 评分不是数字 ({project_name}): {dim_id}={scores[dim_id]!r}")
            return None
        if not 1 <= score <= 10:
            print(f"  ❌ 评分超出范围 ({project_name}): {dim_id}={score}")
            return None
        normalized_scores[dim_id] = _normalize_number(score)

    total = payload.get("total")
    if total in (None, ""):
        total = round(sum(float(score) for score in normalized_scores.values()) / len(normalized_scores), 1)
    else:
        try:
            total = round(float(total), 1)
        except (TypeError, ValueError):
            print(f"  ❌ total 不是数字 ({project_name}): {total!r}")
            return None

    normalized = dict(payload)
    normalized["scores"] = normalized_scores
    normalized["total"] = total
    return normalized


def _test_api_connection(client: OpenAI) -> bool:
    """预检测 API 连通性"""
    print(f"\n🔑 API 配置:")
    print(f"   Base URL: {LLM_BASE_URL}")
    print(f"   Model:    {LLM_MODEL}")
    print(f"   API Key:  {LLM_API_KEY[:8]}..." if len(LLM_API_KEY) > 8 else f"   API Key:  (长度={len(LLM_API_KEY)})")
    print(f"\n🧪 测试 API 连通性...")
    try:
        response = _create_chat_completion(
            client,
            "API 预检",
            [{"role": "user", "content": "回复 OK"}],
            max_tokens=10,
        )
        content = _extract_response_content(response)
        payload = _parse_json_payload(content)

        if not content:
            finish_reason = (
                response.choices[0].finish_reason
                if hasattr(response, "choices")
                else "N/A"
            )
            print(f"   ❌ API 返回空内容! finish_reason={finish_reason}")
            print(f"   原始响应: {response}")
            return False

        if _is_error_payload(content, payload):
            message = _format_error_message(payload, content)
            print(f"   ❌ API 返回错误响应: {message}")
            print(f"   原始响应: {content.strip()[:200]}")
            return False

        if content:
            print(f"   ✅ API 正常，返回: {_clean_response_text(content)[:50]}")
            return True
    except Exception as e:
        print(f"   ❌ API 连接失败: {_describe_exception(e)}")
        return False


def evaluate_project(client: OpenAI, project: dict) -> dict | None:
    """调用 LLM 评估单个项目"""
    try:
        response = _create_chat_completion(
            client,
            f"项目评估 {project['full_name']}",
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(project)},
            ],
            temperature=0.3,
        )
        content = _extract_response_content(response)

        if not content:
            print(f"  ❌ LLM 返回空内容 ({project['full_name']})")
            print(f"     finish_reason: {response.choices[0].finish_reason if hasattr(response, 'choices') else 'N/A'}")
            print(f"     原始响应: {response}")
            return None

        payload = _parse_json_payload(content)
        if payload is None:
            print(f"  ❌ JSON 解析失败 ({project['full_name']})")
            print(f"     LLM 原始返回内容: {_clean_response_text(content)[:500] if content else '(空)'}")
            return None

        if _is_error_payload(content, payload):
            message = _format_error_message(payload, content)
            print(f"  ❌ LLM 返回错误响应 ({project['full_name']}): {message}")
            print(f"     原始响应: {_clean_response_text(content)[:500]}")
            return None

        return _validate_evaluation(payload, project["full_name"])
    except Exception as e:
        print(f"  ❌ LLM 评估失败 ({project['full_name']}): {type(e).__name__}: {e}")
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

    # 预检测 API 连通性
    if not _test_api_connection(client):
        print("\n❌ API 连通性测试未通过。")
        print("   如果日志里是 502/503/504，这通常是上游服务暂时不可用，而不是代码字段解析问题。")
        print("   如果你要使用 grok2api，请确认 GitHub Actions Secret `LLM_BASE_URL` 已切到 grok2api 的 /v1 地址。")
        print("   也可以调整 `LLM_MAX_RETRIES` 和 `LLM_RETRY_BACKOFF_SECONDS` 增加重试次数与退避时间。")
        raise SystemExit(1)

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

    if not results:
        print("\n❌ 没有任何项目评估成功，已终止生成结果文件。")
        raise SystemExit(1)

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
