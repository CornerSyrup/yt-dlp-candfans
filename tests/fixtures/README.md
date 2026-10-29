# 公開 fixture 的證據範圍

這些 JSON 是使用者技術交接資料的 **sanitised derivatives**，供公開離線測試使用；它們不是原始回應的逐位元組副本，也不是本專案的 live API 驗證結果。原始交接內容未放入公開 repository。

- `timeline_page_sanitised.json` 保留所觀察的九筆資料結構、post ID、日期、duration、欄位型別及 permission flags。
- `post_974904_sanitised.json` 保留原先節錄回應的 `data.post` 結構與測試所需 post ID、時間、duration 及 permission flags。
- 創作者改為 `example_creator`／`100001`；貼文、創作者、分類、方案文字改為中性的 Unicode 測試資料。媒體檔名及 profile image 路徑改為合成值；所有絕對媒體網址使用保留測試網域 `example.invalid`。
- 方案識別碼、價格與方案日期亦為合成值，不能當作真實售價或方案證據。真實資料仍可能含額外或不同欄位；未觀察的 schema 不因此成立。
- `timeline_empty.json`、`auth_unauthenticated_minimal.json` 僅保留無個資的終止／未登入形狀。未登入回應的真實 HTTP status 未知。
- `fixture_inventory.json` 的 SHA256 對應 **sanitised timeline**，不能用來聲稱與原始回應相同。

1322820 只有 URL 證據，沒有 API 回應 fixture。原始樣本的 `is_downloadable` 均為 false，公開資料保留原值。使用者確認相同原始 fixture 已在其他程式下載媒體，此欄位不作為 plugin 下載阻擋條件；完整平台語意仍未知。

測試程式中欄位變體、user lookup、HTTP 錯誤、多附件與 HLS manifests 均為明確的 **synthetic** 案例。user-by-code schema、Sanctum Cookie 細節及 flags 的完整平台語意仍未經 live 驗證；使用者已確認單篇 thumbnail 與影片的 `https://video.candfans.jp` origin，詳見已知證據文件。

測試嚴禁未 mock 的 network request；合成 HLS 在記憶體中解析，不下載片段，不讀取真實 Cookie，也不接觸付費內容。此目錄不包含 Cookie、session 或 signed production media URL。
