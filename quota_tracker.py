"""YouTube Data API v3 の日次クォータ消費量を追跡する。

Googleは「残クォータ」を取得するAPIを提供していないため、こちらで呼び出しごとの
消費ユニットを積算して概算する。クォータは太平洋時間0時にリセットされるため、
太平洋時間の日付をキーとして `cache/quota_usage.json` に記録する。
"""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import config

DAILY_QUOTA_UNITS = 10_000
SEARCH_LIST_COST = 100
VIDEOS_LIST_COST = 1

_USAGE_PATH = config.CACHE_DIR / "quota_usage.json"
_PACIFIC = ZoneInfo("America/Los_Angeles")


def _today_key() -> str:
    return datetime.now(_PACIFIC).strftime("%Y-%m-%d")


def _load() -> dict:
    if _USAGE_PATH.exists():
        with open(_USAGE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save(data: dict) -> None:
    with open(_USAGE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def record_usage(units: int) -> int:
    """本日分の消費量に units を加算し、加算後の本日合計を返す。"""
    data = _load()
    key = _today_key()
    data[key] = data.get(key, 0) + units
    _save(data)
    return data[key]


def today_usage() -> int:
    return _load().get(_today_key(), 0)


def usage_summary() -> str:
    used = today_usage()
    remaining = max(DAILY_QUOTA_UNITS - used, 0)
    pct = used / DAILY_QUOTA_UNITS * 100
    warning = " ※残り少なめです" if pct >= 80 else ""
    return (
        f"YouTube APIクォータ（本日・太平洋時間基準）: "
        f"{used}/{DAILY_QUOTA_UNITS} units使用（{pct:.1f}%）"
        f" / 残り約{remaining} units{warning}"
    )


def _main() -> None:
    print(usage_summary())


if __name__ == "__main__":
    _main()
