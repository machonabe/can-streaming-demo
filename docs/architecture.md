# Genspark プロンプト: Honda CAN Streaming Demo アーキテクチャ解説資料

以下のプロンプトをGensparkに貼り付けて、お客様向けの技術資料を生成してください。

---

## プロンプト

```
あなたはDatabricksのSolutions Architectです。自動車OEM / Tier1サプライヤー向けに、車両CANバスデータのリアルタイムストリーミング処理アーキテクチャを提案する資料を作成してください。

# 背景

自動車業界ではCAN (Controller Area Network) バスから取得される車両テレマティクスデータのリアルタイム処理ニーズが急速に高まっています。具体的なユースケースとして：
- リアルタイム車両ヘルスモニタリング
- 予知保全 (Predictive Maintenance)
- 走行パターン分析・運転行動スコアリング
- フリート管理・燃費最適化
- ADAS / 自動運転向けデータパイプライン

今回、以下の2つのアーキテクチャパターンを実際に構築・検証しました。お客様がレイテンシー要件と運用負荷に応じて適切なアーキテクチャを選択できるよう、比較資料を作成してください。

---

# アーキテクチャ図の作成（2パターン）

## パターン1: RisingWave + Databricks（超低レイテンシー構成）

以下のMermaid記法でアーキテクチャ図を作成してください：

"""mermaid
flowchart LR
    subgraph Vehicle["車両 / Edge"]
        ECU["ECU<br/>CAN Bus"]
        GW["テレマティクス<br/>Gateway"]
    end

    subgraph AWS_Ingest["AWS - Ingestion"]
        KDS["Amazon Kinesis<br/>Data Streams"]
    end

    subgraph AWS_Stream["AWS - Stream Processing (EC2)"]
        RW["RisingWave<br/>(Streaming DB)"]
        RW_SRC["Source:<br/>kinesis_can_source"]
        RW_MV1["MV: can_frames_decoded<br/>(CAN Binary Decode)"]
        RW_MV2["MV: vehicle_summary_1min<br/>(1分集計)"]
        RW_SINK["Iceberg Sink<br/>(append-only)"]
    end

    subgraph AWS_Storage["AWS - Storage"]
        S3["Amazon S3<br/>Apache Iceberg<br/>(Parquet + Metadata)"]
    end

    subgraph Databricks["Databricks Lakehouse"]
        UC["Unity Catalog<br/>(External Table)"]
        SQL["SQL Warehouse /<br/>Notebooks"]
        DASH["ダッシュボード<br/>& AI/ML"]
    end

    ECU -->|CAN frames| GW
    GW -->|20-byte binary| KDS
    KDS --> RW_SRC
    RW_SRC --> RW
    RW --> RW_MV1
    RW_MV1 --> RW_MV2
    RW_MV1 --> RW_SINK
    RW_MV2 --> RW_SINK
    RW_SINK -->|VPCE経由| S3
    S3 --> UC
    UC --> SQL
    SQL --> DASH

    style RW fill:#4B0082,color:#fff
    style S3 fill:#FF9900,color:#000
    style UC fill:#FF3621,color:#fff
"""

## パターン2: Databricks SDP のみ（フルマネージド構成）

"""mermaid
flowchart LR
    subgraph Vehicle["車両 / Edge"]
        ECU["ECU<br/>CAN Bus"]
        GW["テレマティクス<br/>Gateway"]
    end

    subgraph AWS_Ingest["AWS - Ingestion"]
        KDS["Amazon Kinesis<br/>Data Streams"]
    end

    subgraph Databricks["Databricks Lakehouse"]
        AL["Auto Loader /<br/>Structured Streaming"]
        DLT["Delta Live Tables<br/>(ETL Pipeline)"]
        BRONZE["Bronze: raw_can_frames<br/>(生バイナリ)"]
        SILVER["Silver: can_frames_decoded<br/>(デコード済み)"]
        GOLD["Gold: vehicle_summary<br/>(集計・Feature)"]
        UC["Unity Catalog"]
        SQL["SQL Warehouse /<br/>Notebooks"]
        DASH["ダッシュボード<br/>& AI/ML"]
    end

    ECU -->|CAN frames| GW
    GW -->|20-byte binary| KDS
    KDS --> AL
    AL --> DLT
    DLT --> BRONZE
    BRONZE --> SILVER
    SILVER --> GOLD
    BRONZE --> UC
    SILVER --> UC
    GOLD --> UC
    UC --> SQL
    SQL --> DASH

    style DLT fill:#FF3621,color:#fff
    style UC fill:#FF3621,color:#fff
    style AL fill:#FF3621,color:#fff
"""

---

# 各構成の詳細比較

以下の観点で比較表を作成してください。

## パターン1: RisingWave + Databricks

### 構成概要
- Amazon Kinesis Data Streams → RisingWave (EC2上、Docker) → Apache Iceberg (S3) → Databricks Unity Catalog
- RisingWaveはPostgreSQL互換のストリーミングデータベース（OSS）
- Materialized View（増分計算）によりリアルタイムにCANフレームをデコード・集計
- Iceberg Sink で Parquet + メタデータを S3 に永続化
- Databricks は Iceberg テーブルを External Table として参照

### メリット
- **超低レイテンシー**: RisingWaveのMVはミリ秒〜秒単位で増分更新される。Kinesis到着からMV反映まで数百ms
- **SQL のみでストリーム処理を定義**: `CREATE MATERIALIZED VIEW` だけでストリーミングETLを構築可能。Spark/Flinkの知識不要
- **バイナリデコードをストリーム内で完結**: `get_byte()` 関数でCAN Bus 20バイトフレームをリアルタイムに解析
- **TUMBLE Window集計**: 1分/5分/1時間などの時間ウィンドウ集計をSQLで宣言的に定義
- **Iceberg Sink による標準フォーマット出力**: DatabricksだけでなくAthena, Snowflake, Trino等でも読み取り可能
- **Databricks側はクエリ・分析に専念**: ストリーム処理のインフラ管理とDatabricksの分析基盤を分離

### デメリット
- **EC2インスタンスの運用負荷**: RisingWaveのDockerコンテナの監視、再起動、スケーリングを自前で管理
- **追加インフラコスト**: EC2, EBS, ネットワーク、VPCエンドポイントのコスト
- **障害対応が複雑**: RisingWave障害時のリカバリ、Kinesis offset管理、Iceberg commit の整合性を運用チームが担保
- **セキュリティ管理**: IAMロール、SG、SCP (Service Control Policy)、VPCエンドポイント等の設計が必要
- **スケーリングの限界**: EC2単体のRisingWave playgroundはスケールアウトが難しい（本番ではK8sクラスタが必要）

### 最適なユースケース
- **サブ秒レイテンシーが要件**: リアルタイム異常検知、ADAS制御フィードバック
- **既にRisingWave / Kafkaエコシステムがある環境**
- **Icebergフォーマットでのマルチエンジン共有が必要**

---

## パターン2: Databricks SDP（Structured Streaming + Delta Live Tables）のみ

### 構成概要
- Amazon Kinesis Data Streams → Databricks Auto Loader (Structured Streaming) → Delta Live Tables → Unity Catalog
- Bronze/Silver/Gold のメダリオンアーキテクチャ
- CAN バイナリデコードを PySpark UDF または SQL 式で実装
- 全てサーバーレスで実行可能（Serverless DLT Pipeline）
- ガバナンス・リネージ・データ品質チェックが組み込み

### メリット
- **完全マネージド / サーバーレス**: EC2やDockerの管理不要。DLTパイプラインはDatabricksが自動スケーリング・障害回復
- **ゼロ運用負荷**: インフラ管理、パッチ適用、スケーリング全てDatabricks側が担当
- **統合ガバナンス**: Unity Catalog によるアクセス制御、データリネージ、監査ログが自動適用
- **データ品質 (Expectations)**: DLT の `CONSTRAINT` 句でデータ品質ルールをパイプライン内に宣言的に定義
- **コスト効率**: 処理量に応じた従量課金。アイドル時はゼロコスト（サーバーレス）
- **AI/ML との統合**: Feature Store, MLflow, Model Serving と同一プラットフォーム上でシームレスに連携
- **メダリオンアーキテクチャ**: Bronze → Silver → Gold の段階的データ品質向上がフレームワークとして組み込み

### デメリット
- **レイテンシー**: Structured Streaming のマイクロバッチは通常 数秒〜数十秒。RisingWaveのMVほどの低レイテンシーは達成が難しい
  - ただし、Continuous Processing モードで約100msまで低減可能（experimentalだがユースケース次第で十分）
- **Icebergフォーマット非対応（直接Sink）**: DLTの出力はDelta形式。Icebergでの出力が必要な場合はUniForm (Delta Universal Format) を利用

### 最適なユースケース
- **レイテンシー要件が数秒〜数十秒で許容**: フリート管理、燃費最適化、定期レポート
- **運用チームが小規模 / インフラ管理を避けたい**
- **Databricks既存ユーザーで統合プラットフォームの価値を重視**
- **データ品質・ガバナンスが最優先**

---

# 判断基準マトリクス

以下のフォーマットで意思決定マトリクスを作成してください：

| 判断基準 | RisingWave + Databricks | Databricks SDP のみ | 推奨シナリオ |
|---------|------------------------|---------------------|------------|
| エンドツーエンド レイテンシー | ◎ (100ms〜1s) | ○ (1s〜30s) | サブ秒が必須 → RW、秒単位で十分 → SDP |
| 運用負荷 | △ (EC2/Docker管理) | ◎ (フルマネージド) | 運用チームが小規模 → SDP |
| スケーラビリティ | △ (K8s必要) | ◎ (自動スケーリング) | 台数増加に柔軟対応 → SDP |
| コスト (小規模) | △ (EC2常時起動) | ◎ (サーバーレス) | 小規模・バースト → SDP |
| コスト (大規模) | ○ (EC2定額) | △ (DBU従量課金) | 大量データ常時処理 → RW |
| データ品質・ガバナンス | △ (自前実装) | ◎ (DLT Expectations, UC) | コンプライアンス重視 → SDP |
| マルチエンジン互換 | ◎ (Iceberg) | ○ (UniForm) | Snowflake等と共有 → RW |
| AI/ML統合 | △ (別途連携) | ◎ (Feature Store等) | ML前提 → SDP |
| 学習コスト | ○ (PostgreSQL互換) | ○ (Spark SQL) | SQL経験者 → どちらもOK |

---

# サンプルデータセット詳細

今回のデモで使用したCANバスシミュレーションデータの仕様を記載してください：

## CAN Bus フレームフォーマット（20バイトバイナリ）

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0-7 | 8 bytes | timestamp | Unix epoch ミリ秒 (Big Endian) |
| 8-9 | 2 bytes | CAN ID | CAN Arbitration ID (Big Endian) |
| 10 | 1 byte | DLC | Data Length Code (常に8) |
| 11-18 | 8 bytes | DATA | CAN Data Payload |
| 19 | 1 byte | CRC | チェックサム |

## センサータイプマッピング

| CAN ID (Dec) | CAN ID (Hex) | Sensor Type | Data Field | Unit | Decode Formula |
|--------------|-------------|-------------|------------|------|----------------|
| 176 | 0xB0 | SPEED | DATA[0:2] | km/h | (byte[11] << 8 | byte[12]) / 100.0 |
| 192 | 0xC0 | RPM | DATA[0:2] | rpm | (byte[11] << 8 | byte[12]) / 4.0 |
| 416 | 0x1A0 | FUEL | DATA[0] | % | byte[11] / 2.55 |
| 768 | 0x300 | GPS | DATA[0:8] | lat/lon | 4byte each, /1e5 - 90 (lat), /1e5 - 180 (lon) |
| 1024 | 0x400 | ACCEL | DATA[0:8] | m/s² | 加速度 (3軸) |
| 1280 | 0x500 | BATTERY | DATA[0:2] | V / % | バッテリー電圧・SOC |

## デモデータ統計

| 指標 | 値 |
|------|---|
| 総レコード数 | 245,748 (全センサー合計) |
| センサータイプ数 | 6 (SPEED, RPM, FUEL, GPS, ACCEL, BATTERY) |
| 各センサーのレコード数 | 40,958 |
| データ期間 | 約60秒 (23:43:41 → 23:44:41 UTC) |
| 1秒あたりのレコード数 | 約4,096 rec/sec (全センサー合計) |
| 1フレームのサイズ | 20 bytes |
| スループット | 約80 KB/sec → 6.6 GB/day → 2.4 TB/year (1台あたり) |
| 速度データ範囲 | 0 〜 180 km/h (平均 67.44 km/h) |
| RPMデータ範囲 | 0 〜 8,000+ rpm (平均 2,299 rpm) |
| 燃料データ範囲 | 20% 〜 100% |
| Iceberg出力サイズ (S3) | 約2.3 MB (17ファイル: Parquet + Avro metadata) |

## Kinesis Data Streams 設定
- ストリーム名: honda-can-stream
- リージョン: us-west-2
- シャード数: 1 (デモ用)
- フォーマット: PLAIN / BYTES (20バイトバイナリそのまま)

## RisingWave パイプライン構成
- デプロイ: EC2 (t3.medium) + Docker (risingwavelabs/risingwave:latest)
- モード: playground (シングルノード)
- Source: `kinesis_can_source` (BYTEA payload)
- MV1: `can_frames_decoded` - CAN バイナリを get_byte() で逐次デコード
- MV2: `vehicle_summary_1min` - TUMBLE(event_time, 1 MINUTE) ウィンドウ集計
- Sink1: `iceberg_sink_decoded` - append-only, commit間隔10チェックポイント
- Sink2: `iceberg_sink_summary` - append-only, commit間隔20チェックポイント
- S3アクセス: VPC Gateway Endpoint 経由 (SCP対応)

---

# 資料のトーン・スタイル

- お客様は日本の自動車OEMまたはTier1サプライヤーのITアーキテクト / データエンジニアを想定
- 技術的に正確でありながら、経営判断に使える粒度で記述
- 「どちらが正解」ではなく「要件に応じた最適解の選択」を促すニュートラルな立場
- ただし、**レイテンシー要件が数秒〜数十秒で十分な場合はDatabricks SDPを推奨**するトーンで記述（運用負荷・TCO・統合性の観点）
- Databricks SAとしての提案なので、Databricksプラットフォームの価値を自然に訴求しつつ、RisingWaveのような外部OSSとの組み合わせも否定しない誠実な姿勢

# 出力形式
- プレゼンテーション風のセクション構成（スライド10〜15枚相当）
- 各セクションにMermaidアーキテクチャ図を埋め込み
- 比較表・マトリクスを多用
- 最後に「推奨アプローチ」セクションで、ユースケース別の推奨構成を3パターン程度提示
```

---

このプロンプトをGensparkに貼り付けてご利用ください。
