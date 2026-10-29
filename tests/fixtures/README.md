# 公開 fixture の根拠と検証範囲

これらの JSON は、ユーザーから提供された技術引き継ぎ資料を公開用に匿名化・加工した **sanitised derivatives** です。オフラインテストに使用します。元の応答とバイト単位で同一ではなく、本プロジェクトによる live API の検証結果でもありません。元の引き継ぎ資料は公開 repository に含めていません。

- `timeline_page_sanitised.json` は、観測された 9 件のデータ構造、post ID、日時、duration、フィールドの型、permission flags を保持しています。
- `post_974904_sanitised.json` は、元の抜粋応答の `data.post` 構造と、テストに必要な post ID、日時、duration、permission flags を保持しています。
- クリエイターは `example_creator`／`100001` に置き換えています。投稿、クリエイター、カテゴリー、プランの文章は、中立的な Unicode テストデータです。メディアのファイル名と profile image のパスは合成値に変更し、絶対メディア URL には予約済みのテストドメイン `example.invalid` を使用しています。
- プラン ID、価格、プランの日付も合成値であり、実際の価格やプランの根拠にはなりません。実際のデータには追加または異なるフィールドが含まれる可能性があり、この fixture から未観測の schema を確定することはできません。
- `timeline_empty.json` と `auth_unauthenticated_minimal.json` は、個人情報を含まないページ終端／未ログイン応答の形だけを保持しています。未ログイン応答の実際の HTTP status は不明です。
- `fixture_inventory.json` の SHA256 は、**匿名化・加工済み timeline** に対応しています。元の応答との一致を示すものではありません。

1322820 について確認できているのは URL のみで、API 応答の fixture はありません。元のサンプルの `is_downloadable` はすべて false であり、公開データでも元の値を保持しています。ユーザーは同じ元の fixture を使って別のプログラムでメディアをダウンロードできたことを確認しているため、plugin はこのフィールドをダウンロードの阻止条件にしません。プラットフォーム上の完全な意味は不明です。

テスト内のフィールドの変化、user lookup、HTTP エラー、複数の添付ファイル、HLS manifests は、明示的な **合成（synthetic）** ケースです。user-by-code schema、Sanctum Cookie の詳細、flags の完全な意味は live 環境では未検証です。ユーザーは単一投稿の thumbnail と動画の origin が `https://video.candfans.jp` であることを確認しています。詳細は既知の根拠に関するドキュメントを参照してください。

テストでは mock 化していない network request を禁止しています。合成 HLS はメモリー内で解析し、セグメントのダウンロード、実際の Cookie の読み取り、有料コンテンツへのアクセスは行いません。このディレクトリーに Cookie、session、署名付きの本番メディア URL は含まれません。
