# PDF → Mathpix → ZIP

PDFをブラウザにドラッグ&ドロップすると、Mathpix PDF API にアップロードして
変換が終わり次第、図版入りのZIP (LaTeX) やDOCX/Markdown/HTMLとしてダウンロードできる
ローカルWeb UIです。

## 必要なもの

- Python 3.10 以上
- Mathpix の `app_id` / `app_key`
  ([Mathpix Console](https://accounts.mathpix.com/) で取得)

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# .env に MATHPIX_APP_ID と MATHPIX_APP_KEY を記入
```

## 起動

```bash
python server.py
```

ブラウザで <http://127.0.0.1:8000> を開き、PDFをドロップしてください。

## 動作の流れ

1. ブラウザがPDFを `POST /upload` に送信
2. サーバーが Mathpix PDF API (`POST /v3/pdf`) にアップロードし `pdf_id` を返す
3. ブラウザが `GET /status/{pdf_id}` を2秒間隔でポーリング
4. `status=completed` になったら、選択したフォーマットで `GET /download/{pdf_id}` を呼ぶ
5. サーバーが Mathpix から `/v3/pdf/{id}.<fmt>` を取得してブラウザに返す

## 出力フォーマット

| フォーマット | 説明 |
| --- | --- |
| `tex.zip` | LaTeXソース + 抽出された図版画像 (デフォルト・図版が欲しいならこれ) |
| `docx` | Microsoft Word |
| `md` | GitHub-flavored Markdown (画像はBase64埋め込み) |
| `html` | 単一HTML |

## ファイル構成

```
.
├── server.py            # FastAPI エントリポイント
├── mathpix_client.py    # Mathpix API ラッパー
├── templates/
│   └── index.html       # ドラッグ&ドロップUI
├── requirements.txt
├── .env.example
└── outputs/             # ダウンロードしたZIPのキャッシュ (gitignore)
```

## 注意

- `.env` はリポジトリにコミットされません。
- `outputs/` に元ファイル名でZIPが保存されます (再ダウンロード用キャッシュ)。
- 複数ユーザで同時利用する場合はジョブ管理 (Redis + Celery 等) を追加してください。
