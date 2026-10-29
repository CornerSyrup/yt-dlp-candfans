# yt-dlp-candfans

[![CI](https://github.com/CornerSyrup/yt-dlp-candfans/actions/workflows/ci.yml/badge.svg)](https://github.com/CornerSyrup/yt-dlp-candfans/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/CornerSyrup/yt-dlp-candfans)](https://github.com/CornerSyrup/yt-dlp-candfans/releases/latest)
[![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

適用於官方 Windows `yt-dlp.exe` 的 CandFans Extractor Plugin，無須修改 yt-dlp 原始碼。支援個人頁 playlist、自動分頁、單篇貼文、手動 Netscape `cookies.txt`、metadata 及授權可下載的 HLS；封面內嵌、續傳與 download archive 使用 yt-dlp 原生功能。

**`is_downloadable` 不作為下載阻擋條件。** 使用者已確認原始 fixture 的 `is_downloadable=false` 仍可在其他程式下載相同媒體；plugin 保留回應原值，依 API 回傳的附件與實際 HTTP／HLS 結果處理，不推測此欄位代表拒絕下載。一般擷取仍要求 `can_browsing` 為數值 `1` 或布林 `true`；這是目前的瀏覽欄位檢查，不代表已確認網站完整權限模型。

## 安裝

從 [最新 Release 下載 yt-dlp-candfans.zip](https://github.com/CornerSyrup/yt-dlp-candfans/releases/latest/download/yt-dlp-candfans.zip)，**保持 ZIP 格式**，放進官方 `yt-dlp.exe` 旁的 `yt-dlp-plugins` 資料夾：

```text
MyDownloader/
  yt-dlp.exe
  cookies.txt                     # API 需要登入時自行提供
  yt-dlp-plugins/
    yt-dlp-candfans.zip
```

正式執行不需要安裝 Python 或本專案的測試依賴。Windows 使用者層級的另一個安裝位置為 `%APPDATA%\yt-dlp\plugins\yt-dlp-candfans.zip`，擇一使用。若已有舊名 `candfans.zip`，在原資料夾更名即可，避免留下兩份同名 extractor。

`yt-dlp-<site/function>` 是常見命名慣例，非官方強制的 ZIP 檔名規範。必要的內部結構是 `yt_dlp_plugins/extractor/candfans.py`；類別為 `CandFansPostIE`、`CandFansProfileIE`。

Release 同時提供 `SHA256SUMS.txt`；PowerShell 可用 `Get-FileHash .\yt-dlp-candfans.zip -Algorithm SHA256` 核對下載檔案。

## 手動 Cookie 與單篇 metadata

API 需要登入時，可提供合法工作階段的 Netscape/Mozilla `cookies.txt`；不需要 Cookie 的請求可省略指令中的 `--cookies`。使用者確認此次 fixture 對應的媒體下載不需要 Cookie，不能據此推論所有 API 或媒體皆不需驗證。Cookie 七欄使用真正 Tab 分隔；以下 `<TAB>` 僅為說明：

```text
# Netscape HTTP Cookie File
.candfans.jp<TAB>TRUE<TAB>/<TAB>TRUE<TAB>0<TAB>YOUR_ACTUAL_COOKIE_NAME<TAB>YOUR_VALUE
```

保留實際 Cookie 的 domain、path、secure、expiry、name 與 value；plugin 不會猜測 Laravel Sanctum cookie 名稱、自動登入或開啟瀏覽器。不要提交 Cookie，也不要公開可能包含簽名媒體 URL 或私人資料的 yt-dlp verbose／JSON 輸出。

在 `yt-dlp.exe` 所在資料夾執行：

```powershell
.\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
    --extractor-args 'candfanspost:metadata_only=true' `
    --ignore-no-formats-error --skip-download --dump-json `
    'https://candfans.jp/posts/comment/show/974904'
```

`metadata_only` 不請求 HLS manifest，也不輸出附件媒體 URL，回傳 `formats=[]`，因此需配合 `--ignore-no-formats-error`。一般的 `--skip-download` 仍可能解析 manifest。此例的 `974904` 有使用者提供的回應節錄；`1322820` 只有 URL，沒有其 API 回應或成功擷取證據。

影片來源只讀 API `attachments[].default`／`low` 中的主影片 M3U8。使用者已確認 `974904` 的影片與圖片皆使用 `https://video.candfans.jp`，且影片相對路徑對應 `/user/<user_id>/post/<post_id>/<filename>.m3u8`。因此，符合已知模式的附件相對路徑可接到此 origin；要求根目錄相對路徑、正整數 ID、單一非空檔名及小寫 `.m3u8`，保留 query。完整 HTTPS 附件 URL 照原值處理。此 origin 最初由使用者確認；本機另以原始 API fixture 回放，對單篇與九篇個人頁項目完成真實 CDN 下載。這不代表 live API 或所有貼文已驗證。空附件不會改讀 `contents_path1`、`sample_file` 或 preview，`is_downloadable=false` 不會阻擋附件解析。

## 個人頁與批次下載

請把 `YOUR_CREATOR_CODE` 換成實際創作者代碼：

```powershell
.\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
    --flat-playlist --dump-single-json `
    'https://candfans.jp/YOUR_CREATOR_CODE'
```

user-by-code endpoint 已知，真實 JSON 結構仍未知。Plugin 只有在同一 record 中找到精確的 `user_code` 與唯一數字 `user_id` 時才接受；否則請提供自行查證的 ID：`--extractor-args 'candfansprofile:user_id=YOUR_VERIFIED_USER_ID'`。佔位值必須替換成數字，公開 fixtures 的匿名 ID 不能當作真實查詢值。

timeline 使用已知的 `post_type[]=1`，按需要請求 `page=1,2,...`，直到 `data=[]`。playlist 只產生貼文 URL，實際處理各篇時才檢查 `can_browsing` 並解析附件。重複 ID 去重；整頁沒有新 ID 時會 warning 並停止，避免無限迴圈，這不代表正常抵達最後一頁。

對你有權下載的單篇，可使用：

```powershell
.\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
    -N 8 -c --download-archive '.\downloaded.txt' `
    --remux-video mp4 --windows-filenames --trim-filenames 150 `
    -o '.\downloads\%(uploader_id)s\%(id)s.%(ext)s' `
    'https://candfans.jp/posts/comment/show/974904'
```

批次下載時把最後的 URL 換成個人頁，可加 `--ignore-errors` 略過不可下載項，並檢查略過原因。`-N 8` 為 HLS concurrent fragments，`-c` 續傳；MP4 remux 需要 FFmpeg。原始觀察中 `974904` 的 `is_downloadable=false` 不會觸發本 plugin 的阻擋；是否能取得媒體，以該次實際伺服器回應為準。

多附件 ID 取自媒體 origin 與 path，忽略簽名 query。附件排序與 token 輪替不影響 ID，但媒體主機／路徑、可用版本或單／多附件數量改變時可能改變。部分附件失敗會 warning 並保留其他可用附件；不代表整篇已完整下載。

## 封面載入與內嵌

API 提供有效絕對 HTTPS `thumbnail_file` 時可直接使用。使用者已確認貼文 `974904` 的圖片為 `https://video.candfans.jp/user/1422016/post/974904/thumbnail.jpg`，與該篇 API 的相對路徑相符。因此，相符的 `/user/<user_id>/post/<post_id>/thumbnail.jpg` 路徑預設使用 `https://video.candfans.jp`，一般指令不再需要指定主機：

```powershell
.\yt-dlp.exe --ignore-config --cookies '.\cookies.txt' `
    -N 8 -c --embed-thumbnail --remux-video mp4 `
    'https://candfans.jp/posts/comment/show/974904'
```

`--embed-thumbnail` 使用 yt-dlp 原生 EmbedThumbnail postprocessor，依容器使用 Mutagen／FFmpeg 等；plugin 提供 URL，不會強制啟用內嵌。必要時可加 `--convert-thumbnails jpg`。封面來源設定只處理圖片 URL。

這項主機最初由使用者確認 `974904` 範例；本機驗證另已實際下載該篇與個人頁九篇的 CDN 封面及影片，API 使用原始 fixture 回放。這不表示 live API 或所有貼文已驗證。預設模式只接受根目錄相對路徑、正整數 ID 與精確的 `thumbnail.jpg` 檔名；不會核對路徑 ID 與其他 API 欄位是否相同。其他主機或不符合此模式的相對路徑，仍須自行查證，並可選擇加 `--extractor-args 'candfanspost:thumbnail_origin=https://YOUR_VERIFIED_THUMBNAIL_HOST'`。此 override 只接受 HTTPS origin，不接受 path、query、fragment 或帳密；不符合已知模式且未指定 origin 時省略封面。API 已提供的絕對 HTTPS URL 優先使用，明確指定的 origin 則覆寫安全相對路徑的預設來源；extractor 本身不會請求圖片。

只查解析後 URL 時，使用前述 metadata-only 指令即可；會輸出 thumbnail URL，但不儲存影片或內嵌封面。更多手動指令見 [Windows_commands.ps1](examples/Windows_commands.ps1)，整份範例皆為註解。

## 開發與測試

Python 3.10+；開發環境安裝測試依賴後，unit tests 完全離線：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/build.py --output dist/yt-dlp-candfans.zip
```

61 個離線測試涵蓋 URL matching、九筆 timeline 與空頁、lazy pagination、權限、API 錯誤、多附件、Cookie scope、metadata、時區與 thumbnail。公開 fixtures 為**經去識別與內容替換的衍生資料**：保留觀察到的 JSON 結構、貼文 ID、時間／duration 與 false 旗標；創作者、文字與媒體網址已換成中性範例。它們不是原始回應的逐位元組副本，也不是 live API 驗證結果，詳見 [fixture 說明](tests/fixtures/README.md)。

使用既有的官方 Windows EXE 做離線 ZIP discovery 與 CLI mock：

```powershell
python scripts/verify_windows.py --exe 'C:\Tools\yt-dlp.exe' `
    --zip dist/yt-dlp-candfans.zip --output .test-tmp/windows
python scripts/verify_thumbnail.py --exe 'C:\Tools\yt-dlp.exe' `
    --zip dist/yt-dlp-candfans.zip --output .test-tmp/thumbnail
```

第二個腳本另需既有 FFmpeg／ffprobe。它產生一秒純色 HLS 影片與 JPEG，實際內嵌封面，以 ffprobe 檢查 `attached_pic` 並比較抽出圖片的 SHA256。這些測試使用 test-only transport 攔截請求；正式 plugin ZIP 不含 transport、fixtures 或測試依賴。這兩個公開腳本證明工具鏈與 mock 行為，與下述真實媒體驗證分開。

另一次本機整合驗證使用官方 Windows `yt-dlp.exe 2026.10.26`，僅攔截 API 請求並回放原始 fixture，保留 `is_downloadable=false`，不提供 Cookie；HLS manifest、片段及封面全部連到真實 CDN。單篇 `974904` 與個人頁九篇均完成下載，兩次指令 exit code 均為 0。`974904` 的輸出為 1947.199667 秒，含 H.264、AAC 及 PNG 封面（`attached_pic=1`），全片 FFmpeg 解碼 exit code 為 0。個人頁九篇也全部通過完整解碼；共十支影片均有音訊與內嵌封面，十張封面也全部解碼成功。總長度為 12008.93 秒，與各 fixture 的最大長度差為 0.200 秒；這次結果不驗證 live API、lookup 或實際 API 分頁。原始私人 fixture、媒體及日誌不放入公開 repository 或 CI。

`--list-extractors` 在部分已驗證的 yt-dlp 版本會先於 plugin 載入而執行，不能單靠 listing 判斷 ZIP 是否可用。`verify_windows.py` 先單獨載入正式 ZIP，以本機 JSON 與 verbose loader 訊息驗證兩個 IE，再加入 fixture transport 測 CLI。

## CI 與 Release

[GitHub Actions CI](https://github.com/CornerSyrup/yt-dlp-candfans/actions/workflows/ci.yml) 在 Ubuntu／Windows、Python 3.12／3.13 執行 61 項離線測試與打包驗證；另以官方 Windows EXE 驗證 ZIP 載入、metadata、分頁及 synthetic HLS CLI，不需要 CandFans Cookie。實際封面內嵌可另用上方的本機整合腳本驗證。

維護者在 CI 通過後建立 `v*` tag（首版 `v0.1.0`）：Release workflow 會再次驗證並發佈 `yt-dlp-candfans.zip` 與 `SHA256SUMS.txt`。從 tag 對應的 commit 建置，不把 secrets、原始私人 fixtures 或生成媒體加入 release：

```powershell
# 維護者確認 CI 通過、版本與 release 內容後執行
git tag v0.1.0
git push origin v0.1.0
```

## 已知限制與回報問題

user-by-code 真實結構、其他圖片／影片來源、Laravel Sanctum Cookie／CSRF 細節、`is_downloadable` 語意及 `post_date` 真實時區均尚未確認；無時區日期暫按 JST UTC+09:00 換算，`upload_date` 為 UTC 日期。已知模式的圖片與附件相對路徑來源依上述使用者確認的單篇範例建立，本機真實 CDN 驗證範圍為單篇 `974904` 與 fixture 中九篇個人頁項目；API 仍為 fixture 回放。詳細界線見 [KNOWN_UNVERIFIED.md](docs/KNOWN_UNVERIFIED.md)。

`ERROR_UNAUTHENTICATED` 或 HTTP 401 只代表該次請求未通過驗證。空附件、未通過的 `can_browsing` 檢查或未知 schema 不會轉用 `contents_path1`、sample／preview 或繞過存取限制。HLS 失敗訊息記錄實際 HTTP status、無格式或 DRM 標記；不從 `is_downloadable` 推測失敗原因。Plugin 不例行取得帳號資料、不處理 DRM 繞過。回報問題時提供版本、已移除秘密的最小 JSON 與重現步驟；不要附真實 Cookie、簽名媒體 URL、付費內容或 backend trace。

## 作者、協作與授權

專案作者與維護者：**CornerSyrup（Klein）**。OpenAI Codex 協助實作與整理 extractors、API 欄位檢查與錯誤處理、lazy pagination、手動 Cookie 支援、metadata／thumbnail 選項、61 個離線測試、synthetic 封面內嵌與官方 Windows EXE 驗證、CI/CD、打包及文件。需求、授權判斷與後續維護決策由作者負責。

本專案採 [MIT License](LICENSE)，保留既有 `Copyright (c) 2026 Klein`。貢獻前請先提出最小重現或測試案例；修改 API contract 時附去識別證據，並保留離線測試及不繞過存取限制的行為。

官方參考：[Plugin 安裝](https://github.com/yt-dlp/yt-dlp#plugins)、[Plugin Development](https://github.com/yt-dlp/yt-dlp/wiki/Plugin-Development)、[手動 Cookie FAQ](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)。
