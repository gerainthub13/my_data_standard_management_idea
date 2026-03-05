"""
创建 DSMS demo 数据：
- HR 10 条
- EHS 10 条
- 财务与资金管理 10 条

特性：
- 可重复执行：若标准编码已存在则跳过
- 自动创建领域分类
- 每个领域创建并发布一个标准代码列表，绑定到部分已发布标准
- 状态分布：6 发布、2 草稿、1 退役、1 废弃
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class StandardSeed:
    code: str
    name: str
    description: str
    status: str  # published | draft | retired | deprecated
    bind_code_list: bool = False


def _expect_status(resp: httpx.Response, expected: int, step: str) -> None:
    if resp.status_code != expected:
        raise AssertionError(f"[{step}] 期望状态码 {expected}，实际 {resp.status_code}，响应={resp.text}")


def _is_conflict(resp: httpx.Response) -> bool:
    return resp.status_code == 409


def _safe_json(resp: httpx.Response) -> dict[str, Any]:
    try:
        return resp.json()
    except Exception:
        return {}


def main() -> int:
    base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    timeout_seconds = float(os.getenv("API_TIMEOUT_SECONDS", "30"))
    result: dict[str, Any] = {
        "created": 0,
        "skipped": 0,
        "bound": 0,
        "domains": {},
    }

    domains: dict[str, dict[str, Any]] = {
        "HR": {
            "category": "HR领域",
            "code_list": {
                "list_code": "HR_EMP_STATUS_LIST",
                "name": "员工在岗状态码表",
                "purpose": "标识员工当前在岗状态",
                "items": [
                    {"item_code": "ACTIVE", "item_name": "在岗", "meaning": "正常在岗", "sort_order": 1},
                    {"item_code": "ON_LEAVE", "item_name": "休假", "meaning": "请假或休假中", "sort_order": 2},
                    {"item_code": "RESIGNED", "item_name": "离职", "meaning": "员工已离职", "sort_order": 3},
                ],
            },
            "standards": [
                StandardSeed("HR_EMPLOYEE_ID", "员工编号", "企业内部员工唯一标识", "published", True),
                StandardSeed("HR_EMPLOYEE_NAME", "员工姓名", "员工法定姓名", "published", True),
                StandardSeed("HR_GENDER_CODE", "性别代码", "员工性别代码值", "published", True),
                StandardSeed("HR_BIRTH_DATE", "出生日期", "员工出生日期", "published"),
                StandardSeed("HR_HIRE_DATE", "入职日期", "员工首次入职日期", "published"),
                StandardSeed("HR_DEPT_CODE", "部门代码", "员工所属部门编码", "published"),
                StandardSeed("HR_POSITION_CODE", "岗位代码", "员工岗位编码", "draft"),
                StandardSeed("HR_CONTRACT_TYPE", "合同类型", "员工劳动合同类型", "draft"),
                StandardSeed("HR_RESIGN_DATE", "离职日期", "员工离职生效日期", "retired"),
                StandardSeed("HR_ATTENDANCE_FLAG", "考勤标识", "员工是否纳入考勤统计", "deprecated"),
            ],
        },
        "EHS": {
            "category": "EHS领域",
            "code_list": {
                "list_code": "EHS_RISK_LEVEL_LIST",
                "name": "EHS风险等级码表",
                "purpose": "标识环境健康安全风险等级",
                "items": [
                    {"item_code": "LOW", "item_name": "低风险", "meaning": "低等级风险", "sort_order": 1},
                    {"item_code": "MEDIUM", "item_name": "中风险", "meaning": "中等级风险", "sort_order": 2},
                    {"item_code": "HIGH", "item_name": "高风险", "meaning": "高等级风险", "sort_order": 3},
                ],
            },
            "standards": [
                StandardSeed("EHS_INCIDENT_ID", "事件编号", "EHS 事件唯一编号", "published", True),
                StandardSeed("EHS_SITE_CODE", "厂区编码", "事件发生厂区编码", "published", True),
                StandardSeed("EHS_RISK_LEVEL", "风险等级", "事件风险等级标识", "published", True),
                StandardSeed("EHS_PPE_TYPE", "防护用品类型", "个人防护用品分类", "published"),
                StandardSeed("EHS_PERMIT_TYPE", "作业许可类型", "受控作业许可类别", "published"),
                StandardSeed("EHS_HAZARD_CODE", "危险源编码", "危险源识别编码", "published"),
                StandardSeed("EHS_AUDIT_SCORE", "审核得分", "EHS 审核评分", "draft"),
                StandardSeed("EHS_WASTE_CLASS", "废弃物类别", "危废/固废分类", "draft"),
                StandardSeed("EHS_EXPOSURE_HOURS", "暴露时长", "职业危害暴露时长（小时）", "retired"),
                StandardSeed("EHS_EMERGENCY_LEVEL", "应急等级", "应急响应等级", "deprecated"),
            ],
        },
        "FIN": {
            "category": "财务与资金管理领域",
            "code_list": {
                "list_code": "FIN_PAY_METHOD_LIST",
                "name": "支付方式码表",
                "purpose": "标识财务付款方式",
                "items": [
                    {"item_code": "BANK_TRANSFER", "item_name": "银行转账", "meaning": "对公/对私转账", "sort_order": 1},
                    {"item_code": "CASH", "item_name": "现金", "meaning": "现金支付", "sort_order": 2},
                    {"item_code": "CHECK", "item_name": "支票", "meaning": "支票支付", "sort_order": 3},
                ],
            },
            "standards": [
                StandardSeed("FIN_VOUCHER_NO", "凭证号", "财务凭证唯一编号", "published", True),
                StandardSeed("FIN_ACCOUNT_SUBJECT", "会计科目", "总账会计科目编码", "published", True),
                StandardSeed("FIN_COST_CENTER", "成本中心", "费用归集成本中心", "published", True),
                StandardSeed("FIN_CURRENCY_CODE", "币种代码", "交易币种代码", "published"),
                StandardSeed("FIN_EXCHANGE_RATE", "汇率", "交易记账汇率", "published"),
                StandardSeed("FIN_PAYMENT_METHOD", "支付方式", "付款采用的支付方式", "published"),
                StandardSeed("FIN_BANK_ACCOUNT_TYPE", "银行账户类型", "资金账户类型", "draft"),
                StandardSeed("FIN_CASHFLOW_TYPE", "现金流类型", "现金流入流出分类", "draft"),
                StandardSeed("FIN_BUDGET_ITEM", "预算项目", "预算控制项目编码", "retired"),
                StandardSeed("FIN_SETTLEMENT_STATUS", "结算状态", "业务结算状态标识", "deprecated"),
            ],
        },
    }

    with httpx.Client(timeout=timeout_seconds) as client:
        def url(path: str) -> str:
            return f"{base_url}{path}"

        # 健康检查
        resp = client.get(url("/health"))
        _expect_status(resp, 200, "health")

        def ensure_category(category_name: str) -> int:
            payload = {"name": category_name, "category_type": "custom", "scope": "standard"}
            resp = client.post(url("/api/v1/categories"), json=payload)
            if resp.status_code == 201:
                return resp.json()["id"]
            if _is_conflict(resp):
                q = client.get(
                    url("/api/v1/categories"),
                    params={"keyword": category_name, "allow_empty_keyword": "true", "page_size": 200},
                )
                _expect_status(q, 200, "query_category_after_conflict")
                items = q.json().get("items", [])
                for item in items:
                    if item.get("name") == category_name and item.get("scope") == "standard":
                        return item["id"]
            raise AssertionError(f"[ensure_category] 分类创建/查询失败: {resp.text}")

        def ensure_code_list(payload: dict[str, Any]) -> str:
            resp = client.post(url("/api/v1/code-lists"), json=payload)
            if resp.status_code == 201:
                code_list_id = resp.json()["id"]
                pub = client.patch(url(f"/api/v1/code-lists/{code_list_id}/publish"))
                _expect_status(pub, 200, "publish_code_list")
                return code_list_id

            if _is_conflict(resp):
                q = client.get(
                    url("/api/v1/code-lists"),
                    params={"list_code": payload["list_code"], "bindable": "true", "page_size": 1},
                )
                _expect_status(q, 200, "query_code_list_after_conflict")
                items = q.json().get("items", [])
                if items:
                    return items[0]["id"]
            raise AssertionError(f"[ensure_code_list] 码表创建/查询失败: {resp.text}")

        def exists_standard(code: str) -> str | None:
            resp = client.get(url("/api/v1/standards"), params={"code": code, "page_size": 1})
            _expect_status(resp, 200, "exists_standard")
            items = resp.json().get("items", [])
            if items:
                return items[0]["id"]
            return None

        for domain_name, domain_data in domains.items():
            category_id = ensure_category(domain_data["category"])
            code_list_id = ensure_code_list(domain_data["code_list"])

            created_count = 0
            skipped_count = 0
            bound_count = 0

            for seed in domain_data["standards"]:
                existing_id = exists_standard(seed.code)
                if existing_id:
                    skipped_count += 1
                    continue

                create_resp = client.post(
                    url("/api/v1/standards"),
                    json={
                        "code": seed.code,
                        "name": seed.name,
                        "description": seed.description,
                        "category_id": category_id,
                        "extattributes": {"domain": domain_name, "source": "demo-seed"},
                    },
                )
                _expect_status(create_resp, 201, f"create_standard_{seed.code}")
                standard_id = create_resp.json()["id"]

                if seed.status == "published":
                    pub = client.patch(url(f"/api/v1/standards/{standard_id}/publish"))
                    _expect_status(pub, 200, f"publish_standard_{seed.code}")
                elif seed.status == "retired":
                    pub = client.patch(url(f"/api/v1/standards/{standard_id}/publish"))
                    _expect_status(pub, 200, f"publish_for_retire_{seed.code}")
                    st = client.patch(url(f"/api/v1/standards/{standard_id}/status"), json={"status": 2})
                    _expect_status(st, 200, f"retire_standard_{seed.code}")
                elif seed.status == "deprecated":
                    st = client.patch(url(f"/api/v1/standards/{standard_id}/status"), json={"status": 3})
                    _expect_status(st, 200, f"deprecate_standard_{seed.code}")
                elif seed.status == "draft":
                    pass
                else:
                    raise AssertionError(f"未知状态类型: {seed.status}")

                if seed.bind_code_list and seed.status == "published":
                    bind = client.put(
                        url(f"/api/v1/standards/{standard_id}/code-list"),
                        json={"code_list_id": code_list_id},
                    )
                    _expect_status(bind, 200, f"bind_code_list_{seed.code}")
                    bound_count += 1

                created_count += 1

            result["domains"][domain_name] = {
                "category_id": category_id,
                "code_list_id": code_list_id,
                "created": created_count,
                "skipped": skipped_count,
                "bound": bound_count,
            }
            result["created"] += created_count
            result["skipped"] += skipped_count
            result["bound"] += bound_count

    print(json.dumps({"status": "ok", "case": "seed_demo_standards", "result": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
