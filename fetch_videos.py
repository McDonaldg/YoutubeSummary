"""YouTube動画の検索・フィルタリングと字幕取得。

検索結果は新着動画を見逃さないよう毎回APIから取得する（キャッシュしない）。
動画詳細・字幕は動画IDごとに cache/ 配下へ永続化し、同一動画の再取得を避ける。
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

import isodate
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)

import config
import quota_tracker


class QuotaExceededError(RuntimeError):
    """YouTube Data API のクォータ超過（403 quotaExceeded）を表す。"""


@dataclass
class VideoInfo:
    video_id: str
    title: str
    description: str
    channel_title: str
    published_at: str
    duration_minutes: float
    url: str

    def to_dict(self) -> dict:
        return asdict(self)


def _load_json_cache(path) -> Optional[dict]:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_json_cache(path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _youtube_client():
    return build("youtube", "v3", developerKey=config.require_youtube_key())


def search_video_ids(query: str, max_results: int | None = None) -> list[str]:
    """検索クエリに一致する動画IDを取得する（実行のたびにAPIへ問い合わせ、新着動画を検知する）。"""
    max_results = max_results or config.YT_MAX_RESULTS
    max_results = min(max(max_results, 1), 10)

    youtube = _youtube_client()
    try:
        response = (
            youtube.search()
            .list(
                part="id",
                q=query,
                type="video",
                order="date",
                maxResults=max_results,
                relevanceLanguage="ja",
            )
            .execute()
        )
    except HttpError as e:
        if e.resp.status == 403 and "quotaExceeded" in str(e):
            raise QuotaExceededError(
                "YouTube Data API のクォータ上限に達しました。処理を中断します。"
                " 明日以降に再実行するか、クォータを確認してください。"
            ) from e
        raise

    quota_tracker.record_usage(quota_tracker.SEARCH_LIST_COST)
    video_ids = [item["id"]["videoId"] for item in response.get("items", [])]
    print(f"[fetch_videos] 検索取得: '{query}' -> {len(video_ids)}件")
    return video_ids


def get_video_details(video_ids: list[str], force: bool = False) -> list[VideoInfo]:
    """動画IDから詳細情報（タイトル・概要・再生時間）を取得（キャッシュ利用）。"""
    results: list[VideoInfo] = []
    missing: list[str] = []

    for vid in video_ids:
        cache_path = config.CACHE_VIDEOS_DIR / f"{vid}.json"
        if not force:
            cached = _load_json_cache(cache_path)
            if cached is not None:
                results.append(VideoInfo(**cached))
                continue
        missing.append(vid)

    if missing:
        youtube = _youtube_client()
        try:
            response = (
                youtube.videos()
                .list(part="snippet,contentDetails", id=",".join(missing))
                .execute()
            )
        except HttpError as e:
            if e.resp.status == 403 and "quotaExceeded" in str(e):
                raise QuotaExceededError(
                    "YouTube Data API のクォータ上限に達しました。処理を中断します。"
                ) from e
            raise

        quota_tracker.record_usage(quota_tracker.VIDEOS_LIST_COST)
        for item in response.get("items", []):
            snippet = item["snippet"]
            duration = isodate.parse_duration(item["contentDetails"]["duration"])
            info = VideoInfo(
                video_id=item["id"],
                title=snippet.get("title", ""),
                description=snippet.get("description", ""),
                channel_title=snippet.get("channelTitle", ""),
                published_at=snippet.get("publishedAt", ""),
                duration_minutes=round(duration.total_seconds() / 60, 1),
                url=f"https://www.youtube.com/watch?v={item['id']}",
            )
            _save_json_cache(config.CACHE_VIDEOS_DIR / f"{info.video_id}.json", info.to_dict())
            results.append(info)
            print(f"[fetch_videos] 詳細取得: {info.title} ({info.duration_minutes}分)")

    return results


def filter_by_duration(
    videos: list[VideoInfo],
    min_minutes: float | None = None,
    max_minutes: float | None = None,
) -> list[VideoInfo]:
    min_minutes = config.YT_MIN_DURATION_MIN if min_minutes is None else min_minutes
    max_minutes = config.YT_MAX_DURATION_MIN if max_minutes is None else max_minutes
    return [v for v in videos if min_minutes <= v.duration_minutes <= max_minutes]


def fetch_transcript(video_id: str, lang: str | None = None, force: bool = False) -> Optional[str]:
    """日本語字幕（無ければ自動生成字幕）を取得しキャッシュする。取得不可ならNone。"""
    lang = lang or config.YT_TRANSCRIPT_LANG
    cache_path = config.CACHE_TRANSCRIPTS_DIR / f"{video_id}.txt"

    if not force and cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    api = YouTubeTranscriptApi()
    try:
        transcript_list = api.list(video_id)
        try:
            transcript = transcript_list.find_transcript([lang])
        except NoTranscriptFound:
            transcript = transcript_list.find_generated_transcript([lang])
        fetched = transcript.fetch()
        text = "\n".join(snippet.text for snippet in fetched)
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
        print(f"[fetch_videos] 字幕取得不可: {video_id} ({e.__class__.__name__})")
        return None

    cache_path.write_text(text, encoding="utf-8")
    return text


def search_and_collect(
    queries: list[str] | None = None,
    max_results: int | None = None,
    force: bool = False,
) -> list[dict]:
    """検索 -> 再生時間フィルタ -> 字幕取得までを一括実行し、パイプライン用データを返す。"""
    queries = queries or config.YT_QUERIES
    if not queries:
        raise ValueError("検索クエリが指定されていません（YT_QUERIES を設定してください）。")

    collected: list[dict] = []
    seen_ids: set[str] = set()

    for query in queries:
        video_ids = search_video_ids(query, max_results=max_results)
        details = get_video_details(video_ids, force=force)
        filtered = filter_by_duration(details)
        print(
            f"[fetch_videos] '{query}': {len(details)}件中 {len(filtered)}件が"
            f" {config.YT_MIN_DURATION_MIN}-{config.YT_MAX_DURATION_MIN}分の対象"
        )

        for video in filtered:
            if video.video_id in seen_ids:
                continue
            seen_ids.add(video.video_id)

            transcript = fetch_transcript(video.video_id, force=force)
            if transcript is None:
                continue

            collected.append(
                {
                    **video.to_dict(),
                    "query": query,
                    "transcript_path": str(
                        config.CACHE_TRANSCRIPTS_DIR / f"{video.video_id}.txt"
                    ),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
            )

    return collected


def _main() -> None:
    parser = argparse.ArgumentParser(description="YouTube動画検索・字幕取得")
    parser.add_argument("--query", action="append", help="検索キーワード（複数指定可）")
    parser.add_argument("--max-results", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="キャッシュを無視して再取得")
    args = parser.parse_args()

    try:
        videos = search_and_collect(
            queries=args.query, max_results=args.max_results, force=args.force
        )
    except (QuotaExceededError, config.ConfigError) as e:
        print(f"[fetch_videos] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n合計 {len(videos)} 件の動画（字幕取得済み）:")
    for v in videos:
        print(f"  - [{v['video_id']}] {v['title']} ({v['duration_minutes']}分)")


if __name__ == "__main__":
    _main()
