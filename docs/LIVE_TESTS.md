# 実メディアテスト

通常の [CI](DEVELOPMENT.md#ci-とリリース) は fixture を使用します。実際の API、Cookie、CDN を確認するテストは、専用の GitHub Actions ワークフローに分離します。アクセス・ダウンロードする権利を持つテスト対象を設定してください。

## 実行条件

[実際の API と動画の検証](../.github/workflows/live.yml) は、`main` ブランチでの手動実行（`workflow_dispatch`）に加え、`main` へ次のファイルの変更を push した場合に起動します。

- `.github/workflows/live.yml`
- `scripts/verify_live.py`
- `yt_dlp_plugins/**`

ジョブは `main` のみで実行され、pull request、タグ作成、定期実行では起動しません。最初に必須 Secrets を確認し、一つでも未設定の場合は checkout、ツールのダウンロード、Cookie ファイル作成、メディアの取得を行わずに正常終了します。概要には **SKIPPED** と不足した Secret の名前を表示します。これはテスト成功を意味しません。

すべて設定済みの場合に限り、次の二つを実行します。

1. プロフィールの最初の投稿から最初の動画一件を選び、最後までダウンロードする。
2. 別のクリエイターの個別投稿を取得し、すべての添付動画を最後までダウンロードする。

両方でサムネイルを埋め込み、ffprobe で動画・音声・`attached_pic` を検査し、FFmpeg で動画と音声を全編デコードします。動画の一部分だけを取得するテストではありません。プロフィール側は `--playlist-end 1` により最初の投稿の最初の動画一件に制限します。複数添付がある投稿でもプロフィール側の残りの動画は取得しません。全投稿・全添付の処理や実際の複数ページ取得を検証したことにはなりません。個別投稿側はすべての添付動画を対象にします。

## Repository Secrets

GitHub のリポジトリで **Settings → Secrets and variables → Actions → New repository secret** を開き、以下を設定します。Cookie や対象 URL は workflow の入力欄、Issue、ソースコードへ記入しないでください。

| Secret | 必須 | 内容 |
|---|---|---|
| `CANDFANS_COOKIES` | はい | Netscape/Mozilla 形式の Cookie ファイル全体。改行を保持した生のテキストを設定する。Base64 化や JSON 化は不要。 |
| `CANDFANS_CREATOR_URL` | はい | テスト対象プロフィールの完全な HTTPS URL。例：`https://candfans.jp/YOUR_CREATOR_CODE`。 |
| `CANDFANS_POST_URL` | はい | 上記プロフィールとは別のクリエイターの個別投稿 URL。例：`https://candfans.jp/posts/comment/show/YOUR_POST_ID`。 |
| `CANDFANS_CREATOR_ID` | いいえ | 自動検索が使えない場合の、確認済みクリエイター数値 ID。 |

`CANDFANS_COOKIES` は先頭の `# Netscape HTTP Cookie File` 行を含め、Cookie の各列を実際のタブで区切った形式にします。ブラウザーから手動で用意したファイルの内容をそのまま登録してください。Cookie の有効期限切れや権限不足は、このテストで自動的に解決されません。

クリエイター検索 API の実際の JSON 構造は未確認です。安定した実行には、確認済みの `CANDFANS_CREATOR_ID` の設定を推奨します。自動検索で ID を決定できない場合も、この値を追加します。公開 fixture の匿名 ID を使用しないでください。

## 実行と結果の確認

GitHub の **Actions** で **実際の API と動画の検証** を選択し、**Run workflow** から `main` を指定して実行します。対象ファイルを `main` へ push した場合も、同じ条件と Secrets で実行されます。

結果の概要では、次を区別してください。

- **SKIPPED**：必要な Secrets が揃っておらず、実メディアテストを実行していない。
- **成功**：二つの対象のダウンロード、音声・動画と埋め込みサムネイルの検査、全編デコードが完了した。
- **失敗**：API、ダウンロード、後処理または検証のいずれかで失敗した。設定済みでも対象が利用可能とは限らない。

失敗はその実行で観測した結果です。`is_downloadable=false` だけを根拠に失敗理由を推測しません。追加の調査が必要な場合は、同じ設定を用いて権限のあるローカル環境で再現し、秘密情報を除去してから共有してください。

## 実行環境とデータの扱い

Windows runner の一時領域へ、固定バージョンの公式 `yt-dlp.exe 2026.10.26` と、`yt-dlp/FFmpeg-Builds` の `autobuild-2026-10-29-00-02` にある Windows 版 FFmpeg／ffprobe をダウンロードし、それぞれ固定した SHA256 と照合します。runner に既存の FFmpeg があることは前提にしていません。ローカル端末へのインストールやシステム全体への恒久的な配置は行いません。

ジョブ全体の上限は 90 分です。各ダウンロードと各動画の全編デコードには、それぞれ 1,200 秒の上限があります。長さや通信速度によって上限を超えた場合は失敗となり、動画の一部だけで成功扱いにはしません。

Cookie は runner の一時ファイルにのみ書き込みます。動画、サムネイル、メタデータ、Cookie、ダウンロード処理の生ログは artifact としてアップロードしません。GitHub に公開するのは、対象 URL や Cookie を含まない検証結果の概要だけです。概要をジョブの Summary に記載し、`live-verification-summary` artifact に 7 日間保存します。実行の成否にかかわらず後始末を実行し、削除対象が `RUNNER_TEMP` の専用サブフォルダー内であることを検査してから、Cookie、ツール、メディアと一時ファイルを削除します。

このテストが成功しても、すべてのクリエイター、投稿、Cookie 条件や API の構造が確認されたことにはなりません。[既知の仕様と未検証事項](KNOWN_UNVERIFIED.md) も参照してください。
