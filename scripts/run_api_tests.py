"""
批量执行 API 测试脚本。

默认顺序：
1) api_validation_test.py
2) api_smoke_test.py
3) api_workflow_test.py
4) api_codelist_test.py
5) api_readonly_ui_test.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYTHON = ROOT.parent / ".venv" / "bin" / "python"
SCRIPTS = [
    "api_validation_test.py",
    "api_smoke_test.py",
    "api_workflow_test.py",
    "api_codelist_test.py",
    "api_readonly_ui_test.py",
]


def main() -> int:
    env = os.environ.copy()
    env.setdefault("SKIP_VECTOR", "true")
    failed: list[str] = []

    for script in SCRIPTS:
        script_path = ROOT / script
        print(f"\n[RUN] {script_path}")
        completed = subprocess.run(
            [str(PYTHON), str(script_path)],
            env=env,
            check=False,
        )
        if completed.returncode != 0:
            failed.append(script)
            print(f"[FAIL] {script} 退出码={completed.returncode}")
        else:
            print(f"[PASS] {script}")

    if failed:
        print(f"\n[SUMMARY] 失败脚本: {', '.join(failed)}")
        return 1

    print("\n[SUMMARY] 全部脚本执行成功")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
