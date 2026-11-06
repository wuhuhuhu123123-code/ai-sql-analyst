# -*- coding: utf-8 -*-
"""HTTP 层冒烟测试：需要安装 Web 层依赖（fastapi + httpx）。

    python scripts/smoke_http.py

它会真的启动一次应用（TestClient，进程内），依次调用 4 个接口并打印结果。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def main() -> int:
    # 离线模式 + 仓库自带演示库
    import os

    os.environ["NL2SQL_OFFLINE"] = "1"
    os.environ["NL2SQL_DB_PATH"] = str(ROOT / "data" / "ecommerce.db")

    with TestClient(app) as client:
        print("== GET /healthz ==")
        r = client.get("/healthz")
        print(r.status_code, json.dumps(r.json(), ensure_ascii=False))
        assert r.status_code == 200

        print("\n== GET /api/schema ==")
        r = client.get("/api/schema")
        body = r.json()
        print(r.status_code, {k: body[k] for k in ("fingerprint", "table_count", "column_count")})
        assert r.status_code == 200

        print("\n== POST /api/query ==")
        r = client.post("/api/query", json={"question": "订单量最多的 5 个城市"})
        body = r.json()
        print(r.status_code, json.dumps({k: body[k] for k in ("columns", "row_count", "cached", "latency_ms")}, ensure_ascii=False))
        print("rows:", json.dumps(body["rows"][:3], ensure_ascii=False))
        assert r.status_code == 200

        print("\n== POST /api/query (再问一次，应命中缓存) ==")
        r2 = client.post("/api/query", json={"question": "订单量最多的 5 个城市"})
        print(r2.status_code, "cached =", r2.json()["cached"])
        assert r2.json()["cached"] is True

        print("\n== GET /api/cache ==")
        r = client.get("/api/cache")
        print(r.status_code, json.dumps(r.json(), ensure_ascii=False))

        print("\n== 参数校验（空问题应 422） ==")
        r = client.post("/api/query", json={"question": ""})
        print("status =", r.status_code)
        assert r.status_code == 422

    print("\n冒烟测试通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
