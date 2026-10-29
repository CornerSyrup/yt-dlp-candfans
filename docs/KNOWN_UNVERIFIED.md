# 已知證據與未驗證事項

公開 fixtures 是使用者提供資料的去識別衍生版本，保留解析所需結構與部分值，並替換創作者、文字及媒體網址。它們不是原始回應的逐位元組副本；測試中的欄位變體、lookup schema、絕對 thumbnail 與錯誤案例另有明確 synthetic 標記。詳見 [fixture 說明](../tests/fixtures/README.md)。

| 項目 | 已知證據 | 實作與驗證界線 |
|---|---|---|
| 貼文 `1322820` | 只有 webpage URL | 只有 URL matching 測試；沒有該篇 API 回應或成功擷取證據。 |
| 貼文 `974904` | 使用者提供的回應節錄位於 `data.post` | 公開為 `post_974904_sanitised.json`，可離線驗證解析，不是完整或 live 回應。 |
| timeline | 觀察資料為九筆，終止形狀是 `data: []` | 公開為 `timeline_page_sanitised.json`。九筆不是固定 page size 的 contract；多頁、重複頁與 malformed cases 另以 synthetic 測試。 |
| 創作者 ID | 公開 fixtures 的 `example_creator`／`100001` 為匿名替代值 | 不能拿來查詢 live API；使用者必須自行查證實際 `user_code` 與 `user_id`。 |
| user-by-code | GET endpoint 已知，真實 JSON body 未提供 | 同一 record 中精確 `user_code`＋唯一數字 `user_id` 的 defensive parsing 僅 synthetic；可手動提供已查證 ID。 |
| `is_downloadable=false` | 原始觀察中 timeline 與單篇均為 false，同時有瀏覽旗標與 HLS URL；使用者確認同一 fixture 已在其他程式成功下載媒體，且此欄位不影響該下載行為 | 不作為下載阻擋條件，不改寫 fixture 值。網站完整欄位語意仍未知；不從 false 推測存取或失敗原因。 |
| 實際媒體存取 | 使用者確認此次 fixture 的 CDN 媒體無需 Cookie | 依附件 URL 的實際 HTTP／HLS 結果判斷，不能延伸成所有 API／媒體均不需驗證。失敗只報實際 HTTP status、無格式或 DRM 標記，不猜原因。 |
| `can_browsing` | 原觀察為數值 1 | 目前一般擷取只接受數值 1 或布林 true，其餘回報該欄位未授予；不推測其他 enum 或網站完整權限模型。 |
| thumbnail | 使用者確認 `974904` 圖片為 `https://video.candfans.jp/user/1422016/post/974904/thumbnail.jpg`，與其 API 相對路徑相符 | 相符的 `/user/<user_id>/post/<post_id>/thumbnail.jpg` 預設接到該 HTTPS origin。此 origin 最初由使用者確認單篇證據，本機另已下載單篇與九篇個人頁項目的真實 CDN 封面；不證明所有貼文／主機或 live API。API 絕對 HTTPS URL 可接受；其他相對路徑／主機可由使用者提供已查證 `thumbnail_origin`，不接受 path/query/fragment/帳密。 |
| `post_date` | 無時區字串，網站日本情境 | 暫依 JST UTC+09:00 換算，仍待 API 確認；`upload_date` 使用 UTC 日期，可能與日本日期相差一天。 |
| duration／多附件 | `movie_time`、`attachment_length` 與部分 `post_attachments[].length` | 依可唯一識別的路徑對應，不依陣列位置猜測；完整穩定附件 contract 未建立。媒體 origin/path 改變可能影響 archive ID。 |
| Laravel Sanctum | 使用者登入失敗 trace 曾提到該 middleware | 不證明特定 Cookie、CSRF 或 header 需求。只使用 yt-dlp cookie jar，不猜名稱、自動登入或例行取得帳號資料。 |
| 未登入回應 | `ERROR_UNAUTHENTICATED` 節錄與空附件觀察 | 真實 HTTP status 未提供；401/403 等以 synthetic 測試。不能推論瀏覽器全域登入狀態。 |
| HLS | 使用者確認 `974904` 的主影片位於 `https://video.candfans.jp`，對應 `/user/<user_id>/post/<post_id>/<filename>.m3u8`；同篇圖片亦使用此 origin | 只解析 API `attachments[].default`／`low` 的完整 HTTPS URL 或符合已知模式的根目錄相對路徑，不從 `contents_path1`／sample／preview 補來源。不依 `is_downloadable` 阻擋。此 origin 最初由使用者確認單篇證據；本機以原始 API fixture 回放完成單篇與九篇個人頁項目的真實 CDN 下載，不提供 Cookie。其他主機、一般 Cookie／referer 需求與有效期未確認。公開媒體網址已替換為 `.invalid`，manifest parsing 與欄位變體採離線 mock。 |
| 封面內嵌／MP4 | 原生 yt-dlp postprocessor 與 FFmpeg 工具鏈 | 公開整合腳本用本地 synthetic HLS／JPEG 內嵌並檢查 attached_pic 與圖片 SHA256。另一次真實 CDN 驗證中，974904 為 1947.199667 秒、H.264／AAC 加 PNG attached_pic=1，全片 FFmpeg 解碼 exit code 0。九篇個人頁影片也全部完整解碼成功；十支影片的音訊與內嵌封面均存在，十張封面亦全部解碼成功。metadata-only 不儲存影片或內嵌。 |
| Windows ZIP loader | 官方 EXE 搭配本機 JSON 檢查正式 ZIP 的兩個 IE，再做 fixture CLI mock | 部分版本的 `--list-extractors` 先於 plugin 載入，listing 不含 plugin 不代表載入失敗。測試工具不包含在正式 ZIP。 |
| 本機混合整合驗證 | 官方 Windows yt-dlp.exe 2026.10.26，API 回放原始 fixture，無 Cookie；HLS、片段與圖片使用真實 CDN。單篇 974904 與個人頁九篇完成下載，兩次指令 exit code 0 | 十支影片及十張內嵌封面均完整解碼 exit code 0；總長度 12008.93 秒，各檔與 fixture 的最大長度差為 0.200 秒。個人頁各篇 API 以原始 timeline record 包入已知 data.post envelope，不宣稱是各篇獨立 API 原始回應。不驗證 live API、lookup、實際 API 跨頁、時區或所有主機；CI 保持完全 mock，不接觸私人工作階段。 |

公開回報只提交最小、去識別的 JSON 與版本資訊。新增 API 證據時同步更新 fixture 與測試，不能把 synthetic 欄位或網址當成已驗證 contract；勿提交真實 Cookie、帳號資料、簽名 URL、付費內容或 backend trace。
