"""複数動画の要約Markdownを1つの統合デッキに結合する。

NotebookLMへ手動で読み込ませる用途を想定し、単一の.mdファイルにまとめる。
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import config
from generate_slides import parse_markdown


def combine_summaries(
    video_ids: list[str],
    title: str | None = None,
    out_name: str | None = None,
) -> Path:
    """指定した動画IDの要約Markdownを1つの統合デッキ(.md)に結合する。"""
    if not video_ids:
        raise ValueError("結合対象の動画IDがありません。")

    decks = []
    for vid in video_ids:
        md_path = config.OUTPUT_MARKDOWN_DIR / f"{vid}.md"
        if not md_path.exists():
            print(f"[combine_deck] スキップ（要約未生成）: {vid}")
            continue
        decks.append(parse_markdown(md_path.read_text(encoding="utf-8")))

    if not decks:
        raise FileNotFoundError("結合可能な要約Markdownが見つかりませんでした。")

    now = datetime.now()
    deck_title = title or f"YouTube要約まとめ ({now.strftime('%Y-%m-%d')})"

    lines = [f"# {deck_title}\n"]
    for i, deck in enumerate(decks, start=1):
        meta_line = " / ".join(p for p in (deck.meta.get("channel"), deck.meta.get("url")) if p)
        lines.append(f"## {i}. {deck.title}")
        if meta_line:
            lines.append(f"_{meta_line}_\n")
        for slide in deck.slides:
            lines.append(f"### {slide.heading}")
            lines.extend(f"- {b}" for b in slide.bullets)
            lines.append("")
        lines.append("")

    content = "\n".join(lines).strip() + "\n"
    out_name = out_name or f"digest_{now.strftime('%Y%m%d_%H%M%S')}"
    out_path = config.OUTPUT_MARKDOWN_DIR / f"{out_name}.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"[combine_deck] 統合デッキ生成: {out_path} ({len(decks)}件を結合)")
    return out_path


def _main() -> None:
    parser = argparse.ArgumentParser(description="複数動画の要約Markdownを1つの統合デッキに結合")
    parser.add_argument("--video-id", action="append", required=True, help="結合する動画ID（複数指定可）")
    parser.add_argument("--title", default=None)
    parser.add_argument("--out-name", default=None)
    args = parser.parse_args()
    combine_summaries(args.video_id, title=args.title, out_name=args.out_name)


if __name__ == "__main__":
    _main()
