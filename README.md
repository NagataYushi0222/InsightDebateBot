# InsightDebate Bot

Discord上のボイスチャットを自動録音・分析し、議論の要約や対立構造を可視化するAI Botです。

## ✨ 特徴
- 📹 **ユーザーごとの音声録音**: 各参加者の発言を個別に記録
- 🤖 **Gemini AIによる分析**: Google Gemini APIで音声を文字起こし・分析・要約
- � **BYOK (Bring Your Own Key)**: 各ユーザーが自分のAPIキーを設定して利用（Botオーナーの負担なし）
- �🔍 **ファクトチェック**: Google検索機能で発言内容の正確性を確認
- 📊 **2つのモード**: 「議論分析（Debate）」と「会議要約（Summary）」を選択可能
-  **Docker対応**: 簡単に自鯖でホスト可能

---

## 🚀 クイックスタート（ユーザー向け）

Botが導入されたサーバーでの使い方は以下の通りです。

### 1. APIキーの設定（初回のみ）
Botを使用する各ユーザーは、自分のGemini APIキーを登録する必要があります。
（[Google AI Studio](https://aistudio.google.com/app/apikey) から無料で取得可能です）

Discord上で以下のコマンドを実行してください：
```
/settings set_apikey [あなたのAPIキー]
```
※キーは暗号化されて保存され、他のユーザーからは見えません。一度設定すれば次回以降は自動で使用されます。

### 2. 分析の開始
ボイスチャットに参加した状態で、以下のコマンドを実行します：
```
/analyze_start
```

---

## � サーバー管理者向けセットアップ

### Dockerでの起動方法

1. リポジトリをクローン
```bash
git clone https://github.com/NagataYushi0222/InsightDebateBot.git
cd InsightDebateBot
```

2. Botトークンの設定
初回起動時にBotトークンの入力を求められるので、対話モードで設定します。
```bash
docker compose run --rm bot
```
※ `GEMINI_API_KEY` の入力は不要になりました（ユーザーごとに設定するため）。

3. 本番起動
```bash
docker compose up -d
```

### 環境変数 (.env)
- `DISCORD_TOKEN`: Botのトークン
- `GUILD_ID`: (任意) コマンド反映を高速化するためのサーバーID

---

## 🎮 コマンド一覧

### 📊 メイン機能
| コマンド | 説明 |
| --- | --- |
| `/analyze_start` | VCの録音・分析を開始します（要APIキー登録） |
| `/analyze_stop` | 分析を終了し、最後のレポートを出力してから退出します |
| `/analyze_now` | 定期レポートを待たずに、今すぐ分析を実行します |

### ⚙️ 設定変更
| コマンド | 説明 |
| --- | --- |
| `/settings set_apikey` | **(重要)** あなた専用のGemini APIキーを登録します |
| `/settings set_mode` | 分析モードを切替 (`debate`: 議論重視 / `summary`: 要約重視) |
| `/settings set_interval` | レポート間隔を変更（秒単位、デフォルト300秒） |

---

## 技術スタック
- **Language**: Python 3.10+
- **Framework**: py-cord (Discord API)
- **AI Model**: Google Gemini 1.5 Flash / 2.0 Flash (via `google-genai` SDK)
- **Database**: SQLite (ユーザー設定・APIキー保存)

## ライセンス
[MIT License](LICENSE)
