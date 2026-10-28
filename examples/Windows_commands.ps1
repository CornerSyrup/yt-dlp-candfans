# yt-dlp-candfans 使用範例目錄。所有指令皆為註解；執行或 dot-source 此檔不會連線或下載。
# 請挑選所需區塊，移除開頭 # 後在 yt-dlp.exe 所在目錄手動執行。
# 不會自動登入；cookies.txt 必須由你自行準備。不要分享真實 Cookie 或 JSON 日誌。
# yt-dlp-<site/function> 是常見命名慣例，非官方強制 ZIP 名稱；內部 namespace 與 IE 類名不變。
# 若已安裝舊名 candfans.zip，可自行選擇在同一資料夾更名為 yt-dlp-candfans.zip，勿安裝第二份。

# 1. 安裝：yt-dlp-candfans.zip 保持 ZIP，不解壓縮。
# New-Item -ItemType Directory -Force '.\yt-dlp-plugins' | Out-Null
# Copy-Item 'C:\請替換成實際路徑\yt-dlp-candfans.zip' '.\yt-dlp-plugins\yt-dlp-candfans.zip'
# .\yt-dlp.exe --ignore-config -v --list-extractors | Select-String 'CandFans|candfans'
# 注意：yt-dlp2026.08.19 在載入 plugin 前列出 extractors，所以此 listing 不含 plugin。
# 空結果不能判定安裝失敗。請在原始碼根目錄，以現有 Python 與 EXE 做離線 loader 驗證：
# python scripts/verify_windows.py `
#     --exe 'C:\請替換成實際路徑\yt-dlp.exe' `
#     --zip 'dist/yt-dlp-candfans.zip' --output '.test-tmp/windows'
# 不安裝套件；正式 ZIP 單獨配合本機 JSON 證明載入，再加入 test-only transport 測 mock CLI。
# 此腳本使用暫存 plugin 目錄，不修改既有安裝；輸出含 verification.json 與 stdout/stderr。

# 2. 手動 Netscape cookie jar：七欄以真正 Tab 分隔，名稱與屬性必須使用真實登入資料。
# # Netscape HTTP Cookie File
# .candfans.jp<TAB>TRUE<TAB>/<TAB>TRUE<TAB>0<TAB>YOUR_ACTUAL_COOKIE_NAME<TAB>YOUR_VALUE
# 此行中的 <TAB> 僅為說明，不是可直接使用的 Cookie。

# 3. 安全 metadata-only：不取 manifest，不輸出附件 URL；formats=[] 為預期行為。
# .\yt-dlp.exe --ignore-config `
#     --cookies '.\cookies.txt' `
#     --extractor-args 'candfanspost:metadata_only=true' `
#     --ignore-no-formats-error --skip-download --dump-json `
#     'https://candfans.jp/posts/comment/show/974904'

# 4. Profile 列舉：請替換 YOUR_CREATOR_CODE 與已查證的數字 YOUR_VERIFIED_USER_ID。
#    不加 user_id 可嘗試 lookup，但其真實 JSON 結構尚未驗證。
# .\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
#     --flat-playlist --dump-single-json `
#     --extractor-args 'candfansprofile:user_id=YOUR_VERIFIED_USER_ID' `
#     'https://candfans.jp/YOUR_CREATOR_CODE'

# 5. 一般 skip-download 仍可能請求 manifest；只有 API 明確允許時才列格式。
#    觀察資料與公開衍生 fixtures 的 is_downloadable=false，執行此例應被阻擋。
# .\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
#     --list-formats 'https://candfans.jp/posts/comment/show/974904'

# 6. 單篇下載：僅有合法下載許可且 API is_downloadable=true、can_browsing=1/true 時可用。
#    -N 8 為 concurrent fragments；-c 續傳；MP4 remux 需要 FFmpeg。
# .\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
#     -N 8 -c --download-archive '.\downloaded.txt' `
#     --remux-video mp4 --windows-filenames --trim-filenames 150 `
#     -o '.\downloads\%(uploader_id)s\%(id)s.%(ext)s' `
#     'https://candfans.jp/posts/comment/show/974904'

# 7. Profile 批次：每篇仍檢查許可；--ignore-errors 略過不可下載項，應閱讀略過原因。
# .\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
#     --extractor-args 'candfansprofile:user_id=YOUR_VERIFIED_USER_ID' `
#     -N 8 -c --download-archive '.\downloaded.txt' --ignore-errors `
#     --remux-video mp4 --windows-filenames --trim-filenames 150 `
#     -o '.\downloads\%(uploader_id)s\%(id)s.%(ext)s' `
#     'https://candfans.jp/YOUR_CREATOR_CODE'

# 8. 載入與內嵌封面：API 的絕對 HTTPS thumbnail_file 可直接使用。
#    使用者確認 974904 的 /user/1422016/post/974904/thumbnail.jpg 位於 https://video.candfans.jp。
#    相符 /user/<user_id>/post/<post_id>/thumbnail.jpg 預設使用該 origin，不需指定參數。
#    模式要求正整數 ID 與精確檔名，不核對其他 API 欄位的 ID。
#    此為使用者確認的單篇證據，非本工具 live 測試；其他貼文未逐篇驗證。
#    yt-dlp 原生 --embed-thumbnail 下載並內嵌，需要現有 FFmpeg；plugin 不會強制啟用。
#    觀察資料與公開衍生 fixtures 的 is_downloadable=false，仍會阻擋影片下載。
# .\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
#     -N 8 -c --download-archive '.\downloaded.txt' `
#     --embed-thumbnail --remux-video mp4 `
#     --windows-filenames --trim-filenames 150 `
#     -o '.\downloads\%(uploader_id)s\%(id)s.%(ext)s' `
#     'https://candfans.jp/posts/comment/show/974904'
#    其他來源或不符模式的相對路徑，可明確加上以下 override；必須替換成已查證的來源：
#    --extractor-args 'candfanspost:thumbnail_origin=https://YOUR_VERIFIED_THUMBNAIL_HOST'
#    只接受 HTTPS origin，不含 path/query/fragment/帳密；未提供可用來源時省略封面。
#    需轉 JPEG 可另加 --convert-thumbnails jpg。
#    metadata-only 可輸出解析後 URL，但下列指令不儲存影片或內嵌封面：
# .\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
#     --extractor-args 'candfanspost:metadata_only=true' `
#     --ignore-no-formats-error --skip-download --dump-json `
#     'https://candfans.jp/posts/comment/show/974904'

# 9. 另一個使用者層級安裝位置，擇一使用，避免重複安裝：
# New-Item -ItemType Directory -Force "$env:APPDATA\yt-dlp\plugins" | Out-Null
# Copy-Item 'C:\請替換成實際路徑\yt-dlp-candfans.zip' "$env:APPDATA\yt-dlp\plugins\yt-dlp-candfans.zip"

# 10. 原始碼根目錄：建立測試環境，離線 unit tests 與重建 ZIP。
# python -m venv .venv
# .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
# .\.venv\Scripts\python.exe -m unittest discover -s tests -v
# .\.venv\Scripts\python.exe scripts/build.py --output dist/yt-dlp-candfans.zip
