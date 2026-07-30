"""設定値・APIキー・キャッシュ/出力ディレクトリの一元管理。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Windowsのコンソールは既定でcp932等の非UTF-8コードページを使うため、
# 動画タイトルに含まれる一部の文字（絵文字・中国語簡体字など）でprintが
# UnicodeEncodeErrorを起こすことがある。全スクリプトの起点であるここで
# stdout/stderrをUTF-8に強制し、表示不可能な文字は落とさず置換する。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent

# --- API keys -----------------------------------------------------------
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# --- YouTube検索ガードレール ---------------------------------------------
# API無料枠保護のため、1クエリあたりの取得件数は 1〜10 に強制する
_HARD_CAP = 10
YT_MAX_RESULTS = min(max(int(os.getenv("YT_MAX_RESULTS", "5")), 1), _HARD_CAP)

YT_QUERIES = [
    q.strip() for q in os.getenv("YT_QUERIES", "").split(",") if q.strip()
]

YT_MIN_DURATION_MIN = int(os.getenv("YT_MIN_DURATION_MIN", "10"))
YT_MAX_DURATION_MIN = int(os.getenv("YT_MAX_DURATION_MIN", "30"))

YT_TRANSCRIPT_LANG = os.getenv("YT_TRANSCRIPT_LANG", "ja")

# --- LLM (要約) コスト制御 ------------------------------------------------
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1500"))
# 1動画あたりの要約API呼び出し上限（ガードレール）
LLM_MAX_CALLS_PER_VIDEO = int(os.getenv("LLM_MAX_CALLS_PER_VIDEO", "1"))

# --- スライド出力 ---------------------------------------------------------
SLIDE_FORMAT = os.getenv("SLIDE_FORMAT", "pptx")  # "pptx" or "html"

# --- LINE配信（LINE Messaging API / broadcast） ---------------------------
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
# LINEのテキストメッセージ上限は5000文字。安全マージンを取って既定4500。
LINE_MAX_CHARS_PER_MESSAGE = int(os.getenv("LINE_MAX_CHARS_PER_MESSAGE", "4500"))

# --- ディレクトリ ---------------------------------------------------------
CACHE_DIR = Path(os.getenv("CACHE_DIR", BASE_DIR / "cache"))
CACHE_SEARCH_DIR = CACHE_DIR / "search"
CACHE_VIDEOS_DIR = CACHE_DIR / "videos"
CACHE_TRANSCRIPTS_DIR = CACHE_DIR / "transcripts"

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", BASE_DIR / "output"))
OUTPUT_MARKDOWN_DIR = OUTPUT_DIR / "markdown"
OUTPUT_SLIDES_DIR = OUTPUT_DIR / "slides"

for _d in (
    CACHE_SEARCH_DIR,
    CACHE_VIDEOS_DIR,
    CACHE_TRANSCRIPTS_DIR,
    OUTPUT_MARKDOWN_DIR,
    OUTPUT_SLIDES_DIR,
):
    _d.mkdir(parents=True, exist_ok=True)


class ConfigError(RuntimeError):
    pass


def require_youtube_key() -> str:
    if not YOUTUBE_API_KEY:
        raise ConfigError(
            "YOUTUBE_API_KEY が設定されていません。.env を作成し設定してください。"
        )
    return YOUTUBE_API_KEY


def require_line_token() -> str:
    if not LINE_CHANNEL_ACCESS_TOKEN:
        raise ConfigError(
            "LINE_CHANNEL_ACCESS_TOKEN が設定されていません。.env を設定してください。"
        )
    return LINE_CHANNEL_ACCESS_TOKEN
