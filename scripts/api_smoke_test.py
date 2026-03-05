import json
import os
import sys
from datetime import datetime

import httpx


def _env_flag(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "y"}


def main() -> int:
    base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    skip_vector = _env_flag("SKIP_VECTOR")
    timeout_seconds = float(os.getenv("API_TIMEOUT_SECONDS", "30"))

    now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    code = f"STD_USER_ID_{now}"

    with httpx.Client(timeout=timeout_seconds) as client:
        def url(path: str) -> str:
            return f"{base_url}{path}"

        # Health
        resp = client.get(url("/health"))
        resp.raise_for_status()

        # Create category
        resp = client.post(
            url("/api/v1/categories"),
            json={"name": f"TestCategory-{now}", "category_type": "custom", "scope": "standard"},
        )
        resp.raise_for_status()
        category = resp.json()

        # Create standard
        resp = client.post(
            url("/api/v1/standards"),
            json={
                "code": code,
                "name": "用户ID",
                "description": "用户唯一标识",
                "category_id": category["id"],
                "extattributes": {"datatype": "string", "length": 64},
                "translations": [
                    {"fieldname": "name", "language": "en", "content": "User ID"},
                    {"fieldname": "description", "language": "en", "content": "Unique user identifier"},
                ],
            },
        )
        resp.raise_for_status()
        standard = resp.json()
        standard_id = standard["id"]

        # Get standard detail (i18n override)
        resp = client.get(url(f"/api/v1/standards/{standard_id}"), params={"lang": "en"})
        resp.raise_for_status()

        # Update standard
        resp = client.put(
            url(f"/api/v1/standards/{standard_id}"),
            json={"description": "用户唯一标识（更新）"},
        )
        resp.raise_for_status()

        # Create revision
        resp = client.post(url(f"/api/v1/standards/{standard_id}/revision"))
        resp.raise_for_status()
        revision = resp.json()

        # Publish revision (makes it latest)
        resp = client.patch(url(f"/api/v1/standards/{revision['id']}/publish"))
        resp.raise_for_status()

        # Keyword search (requires published latest)
        resp = client.post(url("/api/v1/standards/search"), json={"query": code, "use_vector": False})
        resp.raise_for_status()

        # Vector search (optional; requires LM Studio available)
        if not skip_vector:
            resp = client.post(url("/api/v1/standards/search"), json={"query": "用户唯一标识", "use_vector": True})
            resp.raise_for_status()

        # Relation create + list
        resp = client.post(
            url(f"/api/v1/standards/{revision['id']}/relations"),
            json={
                "targetid": "external.table.user",
                "targetver": "v1",
                "reltype": "maptotable",
                "targettype": "table",
                "relstatus": 0,
            },
        )
        resp.raise_for_status()
        relation = resp.json()

        resp = client.get(url(f"/api/v1/standards/{revision['id']}/relations"))
        resp.raise_for_status()

        # Embedding rebuild (optional; may fail if LM Studio is down)
        resp = client.post(
            url("/api/v1/embeddings/rebuild"),
            json={"refids": [revision["id"]], "lang": "zh"},
        )
        resp.raise_for_status()

    print(json.dumps({"status": "ok", "standard_id": standard_id, "relation_id": relation["id"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
