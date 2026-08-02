from pathlib import Path
from typing import Any

from settings import get_prompt_dir


def get_module_dir() -> Path:
    # __file__ 是当前 Python 文件的路径。
    # Path(__file__).parent 表示当前文件所在目录，也就是 04_prompt_engineering。
    return Path(__file__).parent


def get_prompt_path(version: str) -> Path:
    # prompt 文件统一放在 prompts 目录。
    # Java 类比：可以把 prompt 看成 resources 目录下的模板文件，而不是写死在 Service 代码里。
    return get_module_dir() / get_prompt_dir() / f"{version}.md"


def list_prompt_versions() -> list[dict[str, Any]]:
    # glob("*.md") 会列出 prompts 目录下所有 markdown 文件。
    # 这里用 sorted 是为了让接口返回顺序稳定，方便学习者对比。
    prompt_dir = get_module_dir() / get_prompt_dir()
    versions: list[dict[str, Any]] = []
    for prompt_path in sorted(prompt_dir.glob("*.md")):
        version = prompt_path.stem
        prompt_text = prompt_path.read_text(encoding="utf-8")
        versions.append(
            {
                "version": version,
                "file": str(prompt_path),
                "behavior": extract_behavior(prompt_text),
                "first_line": prompt_text.splitlines()[0] if prompt_text else "",
            }
        )
    return versions


def load_prompt(version: str) -> dict[str, Any]:
    # 读取某个版本的 prompt。
    # 如果版本写错，主动抛 FileNotFoundError，让 main.py 返回清晰错误。
    prompt_path = get_prompt_path(version)
    if not prompt_path.exists():
        available_versions = [item["version"] for item in list_prompt_versions()]
        raise FileNotFoundError(
            f"找不到 prompt 版本 {version}，可用版本：{available_versions}"
        )

    prompt_text = prompt_path.read_text(encoding="utf-8")
    return {
        "version": version,
        "path": str(prompt_path),
        "text": prompt_text,
        "behavior": extract_behavior(prompt_text),
    }


def extract_behavior(prompt_text: str) -> str:
    # 本模块用 PROMPT_BEHAVIOR 这一行模拟“prompt 对模型行为的影响”。
    # 真实模型不会读取这个标签后机械执行；这里是教学 mock，为了让不同版本的效果稳定可复现。
    for line in prompt_text.splitlines():
        if line.startswith("PROMPT_BEHAVIOR:"):
            return line.replace("PROMPT_BEHAVIOR:", "").strip()
    return "unknown"
