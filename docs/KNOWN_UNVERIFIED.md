# 已知證據與未驗證事項

公開 fixtures 是使用者提供資料的去識別衍生版本，保留解析所需結構與部分值，並替換創作者、文字及媒體網址。它們不是原始回應的逐位元組副本；測試中的下載許可、lookup schema、絕對 thumbnail 與錯誤案例另有明確 synthetic 標記。詳見 [fixture 說明](../tests/fixtures/README.md)。

| 項目 | 已知證據 | 實作與驗證界線 |
|---|---|---|
| 貼文 `1322820` | 只有 webpage URL | 只有 URL matching 測試；沒有該篇 API 回應或成功擷取證據。 |
| 貼文 `974904` | 使用者提供的回應節錄位於 `data.post` | 公開為 `post_974904_sanitised.json`，可離線驗證解析，不是完整或 live 回應。 |
| timeline | 觀察資料為九筆，終止形狀是 `data: []` | 公開為 `timeline_page_sanitised.json`。九筆不是固定 page size 的 contract；多頁、重複頁與 malformed cases 另以 synthetic 測試。 |
| 創作者 ID | 公開 fixtures 的 `example_creator`／`100001` 為匿名替代值 | 不能拿來查詢 live API；使用者必須自行查證實際 `user_code` 與 `user_id`。 |
| user-by-code | GET endpoint 已知，真實 JSON body 未提供 | 同一 record 中精確 `user_code`＋唯一數字 `user_id` 的 defensive parsing 僅 synthetic；可手動提供已查證 ID。 |
| `is_downloadable=false` | 原始觀察中 timeline 與單篇均為 false，同時有瀏覽旗標與 HLS URL | 網站精確語意未知。保守阻擋 HLS 擷取與下載，沒有 override；metadata-only 僅讀 API 授權回傳欄位。 |
| 許可下載分支 | 未提供真實 `is_downloadable=true` 回應 | 只有 synthetic 測試；API true 不取代使用者必須具有的合法下載許可。 |
| `can_browsing` | 原觀察為數值 1 | 下載只接受數值 1 或布林 true，其餘拒絕，不推測其他 enum。 |
| thumbnail | 使用者確認 `974904` 圖片為 `https://video.candfans.jp/user/1422016/post/974904/thumbnail.jpg`，與其 API 相對路徑相符 | 相符的 `/user/<user_id>/post/<post_id>/thumbnail.jpg` 預設接到該 HTTPS origin。這是使用者確認的單篇證據，不是本工具 live 驗證，也不證明所有貼文／主機。API 絕對 HTTPS URL 可接受；其他相對路徑／主機可由使用者提供已查證 `thumbnail_origin`，不接受 path/query/fragment/帳密。 |
| `post_date` | 無時區字串，網站日本情境 | 暫依 JST UTC+09:00 換算，仍待 API 確認；`upload_date` 使用 UTC 日期，可能與日本日期相差一天。 |
| duration／多附件 | `movie_time`、`attachment_length` 與部分 `post_attachments[].length` | 依可唯一識別的路徑對應，不依陣列位置猜測；完整穩定附件 contract 未建立。媒體 origin/path 改變可能影響 archive ID。 |
| Laravel Sanctum | 使用者登入失敗 trace 曾提到該 middleware | 不證明特定 Cookie、CSRF 或 header 需求。只使用 yt-dlp cookie jar，不猜名稱、自動登入或例行取得帳號資料。 |
| 未登入回應 | `ERROR_UNAUTHENTICATED` 節錄與空附件觀察 | 真實 HTTP status 未提供；401/403 等以 synthetic 測試。不能推論瀏覽器全域登入狀態。 |
| HLS | 使用者確認 `974904` 的主影片位於 `https://video.candfans.jp`，對應 `/user/<user_id>/post/<post_id>/<filename>.m3u8`；同篇圖片亦使用此 origin | 只解析 API `attachments[].default`／`low` 的完整 HTTPS URL 或符合已知模式的根目錄相對路徑，不從 `contents_path1`／sample／preview 補來源。下載旗標規則不變。這是使用者確認的單篇證據，不是本工具 live 驗證；其他主機、Cookie、referer 與有效期未確認。公開媒體網址已替換為 `.invalid`，manifest parsing 與許可分支採離線 mock。 |
| 封面內嵌／MP4 | 原生 yt-dlp postprocessor 與 FFmpeg 工具鏈 | 用本地 synthetic HLS／JPEG 實際內嵌並檢查 attached_pic 與圖片 SHA256；不代表已成功下載 CandFans 封面或媒體。metadata-only 不儲存影片或內嵌。 |
| Windows ZIP loader | 官方 EXE 搭配本機 JSON 檢查正式 ZIP 的兩個 IE，再做 fixture CLI mock | 部分版本的 `--list-extractors` 先於 plugin 載入，listing 不含 plugin 不代表載入失敗。測試工具不包含在正式 ZIP。 |
| live 驗收 | 本工具沒有成功的真實 Cookie、已登入 API 或實際下載驗證；使用者另確認上述單篇圖片與主影片 URL | 在授權環境驗證 lookup、跨頁、其他單篇／主機、旗標、時區與媒體；使用者提供的 URL 證據與本工具 mock 結果分開記錄。CI 不接觸 CandFans 或私人工作階段。 |

公開回報只提交最小、去識別的 JSON 與版本資訊。新增 API 證據時同步更新 fixture 與測試，不能把 synthetic 許可或網址當成已驗證 contract；勿提交真實 Cookie、帳號資料、簽名 URL、付費內容或 backend trace。
