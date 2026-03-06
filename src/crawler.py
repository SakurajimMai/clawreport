"""GitHub 爬虫 — 发现并采集 OpenClaw 类项目的元数据与源码样本"""

import json
import os
import time
from datetime import datetime, timezone

from github import Github, GithubException

from config import (
    DATA_DIR,
    GITHUB_TOKEN,
    MAX_SAMPLE_FILES,
    MIN_STARS,
    SEARCH_QUERIES,
    UPSTREAM_REPO,
)


def _gh_client() -> Github:
    """创建 GitHub 客户端"""
    if GITHUB_TOKEN:
        return Github(GITHUB_TOKEN, per_page=100)
    print("⚠️  未设置 GITHUB_TOKEN，API 速率限制为 60 次/小时")
    return Github(per_page=100)


def _repo_meta(repo) -> dict:
    """提取仓库元数据"""
    try:
        contributors_count = repo.get_contributors().totalCount
    except GithubException:
        contributors_count = 0

    try:
        releases = list(repo.get_releases()[:5])
        release_count = repo.get_releases().totalCount
        latest_release = releases[0].published_at.isoformat() if releases else None
    except GithubException:
        release_count = 0
        latest_release = None

    # 判断发布频率
    if release_count == 0:
        release_freq = "无"
        release_freq_en = "None"
    elif release_count >= 12:
        release_freq = "日更"
        release_freq_en = "Daily"
    elif release_count >= 4:
        release_freq = "周更"
        release_freq_en = "Weekly"
    else:
        release_freq = "不定期"
        release_freq_en = "Irregular"

    return {
        "name": repo.name,
        "full_name": repo.full_name,
        "html_url": repo.html_url,
        "description": repo.description or "",
        "language": repo.language or "Unknown",
        "stars": repo.stargazers_count,
        "forks": repo.forks_count,
        "open_issues": repo.open_issues_count,
        "contributors": contributors_count,
        "created_at": repo.created_at.isoformat(),
        "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
        "release_count": release_count,
        "latest_release": latest_release,
        "release_freq_zh": release_freq,
        "release_freq_en": release_freq_en,
        "has_ci": False,  # 稍后检查
        "topics": repo.get_topics(),
    }


def _sample_source_files(repo, max_files: int = MAX_SAMPLE_FILES) -> list[dict]:
    """采样核心源码文件内容（用于 AI 评估）"""
    samples = []
    priority_patterns = [
        "README",
        "package.json",
        "Cargo.toml",
        "pyproject.toml",
        "Dockerfile",
        ".github/workflows",
    ]

    try:
        contents = repo.get_contents("")
    except GithubException:
        return samples

    # 先收集优先文件
    file_list = []
    while contents:
        item = contents.pop(0)
        if item.type == "dir":
            # 检查 CI 配置
            if ".github" in item.path:
                try:
                    contents.extend(repo.get_contents(item.path))
                except GithubException:
                    pass
            # 采样 src/ lib/ 等核心目录的前几个文件
            elif item.path in ("src", "lib", "core", "pkg", "internal", "app"):
                try:
                    sub = repo.get_contents(item.path)
                    file_list.extend(
                        [f for f in sub if f.type == "file"][:3]
                    )
                except GithubException:
                    pass
        else:
            file_list.append(item)

    # 排序：优先级文件在前
    def _priority(f):
        for i, p in enumerate(priority_patterns):
            if p.lower() in f.path.lower():
                return i
        return 100

    file_list.sort(key=_priority)

    for f in file_list[:max_files]:
        try:
            if f.size and f.size > 50_000:  # 跳过大文件
                continue
            content = f.decoded_content.decode("utf-8", errors="replace")
            # 截断过长内容
            if len(content) > 5000:
                content = content[:5000] + "\n... (truncated)"
            samples.append({"path": f.path, "content": content})
        except (GithubException, Exception):
            continue

    return samples


def _check_ci(repo, meta: dict):
    """检查是否有 CI/CD 配置"""
    try:
        repo.get_contents(".github/workflows")
        meta["has_ci"] = True
    except GithubException:
        meta["has_ci"] = False


def discover_projects() -> list[dict]:
    """发现所有 OpenClaw 类项目"""
    g = _gh_client()
    seen = set()
    projects = []

    # 1) 获取上游仓库本身
    print(f"📦 获取上游仓库 {UPSTREAM_REPO} ...")
    try:
        upstream = g.get_repo(UPSTREAM_REPO)
        meta = _repo_meta(upstream)
        meta["is_upstream"] = True
        _check_ci(upstream, meta)
        meta["source_samples"] = _sample_source_files(upstream)
        projects.append(meta)
        seen.add(upstream.full_name.lower())
    except GithubException as e:
        print(f"  ❌ 无法获取上游仓库: {e}")

    # 2) 获取 forks
    print("🔍 搜索 forks ...")
    try:
        upstream = g.get_repo(UPSTREAM_REPO)
        for fork in upstream.get_forks():
            key = fork.full_name.lower()
            if key in seen:
                continue
            if fork.stargazers_count < MIN_STARS:
                continue
            seen.add(key)
            print(f"  ✅ Fork: {fork.full_name} ⭐{fork.stargazers_count}")
            meta = _repo_meta(fork)
            meta["is_upstream"] = False
            _check_ci(fork, meta)
            meta["source_samples"] = _sample_source_files(fork)
            projects.append(meta)
            time.sleep(0.5)  # 避免触发速率限制
    except GithubException as e:
        print(f"  ❌ 获取 forks 失败: {e}")

    # 3) 关键词搜索
    for query in SEARCH_QUERIES:
        print(f"🔍 搜索关键词: {query} ...")
        try:
            results = g.search_repositories(query, sort="stars", order="desc")
            for repo in results[:20]:
                key = repo.full_name.lower()
                if key in seen:
                    continue
                if repo.stargazers_count < MIN_STARS:
                    continue
                seen.add(key)
                print(f"  ✅ 搜索结果: {repo.full_name} ⭐{repo.stargazers_count}")
                meta = _repo_meta(repo)
                meta["is_upstream"] = False
                _check_ci(repo, meta)
                meta["source_samples"] = _sample_source_files(repo)
                projects.append(meta)
                time.sleep(0.5)
        except GithubException as e:
            print(f"  ❌ 搜索失败: {e}")
        time.sleep(2)  # 搜索 API 有更严格的速率限制

    print(f"\n📊 共发现 {len(projects)} 个项目")
    return projects


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    projects = discover_projects()

    output_path = os.path.join(DATA_DIR, "projects_raw.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "crawled_at": datetime.now(timezone.utc).isoformat(),
                "total": len(projects),
                "projects": projects,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"💾 已保存到 {output_path}")


if __name__ == "__main__":
    main()
