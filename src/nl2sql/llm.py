# -*- coding: utf-8 -*-
"""OpenAI 兼容的对话补全客户端（零第三方依赖实现）。

生产用 LLMClient 走 HTTP；测试与离线演示用 FakeLLM，
两者接口一致，便于把「模型调用」从业务逻辑中隔离出去。
"""
from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field


class LLMError(RuntimeError):
    """模型调用失败（网络、鉴权、限流、返回格式异常）。"""


@dataclass
class LLMResult:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMClient:
    base_url: str
    api_key: str
    model: str
    timeout_s: float = 30.0
    max_retries: int = 2
    max_tokens: int = 512
    temperature: float = 0.0

    def chat(self, messages: list[dict[str, str]]) -> LLMResult:
        if not self.api_key:
            raise LLMError("未配置 LLM_API_KEY，无法调用模型；可用 --offline 试运行")
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        last_error = ""
        for attempt in range(self.max_retries + 1):
            started = time.perf_counter()
            request = urllib.request.Request(
                url,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_s) as resp:
                    raw = resp.read().decode("utf-8")
                return self._parse(raw, time.perf_counter() - started)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")[:300]
                last_error = f"HTTP {exc.code}: {detail}"
                if exc.code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                raise LLMError(last_error) from exc
            except (urllib.error.URLError, socket.timeout) as exc:
                last_error = f"网络错误：{exc}"
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                raise LLMError(last_error) from exc

        raise LLMError(last_error or "模型调用失败")

    def _parse(self, raw: str, elapsed: float) -> LLMResult:
        try:
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"模型返回格式异常：{raw[:200]}") from exc
        usage = data.get("usage") or {}
        return LLMResult(
            text=content or "",
            model=data.get("model", self.model),
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            latency_ms=round(elapsed * 1000, 2),
        )


@dataclass
class FakeLLM:
    """离线替身：按规则把中文问题映射到固定 SQL，并记录调用次数。"""

    responses: list[str] = field(default_factory=list)
    calls: list[list[dict[str, str]]] = field(default_factory=list)
    model: str = "fake-rule-model"
    latency_ms: float = 0.0

    def chat(self, messages: list[dict[str, str]]) -> LLMResult:
        self.calls.append(messages)
        if self.responses:
            text = self.responses.pop(0)
        else:
            question = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    # 提示词里 few-shot 也带「问题：」，取最后一个即本次真实问题
                    matches = re.findall(r"问题：\s*(.+)$", msg["content"], re.MULTILINE)
                    question = matches[-1].strip() if matches else msg["content"]
                    break
            text = rule_based_sql(question)
        return LLMResult(
            text=text,
            model=self.model,
            prompt_tokens=sum(len(m["content"]) for m in messages) // 2,
            completion_tokens=len(text) // 2,
            latency_ms=self.latency_ms,
        )


CATEGORY_SQL = """SELECT p.category AS 品类,
       ROUND(SUM(oi.quantity * oi.unit_price), 2) AS 销售额
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.status = '已完成'
GROUP BY p.category
ORDER BY 销售额 DESC
LIMIT 10"""

CITY_SQL = """SELECT c.city AS 城市,
       COUNT(DISTINCT o.order_id) AS 订单量
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.city
ORDER BY 订单量 DESC
LIMIT 5"""

AOV_SQL = """SELECT ROUND(SUM(oi.quantity * oi.unit_price) /
             COUNT(DISTINCT o.order_id), 2) AS 平均客单价
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
WHERE o.status = '已完成'"""

REPEAT_SQL = """SELECT c.customer_id AS 客户编号,
       c.name AS 客户,
       COUNT(DISTINCT o.order_id) AS 订单数
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.status = '已完成'
GROUP BY c.customer_id
HAVING COUNT(DISTINCT o.order_id) >= 2
ORDER BY 订单数 DESC
LIMIT 10"""

TREND_SQL = """SELECT substr(o.order_date, 1, 7) AS 月份,
       COUNT(DISTINCT o.order_id) AS 订单量
FROM orders o
WHERE o.status = '已完成'
GROUP BY 月份
ORDER BY 月份
LIMIT 24"""


def rule_based_sql(question: str) -> str:
    """离线模式的关键词路由，仅用于无 API Key 的本地演示。"""
    q = question.replace(" ", "")
    if any(k in q for k in ("品类", "分类", "类别")):
        return CATEGORY_SQL
    if any(k in q for k in ("城市", "地区", "地域")):
        return CITY_SQL
    if any(k in q for k in ("客单价", "平均订单", "平均金额")):
        return AOV_SQL
    if any(k in q for k in ("复购", "回头客", "二次购买")):
        return REPEAT_SQL
    return TREND_SQL
