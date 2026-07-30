# YoutubeSummary

関心テーマに基づいてYouTube動画を自動検索し、字幕を要約してプレゼンスライド（pptx / HTML）を自動生成するパイプラインです。

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env に YOUTUBE_API_KEY / ANTHROPIC_API_KEY 等を設定
```

- `ANTHROPIC_API_KEY` 未設定の場合、要約は簡易抽出フォールバックで動作します（コスト0での動作確認用）。

## 使い方

```bash
# パイプライン一括実行（.env の YT_QUERIES を使用）
python3 main.py

# クエリと出力形式を指定
python3 main.py --query "生成AI 活用事例" --max-results 5 --format html

# キャッシュを無視して再取得・再生成
python3 main.py --force
```

各スクリプトは単体でも実行できます。

```bash
python3 fetch_videos.py --query "キーワード" --max-results 5
python3 summarize_to_md.py --video-id <VIDEO_ID>
python3 generate_slides.py --video-id <VIDEO_ID> --format pptx
```

## パイプライン構成

1. `fetch_videos.py` — YouTube Data API v3で検索し、再生時間（既定10〜30分）でフィルタ、`youtube-transcript-api`で日本語字幕（無ければ自動生成字幕）を取得。検索結果・動画詳細・字幕はすべて `cache/` にキャッシュし、既存データは再取得しない。
2. `summarize_to_md.py` — 字幕をClaude API（1動画1回呼び出し、`max_tokens`は`.env`で制御）で「背景・キーポイント・結論」の構造化Markdownに要約し `output/markdown/` に保存。NotebookLMへのソース投入にもそのまま利用可能。
3. `generate_slides.py` — 構造化Markdownを見出し単位でスライド化し、`python-pptx`でpptx、または自己完結型HTMLスライド（外部ライブラリ不要、矢印キーで送り操作）を `output/slides/` に生成。

## コスト・利用制限ガードレール

- YouTube検索は1クエリあたり最大10件（既定5件、`YT_MAX_RESULTS`で調整）。
- 全取得データはキャッシュ利用し、`--force`を指定しない限り再取得しない。
- YouTube API のクォータ超過（403 quotaExceeded）を検知すると、安全に処理を中断しエラーメッセージを表示する。
- LLM呼び出しは1動画につき最大1回、出力トークン上限は`LLM_MAX_TOKENS`で固定。

## ディレクトリ構成

```
config.py              設定・APIキー・キャッシュ管理
fetch_videos.py         YouTube検索・字幕取得
summarize_to_md.py      Markdown要約生成
generate_slides.py      スライド生成（pptx / html）
main.py                 パイプライン実行エントリーポイント
cache/                  検索結果・動画詳細・字幕のキャッシュ（gitignore対象）
output/markdown/        構造化Markdown要約
output/slides/          生成済みスライド
```
