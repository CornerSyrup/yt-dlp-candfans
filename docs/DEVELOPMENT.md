# 開発と検証

利用者向けのインストールと操作方法は [README](../README.md) を参照してください。

## オフラインテストとビルド

Python 3.10 以降を使用します。テスト用の依存関係を用意した後は、単体テストとビルドにネットワーク接続は不要です。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/check_public_fixtures.py
.\.venv\Scripts\python.exe scripts/build.py --output dist/yt-dlp-candfans.zip
.\.venv\Scripts\python.exe scripts/verify_archive.py --archive dist/yt-dlp-candfans.zip
```

公開 fixture は匿名化した派生データです。実際の Cookie、個人情報、署名付きメディア URL、動画は追加しないでください。[fixture の説明](../tests/fixtures/README.md) と [確認済み事項と未確認事項](KNOWN_UNVERIFIED.md) に、検証の範囲を記載しています。

## 公式 Windows EXE での検証

既存の公式 `yt-dlp.exe` を指定します。サムネイルの埋め込み検証には、既存の FFmpeg と ffprobe も必要です。

```powershell
python scripts/verify_windows.py --exe 'C:\Tools\yt-dlp.exe' `
    --zip dist/yt-dlp-candfans.zip --output .test-tmp/windows
python scripts/verify_thumbnail.py --exe 'C:\Tools\yt-dlp.exe' `
    --zip dist/yt-dlp-candfans.zip --output .test-tmp/thumbnail
```

これらのスクリプトはテスト専用の通信処理で API とメディアを置き換えます。サムネイル検証では、1 秒の合成 HLS 動画と JPEG を使用し、`attached_pic` と抽出画像の SHA256 を確認します。実際の CandFans API や CDN の検証とは別のテストです。配布 ZIP にテスト用通信処理や fixture は含まれません。

## CI とリリース

[CI](https://github.com/CornerSyrup/yt-dlp-candfans/actions/workflows/ci.yml) は Ubuntu／Windows、Python 3.12／3.13 でオフラインテストと ZIP の検証を実行します。公式 Windows EXE の読み込みと CLI 動作も fixture で確認します。

保守担当者が CI の成功を確認し、未使用の `v*` バージョンタグを push すると、Release workflow が同じタグのソースを再検証し、`yt-dlp-candfans.zip` と `SHA256SUMS.txt` を公開します。公開にはタグに対応するコミットを使用し、秘密情報や実際のメディアを含めません。

API の処理を変更するときは、匿名化した根拠と再現テストを追加し、未確認の構造やフィールドの意味を確定事項として扱わないでください。
