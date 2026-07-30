"""統合デッキ(Markdown)をLINEへ配信する。

LINE Notifyは廃止済みのため、LINE Messaging APIのbroadcast（Botを友だち登録した
全員に配信）を使う。個人利用ではBotを自分だけが友だち追加すれば、実質的に自分
専用の配信チャネルになる。
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import requests

import config

LINE_BROADCAST_URL = "https://api.line.me/v2/bot/message/broadcast"
LINE_TEXT_LIMIT = 5000
_MESSAGES_PER_CALL = 5


def markdown_to_line_text(md_text: str) -> str:
    """Markdown見出し・箇条書きをLINEで読みやすいプレーンテキストに変換する。"""
    lines: list[str] = []
    for line in md_text.splitlines():
        if line.startswith("### "):
            lines.append(f"◆{line[4:].strip()}")
        elif line.startswith("## "):
            lines.append(f"\n■{line[3:].strip()}")
        elif line.startswith("# "):
            lines.append(f"【{line[2:].strip()}】")
        elif line.startswith(("- ", "* ")):
            lines.append(f"・{line[2:].strip()}")
        elif line.startswith("_") and line.endswith("_") and len(line) > 1:
            lines.append(line.strip("_"))
        else:
            lines.append(line)
    return "\n".join(lines).strip()


def split_chunks(text: str, limit: int) -> list[str]:
    limit = min(max(limit, 1), LINE_TEXT_LIMIT)
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


def send_line_broadcast(text: str) -> None:
    config.require_line_token()
    chunks = split_chunks(text, config.LINE_MAX_CHARS_PER_MESSAGE)
    headers = {
        "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    for batch_start in range(0, len(chunks), _MESSAGES_PER_CALL):
        batch = chunks[batch_start : batch_start + _MESSAGES_PER_CALL]
        payload = {"messages": [{"type": "text", "text": c} for c in batch]}
        resp = requests.post(LINE_BROADCAST_URL, headers=headers, json=payload, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"LINE配信失敗 ({resp.status_code}): {resp.text}")
        done = batch_start + len(batch)
        print(f"[send_line] 配信完了: {done}/{len(chunks)}通")
        if done < len(chunks):
            time.sleep(1)


def send_deck(deck_path: Path) -> None:
    line_text = markdown_to_line_text(deck_path.read_text(encoding="utf-8"))
    send_line_broadcast(line_text)


def _main() -> None:
    parser = argparse.ArgumentParser(description="統合デッキ(Markdown)をLINEへ配信")
    parser.add_argument("--file", required=True, help="配信するMarkdownファイルパス")
    args = parser.parse_args()
    send_deck(Path(args.file))


if __name__ == "__main__":
    _main()
