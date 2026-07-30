"""字幕テキストから構造化Markdown要約を生成する。

コスト制御:
  - 1動画につきClaude APIの呼び出しは1回のみ（config.LLM_MAX_CALLS_PER_VIDEO）。
  - 出力トークン上限は config.LLM_MAX_TOKENS で固定。
  - ANTHROPIC_API_KEY 未設定時は簡易抽出フォールバックを使用し、コスト0で動作確認できる。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import config

# 入力コストを抑えるため、字幕が極端に長い場合は先頭のみ使用する
TRANSCRIPT_MAX_CHARS = 20000

PROMPT_TEMPLATE = """あなたはプレゼン資料作成の専門家です。以下のYouTube動画の字幕テキストを分析し、\
日本語のMarkdownで構造化してください。出力は必ず次の見出し構成に厳密に従ってください。\
各見出しの下は箇条書き（「- 」始まり）で3〜6項目、簡潔に。見出しやフォーマット以外の説明文は書かないでください。

## 背景
## キーポイント
## 結論

--- 動画タイトル ---
{title}

--- 字幕テキスト ---
{transcript}
"""


def _extractive_fallback(title: str, transcript: str) -> str:
    """APIキー未設定時の簡易フォールバック（コスト0、動作確認用）。"""
    sentences = [s.strip() for s in transcript.replace("\n", " ").split("。") if s.strip()]
    head = sentences[: min(5, len(sentences))]
    mid_start = len(sentences) // 2
    mid = sentences[mid_start : mid_start + 3]
    tail = sentences[-3:] if len(sentences) > 3 else []

    def bullets(items: list[str]) -> str:
        if not items:
            return "- (情報なし)"
        return "\n".join(f"- {s}。" for s in items)

    return (
        "## 背景\n"
        f"{bullets(head)}\n\n"
        "## キーポイント\n"
        f"{bullets(mid)}\n\n"
        "## 結論\n"
        f"{bullets(tail)}\n"
    )


def _summarize_with_claude(title: str, transcript: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prompt = PROMPT_TEMPLATE.format(title=title, transcript=transcript[:TRANSCRIPT_MAX_CHARS])

    response = client.messages.create(
        model=config.LLM_MODEL,
        max_tokens=config.LLM_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def summarize_video(video: dict, force: bool = False) -> Path:
    """1動画分のMarkdown要約を生成し output/markdown/{video_id}.md に保存する。"""
    video_id = video["video_id"]
    out_path = config.OUTPUT_MARKDOWN_DIR / f"{video_id}.md"

    if out_path.exists() and not force:
        print(f"[summarize_to_md] キャッシュ利用: {out_path.name}")
        return out_path

    transcript_path = Path(video.get("transcript_path") or config.CACHE_TRANSCRIPTS_DIR / f"{video_id}.txt")
    if not transcript_path.exists():
        raise FileNotFoundError(f"字幕キャッシュが見つかりません: {transcript_path}")
    transcript = transcript_path.read_text(encoding="utf-8")

    if config.ANTHROPIC_API_KEY:
        body = _summarize_with_claude(video["title"], transcript)
        source = "claude"
    else:
        print("[summarize_to_md] ANTHROPIC_API_KEY 未設定のため抽出フォールバックを使用します")
        body = _extractive_fallback(video["title"], transcript)
        source = "extractive-fallback"

    frontmatter = (
        "---\n"
        "marp: true\n"
        f"title: {json.dumps(video['title'], ensure_ascii=False)}\n"
        f"video_id: {video_id}\n"
        f"url: {video.get('url', '')}\n"
        f"channel: {json.dumps(video.get('channel_title', ''), ensure_ascii=False)}\n"
        f"published_at: {video.get('published_at', '')}\n"
        f"summary_source: {source}\n"
        "---\n\n"
    )
    content = f"{frontmatter}# {video['title']}\n\n{body.strip()}\n"
    out_path.write_text(content, encoding="utf-8")
    print(f"[summarize_to_md] 生成完了: {out_path}")
    return out_path


def _main() -> None:
    parser = argparse.ArgumentParser(description="字幕からMarkdown要約を生成")
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--title", default=None, help="動画タイトル（メタ情報キャッシュが無い場合用）")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    meta_path = config.CACHE_VIDEOS_DIR / f"{args.video_id}.json"
    if meta_path.exists():
        video = json.loads(meta_path.read_text(encoding="utf-8"))
    elif args.title:
        video = {
            "video_id": args.video_id,
            "title": args.title,
            "url": f"https://www.youtube.com/watch?v={args.video_id}",
            "channel_title": "",
            "published_at": "",
        }
    else:
        print(
            f"[summarize_to_md] ERROR: {meta_path} が見つかりません。--title を指定してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    summarize_video(video, force=args.force)


if __name__ == "__main__":
    _main()
