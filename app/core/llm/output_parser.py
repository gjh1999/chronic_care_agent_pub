import json
import re


def extract_json(text: str) -> str:
    """
    从 LLM 输出中提取 JSON（兼容乱输出）
    """
    # 找第一个 { 到最后一个 }
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"未找到JSON: {text}")

    return match.group(0)


def parse_json(text: str):
    """
    安全解析 JSON
    """
    try:
        return json.loads(text)
    except:
        cleaned = extract_json(text)
        return json.loads(cleaned)