from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = PROJECT_ROOT / "scrape_history.json"
MAX_HISTORY = 200


@dataclass
class HistoryItem:
    timestamp: str
    provider: str
    url: str
    prompt: str
    summary: str


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_history(path: Path = HISTORY_PATH) -> List[HistoryItem]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items: List[HistoryItem] = []
        for item in raw[:MAX_HISTORY]:
            try:
                items.append(
                    HistoryItem(
                        timestamp=item.get("timestamp", ""),
                        provider=item.get("provider", ""),
                        url=item.get("url", ""),
                        prompt=item.get("prompt", ""),
                        summary=item.get("summary", ""),
                    )
                )
            except Exception:
                continue
        return items
    except Exception:
        return []


def append_history(
    provider: str,
    url: str,
    prompt: str,
    result: Any,
    path: Path = HISTORY_PATH,
) -> None:
    items = load_history(path)

    # Try to build a short summary from result
    summary = ""
    try:
        if isinstance(result, dict):
            if "content" in result and isinstance(result["content"], str):
                summary = result["content"][:200]
            else:
                summary = json.dumps(result, ensure_ascii=False)[:200]
        else:
            summary = str(result)[:200]
    except Exception:
        summary = ""

    items.insert(
        0,
        HistoryItem(
            timestamp=_now_iso(),
            provider=provider,
            url=url,
            prompt=prompt,
            summary=summary,
        ),
    )
    items = items[:MAX_HISTORY]
    data = [asdict(i) for i in items]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")



