# yt-dlp-candfans の使用例です。すべてのコマンドはコメントです。このファイルを実行または dot-source しても通信やダウンロードは発生しません。
# 必要なブロックを選び、先頭の # を取り除いて、yt-dlp.exe のあるディレクトリーで手動実行してください。
# 自動ログインは行いません。API にログインが必要な場合は cookies.txt を用意し、Cookie が不要なら --cookies を省略してください。実際の Cookie や JSON ログを共有しないでください。
# yt-dlp-<site/function> は一般的な命名慣例であり、公式に必須とされる ZIP 名ではありません。内部の namespace と IE クラス名は変わりません。
# 旧名の candfans.zip をインストール済みの場合は、同じフォルダーで yt-dlp-candfans.zip に変更できます。重複してインストールしないでください。

# 1. インストール：yt-dlp-candfans.zip は展開せず、ZIP のまま配置します。
# New-Item -ItemType Directory -Force '.\yt-dlp-plugins' | Out-Null
# Copy-Item 'C:\実際のパスに置き換えてください\yt-dlp-candfans.zip' '.\yt-dlp-plugins\yt-dlp-candfans.zip'
# .\yt-dlp.exe --ignore-config -v --list-extractors | Select-String 'CandFans|candfans'
# 注意：yt-dlp 2026.08.19 は plugin の読み込み前に extractors を列挙するため、この一覧に plugin は含まれません。
# 結果が空でもインストール失敗とは判断できません。ソースのルートで、既存の Python と EXE によるオフライン loader 検証を実行してください。
# python scripts/verify_windows.py `
#     --exe 'C:\実際のパスに置き換えてください\yt-dlp.exe' `
#     --zip 'dist/yt-dlp-candfans.zip' --output '.test-tmp/windows'
# この検証スクリプトはパッケージをインストールしません。まず正式 ZIP とローカル JSON だけで読み込みを確認し、その後に test-only transport を追加して mock CLI を検証します。
# 一時的な plugin ディレクトリーを使用し、既存のインストールは変更しません。出力には verification.json と stdout/stderr が含まれます。

# 2. 手動の Netscape cookie jar：7 列を実際の Tab で区切り、名前と属性には実際のログイン情報を使用します。
# # Netscape HTTP Cookie File
# .candfans.jp<TAB>TRUE<TAB>/<TAB>TRUE<TAB>0<TAB>YOUR_ACTUAL_COOKIE_NAME<TAB>YOUR_VALUE
# 上記の <TAB> は説明用であり、そのまま使用できる Cookie ではありません。

# 3. metadata-only：manifest の取得や添付メディア URL の出力を行いません。formats=[] は想定どおりの結果です。
# .\yt-dlp.exe --ignore-config `
#     --cookies '.\cookies.txt' `
#     --extractor-args 'candfanspost:metadata_only=true' `
#     --ignore-no-formats-error --skip-download --dump-json `
#     'https://candfans.jp/posts/comment/show/974904'

# 4. Profile の列挙：YOUR_CREATOR_CODE と、確認済みの数値 YOUR_VERIFIED_USER_ID を置き換えてください。
#    user_id を省略すると lookup を試みますが、実際の JSON 構造は未検証です。
# .\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
#     --flat-playlist --dump-single-json `
#     --extractor-args 'candfansprofile:user_id=YOUR_VERIFIED_USER_ID' `
#     'https://candfans.jp/YOUR_CREATOR_CODE'

# 5. 通常の skip-download でも manifest を要求する場合があります。is_downloadable=false は解析を阻止しません。
#    API の添付情報と実際の HTTP/HLS 結果から形式を列挙し、このフィールドから失敗原因を推測しません。
# .\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
#     --list-formats 'https://candfans.jp/posts/comment/show/974904'

# 6. 単一投稿のダウンロード：ダウンロード権限のあるメディアに使用してください。現在は can_browsing=1/true を確認します。
#    attachments.default/low のみを処理します。/user/<id>/post/<id>/<filename>.m3u8 に一致するパスには、確認済みの origin を使用します。
#    origin https://video.candfans.jp は、投稿 974904 の例でユーザーが確認しています。ローカルでは API fixture の再生を通じて、単一投稿と個人ページの 9 投稿を CDN からダウンロード済みです。
#    添付情報が空でも contents_path1/sample/preview に切り替えません。is_downloadable による阻止は行いません。
#    -N 8 はセグメントの並列数、-c は再開です。MP4 への remux には FFmpeg が必要です。
# .\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
#     -N 8 -c --download-archive '.\downloaded.txt' `
#     --remux-video mp4 --windows-filenames --trim-filenames 150 `
#     -o '.\downloads\%(uploader_id)s\%(id)s.%(ext)s' `
#     'https://candfans.jp/posts/comment/show/974904'

# 7. Profile の一括ダウンロード：各投稿の can_browsing と実際の添付情報を確認します。--ignore-errors は失敗した項目をスキップするため、理由をログで確認してください。
# .\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
#     --extractor-args 'candfansprofile:user_id=YOUR_VERIFIED_USER_ID' `
#     -N 8 -c --download-archive '.\downloaded.txt' --ignore-errors `
#     --remux-video mp4 --windows-filenames --trim-filenames 150 `
#     -o '.\downloads\%(uploader_id)s\%(id)s.%(ext)s' `
#     'https://candfans.jp/YOUR_CREATOR_CODE'

# 8. サムネイルの取得と埋め込み：API の絶対 HTTPS thumbnail_file はそのまま使用できます。
#    ユーザーは、974904 の /user/1422016/post/974904/thumbnail.jpg が https://video.candfans.jp にあることを確認しています。
#    /user/<user_id>/post/<post_id>/thumbnail.jpg に一致するパスには、引数を指定せずにこの origin を使用します。
#    このパターンには正の整数 ID と正確なファイル名が必要です。他の API フィールドの ID との照合は行いません。
#    ローカルでは API fixture の再生により、単一投稿と個人ページの 9 投稿を CDN からダウンロード済みです。live API は未検証です。
#    yt-dlp 標準の --embed-thumbnail で取得・埋め込みを行います。既存の FFmpeg が必要です。plugin はこのオプションを自動で有効にしません。
#    is_downloadable=false は動画のダウンロードを阻止しません。サーバーエラーは実際の結果に従って報告します。
# .\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
#     -N 8 -c --download-archive '.\downloaded.txt' `
#     --embed-thumbnail --remux-video mp4 `
#     --windows-filenames --trim-filenames 150 `
#     -o '.\downloads\%(uploader_id)s\%(id)s.%(ext)s' `
#     'https://candfans.jp/posts/comment/show/974904'
#    別の origin やパターンに一致しない相対パスには、以下の override を明示できます。確認済みの origin に置き換えてください。
#    --extractor-args 'candfanspost:thumbnail_origin=https://YOUR_VERIFIED_THUMBNAIL_HOST'
#    path/query/fragment/認証情報を含まない HTTPS origin のみを受け付けます。使用可能な origin がなければサムネイルを省略します。
#    JPEG に変換する場合は --convert-thumbnails jpg を追加できます。
#    metadata-only でも解決後の URL は出力できますが、以下のコマンドは動画の保存やサムネイルの埋め込みを行いません。
# .\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
#     --extractor-args 'candfanspost:metadata_only=true' `
#     --ignore-no-formats-error --skip-download --dump-json `
#     'https://candfans.jp/posts/comment/show/974904'

# 9. 別のユーザー単位のインストール先です。いずれか一方を使い、重複インストールを避けてください。
# New-Item -ItemType Directory -Force "$env:APPDATA\yt-dlp\plugins" | Out-Null
# Copy-Item 'C:\実際のパスに置き換えてください\yt-dlp-candfans.zip' "$env:APPDATA\yt-dlp\plugins\yt-dlp-candfans.zip"

# 10. ソースのルートでテスト環境を作成し、オフライン unit tests と ZIP の再作成を行います。以下には依存パッケージのインストールが含まれます。
# python -m venv .venv
# .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
# .\.venv\Scripts\python.exe -m unittest discover -s tests -v
# .\.venv\Scripts\python.exe scripts/build.py --output dist/yt-dlp-candfans.zip
