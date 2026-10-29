# yt-dlp-candfans

[![CI](https://github.com/CornerSyrup/yt-dlp-candfans/actions/workflows/ci.yml/badge.svg)](https://github.com/CornerSyrup/yt-dlp-candfans/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/CornerSyrup/yt-dlp-candfans)](https://github.com/CornerSyrup/yt-dlp-candfans/releases/latest)

CandFans のプロフィールページと個別投稿に対応する yt-dlp プラグインです。公式 Windows `yt-dlp.exe` で利用でき、yt-dlp 本体の変更や Python のインストールは不要です。プロフィールの自動ページ送り、HLS 動画、メタデータ、サムネイルに対応します。

## インストール

[最新版の yt-dlp-candfans.zip をダウンロード](https://github.com/CornerSyrup/yt-dlp-candfans/releases/latest/download/yt-dlp-candfans.zip)し、**解凍せずに** `yt-dlp.exe` と同じ場所の `yt-dlp-plugins` フォルダーへ保存します。

```text
MyDownloader/
  yt-dlp.exe
  yt-dlp-plugins/
    yt-dlp-candfans.zip
```

更新時は既存の ZIP を置き換えてください。旧名 `candfans.zip` がある場合は削除し、同じプラグインを重複配置しないでください。ユーザー単位の配置先 `%APPDATA%\yt-dlp\plugins\yt-dlp-candfans.zip` も利用できます。配置先はいずれか一方を使用します。

MP4 への変換やサムネイルの埋め込みには、yt-dlp が検出できる FFmpeg が必要です。必要に応じて `--ffmpeg-location 'C:\Tools\ffmpeg\bin'` で指定できます。Release の `SHA256SUMS.txt` と `Get-FileHash .\yt-dlp-candfans.zip -Algorithm SHA256` でダウンロードした ZIP を照合できます。

## 個別投稿をダウンロード

PowerShell で `yt-dlp.exe` のあるフォルダーを開き、投稿 URL を置き換えて実行します。

```powershell
.\yt-dlp.exe --ignore-config `
    -N 8 -c --embed-thumbnail --remux-video mp4 `
    --windows-filenames `
    -o '.\downloads\%(id)s.%(ext)s' `
    'https://candfans.jp/posts/comment/show/YOUR_POST_ID'
```

`-N 8` は HLS の並列ダウンロード数、`-c` は中断したダウンロードの再開です。`--embed-thumbnail` を指定すると動画にサムネイルを埋め込みます。サムネイルだけを別ファイルで保存する場合は `--write-thumbnail` を使用してください。

## プロフィールを一括ダウンロード

`YOUR_CREATOR_CODE` をプロフィール URL のクリエイターコードに置き換えます。投稿を列挙し、空のページまで自動的にページを送ります。

```powershell
.\yt-dlp.exe --ignore-config `
    -N 8 -c --embed-thumbnail --remux-video mp4 `
    --download-archive '.\downloaded.txt' `
    --windows-filenames `
    -o '.\downloads\%(uploader_id)s\%(id)s.%(ext)s' `
    'https://candfans.jp/YOUR_CREATOR_CODE'
```

`--download-archive` は完了した動画 ID を記録し、次回の重複ダウンロードを防ぎます。失敗した投稿を飛ばして続けるには `--ignore-errors` を追加し、終了後に警告やエラーを確認してください。複数添付の一部が失敗した場合、ほかの添付が保存されても投稿全体の完了を意味しません。

クリエイター ID の自動取得に失敗した場合は、確認済みの数値 ID を指定します。`YOUR_VERIFIED_USER_ID` を実際の数値に置き換えてください。

```powershell
.\yt-dlp.exe --ignore-config `
    --extractor-args 'candfansprofile:user_id=YOUR_VERIFIED_USER_ID' `
    --embed-thumbnail --remux-video mp4 `
    'https://candfans.jp/YOUR_CREATOR_CODE'
```

## ログインが必要な場合

Netscape/Mozilla 形式の `cookies.txt` を手動で用意し、コマンドに `--cookies '.\cookies.txt'` を追加します。Cookie が不要なリクエストでは省略できます。プラグインは自動ログインを行いません。Cookie や認証情報を含むログを公開しないでください。

```powershell
.\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
    --embed-thumbnail --remux-video mp4 `
    'https://candfans.jp/posts/comment/show/YOUR_POST_ID'
```

## メタデータとサムネイルの設定

動画や HLS manifest を取得せずにメタデータを確認する場合：

```powershell
.\yt-dlp.exe --ignore-config `
    --extractor-args 'candfanspost:metadata_only=true' `
    --ignore-no-formats-error --skip-download --dump-json `
    'https://candfans.jp/posts/comment/show/YOUR_POST_ID'
```

`metadata_only` は添付動画 URL を出力せず、サムネイルの埋め込みも行いません。通常の `--skip-download` は manifest を取得することがあります。

既知のサムネイル相対パスは `https://video.candfans.jp` を使用します。別の配信元を確認済みの場合は `--extractor-args 'candfanspost:thumbnail_origin=https://YOUR_VERIFIED_HOST'` を指定できます。値は HTTPS の origin のみで、パスやクエリは指定できません。画像形式の変換が必要な場合は `--convert-thumbnails jpg` を追加してください。

## 問題が発生した場合

- プラグインが見つからない：ZIP の配置先と重複配置を確認してください。一部の yt-dlp では `--list-extractors` がプラグイン読み込み前に実行されるため、一覧にないことだけでは読み込み失敗と判断できません。対象 URL に `-v --simulate` を付け、プラグインの読み込みメッセージを確認できます。この操作は API や manifest に接続する場合があります。
- 認証エラー：そのリクエストの Cookie とアクセス権を確認してください。エラーだけからアカウント全体のログイン状態は判断できません。
- 動画やサムネイルの取得に失敗する：表示された HTTP／HLS エラーを確認してください。`is_downloadable=false` はプラグインのダウンロード停止条件ではありません。
- MP4 変換や埋め込みに失敗する：FFmpeg が利用可能か確認してください。サムネイルの URL がない場合は埋め込まれません。

利用できるのは、自分がアクセス・ダウンロードする権利を持つコンテンツです。API に添付がない場合にプレビューへ切り替えたり、アクセス制限や DRM を回避したりする機能はありません。現在は `can_browsing` が数値 `1` または真偽値 `true` の投稿を処理します。クリエイター検索 API の実際の応答構造など、未確認の事項は [既知の仕様と未検証事項](docs/KNOWN_UNVERIFIED.md) を参照してください。

追加の PowerShell 例は [Windows_commands.ps1](examples/Windows_commands.ps1) にあります。不具合報告にはバージョン、再現手順、機密情報を取り除いた最小限のログを添えてください。

作者・メンテナー：CornerSyrup（Klein）。[貢献者](docs/CONTRIBUTORS.md) ／ [MIT License](LICENSE)
