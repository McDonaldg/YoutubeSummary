"""パイプライン実行エントリーポイント。

検索 -> 字幕取得 -> Markdown要約 -> スライド生成 を一括実行する。
各段階はキャッシュ済みデータがあれば再利用し、API呼び出しを最小化する。
"""
from __future__ import annotations

import argparse
import sys

import config
import quota_tracker
from combine_deck import combine_summaries
from config import ConfigError
from fetch_videos import QuotaExceededError, search_and_collect
from generate_slides import generate as generate_slides_for
from send_line import send_deck
from summarize_to_md import summarize_video


def run_pipeline(
    queries: list[str] | None = None,
    max_results: int | None = None,
    slide_format: str | None = None,
    force: bool = False,
    send_line: bool = False,
    deck_title: str | None = None,
) -> list[dict]:
    print("=== 1. YouTube動画の検索・字幕取得 ===")
    try:
        videos = search_and_collect(queries=queries, max_results=max_results, force=force)
    except QuotaExceededError as e:
        print(f"[main] ERROR: {e}", file=sys.stderr)
        print(quota_tracker.usage_summary())
        sys.exit(1)
    except ConfigError as e:
        print(f"[main] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(quota_tracker.usage_summary())

    if not videos:
        print("[main] 対象動画が見つかりませんでした（再生時間フィルタまたは字幕なし）。")
        return []

    results = []
    for video in videos:
        video_id = video["video_id"]
        print(f"\n=== 2-3. 要約生成: {video['title']} ===")
        try:
            md_path = summarize_video(video, force=force)
        except Exception as e:  # noqa: BLE001
            print(f"[main] 要約失敗、スキップします: {video_id} ({e})", file=sys.stderr)
            continue

        print(f"=== 4. スライド生成: {video_id} ===")
        try:
            slide_path = generate_slides_for(video_id, fmt=slide_format)
        except Exception as e:  # noqa: BLE001
            print(f"[main] スライド生成失敗、スキップします: {video_id} ({e})", file=sys.stderr)
            continue

        results.append({**video, "markdown_path": str(md_path), "slide_path": str(slide_path)})

    print(f"\n=== 完了: {len(results)}/{len(videos)} 件のスライドを生成しました ===")
    for r in results:
        print(f"  - {r['title']}\n      md: {r['markdown_path']}\n      slide: {r['slide_path']}")

    if results:
        print("\n=== 5. 統合デッキ生成（NotebookLM取り込み用） ===")
        try:
            deck_path = combine_summaries(
                [r["video_id"] for r in results], title=deck_title
            )
        except Exception as e:  # noqa: BLE001
            print(f"[main] 統合デッキ生成失敗: {e}", file=sys.stderr)
            deck_path = None

        if deck_path and send_line:
            print("=== 6. LINE配信 ===")
            try:
                send_deck(deck_path)
            except Exception as e:  # noqa: BLE001
                print(f"[main] LINE配信失敗: {e}", file=sys.stderr)

    return results


def _main() -> None:
    parser = argparse.ArgumentParser(description="YouTube要約スライド自動生成パイプライン")
    parser.add_argument("--query", action="append", help="検索キーワード（複数指定可、未指定なら.envのYT_QUERIES）")
    parser.add_argument("--max-results", type=int, default=None, help=f"クエリあたり最大件数（既定: {config.YT_MAX_RESULTS}, 上限10）")
    parser.add_argument("--format", choices=["pptx", "html"], default=None, help=f"スライド形式（既定: {config.SLIDE_FORMAT}）")
    parser.add_argument("--force", action="store_true", help="キャッシュを無視して全段階を再実行")
    parser.add_argument("--send-line", action="store_true", help="統合デッキをLINEへ配信する（既定はしない）")
    parser.add_argument("--deck-title", default=None, help="統合デッキのタイトル")
    args = parser.parse_args()

    run_pipeline(
        queries=args.query,
        max_results=args.max_results,
        slide_format=args.format,
        force=args.force,
        send_line=args.send_line,
        deck_title=args.deck_title,
    )


if __name__ == "__main__":
    _main()
