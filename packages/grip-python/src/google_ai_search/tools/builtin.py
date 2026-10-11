"""Built-in safe tools for Google AI Search."""

from __future__ import annotations

import ast
import json
import math
import operator
import re
from typing import Any
from urllib.parse import urlparse

import requests


# --- 1. Safe Calculator ---

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_FUNCS = {
    "round": round,
    "abs": abs,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "exp": math.exp,
    "ceil": math.ceil,
    "floor": math.floor,
}


def _eval_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp):
        op = _OPERATORS.get(type(node.op))
        if not op:
            raise ValueError(f"Unsupported unary operator: {type(node.op)}")
        return op(_eval_node(node.operand))
    if isinstance(node, ast.BinOp):
        op = _OPERATORS.get(type(node.op))
        if not op:
            raise ValueError(f"Unsupported binary operator: {type(node.op)}")
        return op(_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        fn_name = node.func.id
        if fn_name not in _SAFE_FUNCS:
            raise ValueError(f"Function '{fn_name}' is not allowed in safe calculator.")
        args = [_eval_node(arg) for arg in node.args]
        return _SAFE_FUNCS[fn_name](*args)
    raise ValueError(f"Unsupported expression element: {type(node)}")


def calculator(expression: str) -> float | int:
    """Safely evaluate mathematical and arithmetic expressions without eval."""
    expr = expression.strip().replace("^", "**")
    tree = ast.parse(expr, mode="eval")
    result = _eval_node(tree.body)
    return result


# --- 2. Citation Verifier ---

def citation_verifier(
    url: str | list[str],
    timeout_sec: float = 5.0,
    check_live: bool = True,
) -> dict[str, Any]:
    """Verify whether a cited web URL (or list of URLs) is accessible and extract status metadata."""
    if isinstance(url, (list, tuple)):
        items = [citation_verifier(u, timeout_sec=timeout_sec, check_live=check_live) for u in url]
        valid_items = [it for it in items if it.get("valid", it.get("reachable", False))]
        invalid_items = [it for it in items if not it.get("valid", it.get("reachable", False))]
        return {
            "total": len(items),
            "valid": valid_items,
            "invalid": invalid_items,
            "results": items,
        }

    parsed = urlparse(url)
    if not parsed.scheme.startswith("http"):
        return {"url": url, "valid": False, "reachable": False, "error": "Invalid URL scheme"}

    if not check_live:
        return {"url": url, "valid": True, "domain": parsed.netloc, "reachable": True}

    try:
        resp = requests.head(
            url,
            allow_redirects=True,
            timeout=timeout_sec,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"},
        )
        return {
            "url": url,
            "valid": True,
            "final_url": resp.url,
            "domain": parsed.netloc,
            "status_code": resp.status_code,
            "reachable": resp.status_code < 400,
            "content_type": resp.headers.get("Content-Type", ""),
        }
    except Exception as exc:
        return {
            "url": url,
            "valid": False,
            "domain": parsed.netloc,
            "status_code": None,
            "reachable": False,
            "error": str(exc),
        }


# --- 3. Page Fetcher ---

def page_fetcher(url: str, max_chars: int = 4000) -> str:
    """Fetch cleaned visible textual content from a web page URL for grounding."""
    try:
        resp = requests.get(
            url,
            timeout=8.0,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"},
        )
        resp.raise_for_status()
        text = resp.text

        # Strip scripts and styles
        text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
        # Strip remaining tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception as exc:
        return f"Failed to fetch {url}: {exc}"


# --- 4. Summarizer ---

def summarizer(text: str, max_sentences: int = 3) -> str:
    """Extract key sentences from a body of text to create a concise summary."""
    clean = text.strip()
    if not clean:
        return ""
    # Split sentences
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if len(s.strip()) > 15]
    if not sentences:
        return clean[:300]
    selected = sentences[:max_sentences]
    return " ".join(selected)


# --- 5. JSON Extractor ---

def json_extractor(text: str) -> dict[str, Any] | list[Any] | None:
    """Safely extract valid JSON objects or arrays embedded within markdown text."""
    # Try direct parse
    clean = text.strip()
    try:
        return json.loads(clean)
    except Exception:
        pass

    # Try codeblock match
    codeblock = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
    if codeblock:
        try:
            return json.loads(codeblock.group(1).strip())
        except Exception:
            pass

    # Try brace / bracket boundary match
    json_obj = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", clean)
    if json_obj:
        try:
            return json.loads(json_obj.group(1).strip())
        except Exception:
            pass

    return None


# --- 6. Unit Converter ---

_CONVERSIONS = {
    ("km", "mi"): 0.621371,
    ("mi", "km"): 1.60934,
    ("m", "ft"): 3.28084,
    ("ft", "m"): 0.3048,
    ("kg", "lb"): 2.20462,
    ("lb", "kg"): 0.453592,
    ("gb", "mb"): 1024.0,
    ("mb", "gb"): 1 / 1024.0,
    ("tb", "gb"): 1024.0,
    ("gb", "tb"): 1 / 1024.0,
}


def unit_converter(value: float, from_unit: str, to_unit: str) -> float:
    """Convert common measurement units (distance, mass, data storage)."""
    f = from_unit.strip().lower()
    t = to_unit.strip().lower()
    if f == t:
        return float(value)

    if (f, t) in _CONVERSIONS:
        return round(value * _CONVERSIONS[(f, t)], 4)

    # Temperature
    if f == "c" and t == "f":
        return round((value * 9 / 5) + 32, 2)
    if f == "f" and t == "c":
        return round((value - 32) * 5 / 9, 2)
    if f == "c" and t == "k":
        return round(value + 273.15, 2)
    if f == "k" and t == "c":
        return round(value - 273.15, 2)

    raise ValueError(f"Unsupported unit conversion from '{from_unit}' to '{to_unit}'")
