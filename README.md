# PDF → Mathpix → ZIP

PDFをブラウザにドラッグ&ドロップすると、Mathpix PDF API にアップロードして
変換が終わり次第、図版入りのZIP (LaTeX) やDOCX/Markdown/HTMLとしてダウンロードできる
Web UI / CLI / Celeryワーカー構成です。

## 必要なもの

- Python 3.10 以上 (またはDocker)
- Mathpix の `app_id` / `app_key`
  ([Mathpix Console](https://accounts.mathpix.com/) で取得)
- (任意) Redis — 複数ユーザ同時処理やバックグラウンド実行をする場合

## クイックスタート

### A. Docker Compose (推奨: Web + Worker + Redis 一括起動)

```bash
cp .env.example .env
# .env に MATHPIX_APP_ID と MATHPIX_APP_KEY を記入

docker compose up --build
```

<http://localhost:8000> を開いてPDFをドロップ。

### B. ローカル Python (Redis不要・eagerモード)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env で CELERY_TASK_ALWAYS_EAGER=1 の行を有効化

python server.py
```

Redis なしでタスクが同一プロセスで実行されます (同時ユーザには不向き)。

### C. ローカル Python + Redis + Worker

```bash
redis-server &   # 別ターミナルで
celery -A celery_app.celery_app worker --loglevel=info &
python server.py
```

## CLI (バッチ処理・Celery不要)

```bash
python cli.py paper.pdf                  # → outputs/paper.tex.zip
python cli.py paper.pdf --fmt docx -o ./out
python cli.py *.pdf --fmt md
```

## テスト

```bash
pip install -r requirements-dev.txt
pytest
```

Mathpix API は全て `unittest.mock` でモックしているので、ネットワークや
キーなしで実行できます。

## 動作の流れ (Web UI)

1. ブラウザが PDF + 変換オプションを `POST /upload` に送信
2. サーバーが Celery タスクを enqueue し、`task_id` を返す
3. ワーカーが Mathpix PDF API にアップロードし、`completed` になるまでポーリング
4. ブラウザが `GET /status/{task_id}` でワーカーの進捗を取得 (2秒間隔)
5. `state=SUCCESS` になったら、選択したフォーマットで `GET /download/{task_id}`
6. サーバーが Mathpix から `/v3/pdf/{pdf_id}.<fmt>` を取得して返す

## 変換オプション (UI から変更可能)

| オプション | デフォルト | 説明 |
| --- | --- | --- |
| 数式インライン区切り | `$...$` | `\(...\)` も選択可 |
| `rm_spaces` | on | 余分な空白を正規化 |
| `numbers_default_to_math` | off | 数字を常に数式として扱う |
| `include_line_data` | off | 行単位メタデータを含める |

## 出力フォーマット

| フォーマット | 説明 |
| --- | --- |
| `tex.zip` | LaTeXソース + 抽出された図版画像 (デフォルト・図版が欲しいならこれ) |
| `docx` | Microsoft Word |
| `md` | GitHub-flavored Markdown (画像はBase64埋め込み) |
| `html` | 単一HTML |
| `mmd` | Mathpix Markdown |

## ファイル構成

```
.
├── server.py            # FastAPI エントリポイント
├── cli.py               # コマンドラインインターフェース
├── celery_app.py        # Celery インスタンス (broker/backend 設定)
├── tasks.py             # Celery タスク (upload → poll → return pdf_id)
├── mathpix_client.py    # Mathpix API ラッパー (全エントリポイントで共有)
├── templates/
│   └── index.html       # ドラッグ&ドロップUI
├── tests/
│   └── test_mathpix_client.py
├── Dockerfile
├── docker-compose.yml   # web + worker + redis
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── outputs/             # ダウンロードしたZIPのキャッシュ (gitignore)
```

## 注意

- `.env` はリポジトリにコミットされません。
- `outputs/` は web / worker コンテナ間で共有する必要があるため、
  compose 設定で bind mount されています。
- 本番運用時は Mathpix キーを Secrets Manager 等で管理し、
  `outputs/` の定期クリーンアップを追加してください。
