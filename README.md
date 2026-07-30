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

# 統合デッキ生成後、LINEへ配信する場合
python3 main.py --send-line --deck-title "今週のYouTube要約"
```

各スクリプトは単体でも実行できます。

```bash
python3 fetch_videos.py --query "キーワード" --max-results 5
python3 summarize_to_md.py --video-id <VIDEO_ID>
python3 generate_slides.py --video-id <VIDEO_ID> --format pptx
python3 combine_deck.py --video-id <ID1> --video-id <ID2> --title "統合デッキ名"
python3 send_line.py --file output/markdown/digest_xxx.md
```

## パイプライン構成

1. `fetch_videos.py` — YouTube Data API v3で検索し、再生時間（既定10〜30分）でフィルタ、`youtube-transcript-api`で日本語字幕（無ければ自動生成字幕）を取得。検索結果・動画詳細・字幕はすべて `cache/` にキャッシュし、既存データは再取得しない。
2. `summarize_to_md.py` — 字幕をClaude API（1動画1回呼び出し、`max_tokens`は`.env`で制御）で「背景・キーポイント・結論」の構造化Markdownに要約し `output/markdown/` に保存。
3. `generate_slides.py` — 構造化Markdownを見出し単位でスライド化し、`python-pptx`でpptx、または自己完結型HTMLスライド（外部ライブラリ不要、矢印キーで送り操作）を `output/slides/` に生成。
4. `combine_deck.py` — 今回の実行で処理した全動画の要約を1つの`.md`（`output/markdown/digest_*.md`）に結合。**NotebookLMへはこのファイルを手動でアップロードする運用**を想定（NotebookLMに公開APIが無いため自動投入は非対応）。
5. `send_line.py` — 統合デッキをLINE Messaging APIのbroadcastでテキスト配信（`--send-line`指定時のみ、既定はスキップ）。

## LINE配信のセットアップ（任意）

LINE Notifyは廃止されているため、LINE Messaging APIを使用します。

1. [LINE Developers](https://developers.line.biz/) でプロバイダーを作成
2. 「Messaging API」チャネルを新規作成
3. チャネルの「Messaging API設定」タブで「チャネルアクセストークン（長期）」を発行し、`.env`の`LINE_CHANNEL_ACCESS_TOKEN`に設定
4. 同タブに表示されるQRコードを自分のLINEアプリでスキャンし、Botを友だち追加
5. `python3 main.py --send-line` を実行すると、そのBotから自分宛にテキストが届く

broadcast配信（Botの友だち全員に送信）を使っているため、Botを自分だけが友だち追加していれば実質的に個人専用チャネルになります。

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
combine_deck.py         複数動画要約の統合デッキ生成（NotebookLM手動取り込み用）
send_line.py            統合デッキのLINE配信
main.py                 パイプライン実行エントリーポイント
cache/                  検索結果・動画詳細・字幕のキャッシュ（gitignore対象）
output/markdown/        構造化Markdown要約・統合デッキ(digest_*.md)
output/slides/          生成済みスライド
```
