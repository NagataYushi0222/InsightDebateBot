# InsightDebate Bot

Discord上のボイスチャットを自動録音・分析し、議論の要約や対立構造を可視化するAI Botです。

## ✨ 特徴
- 📹 **ユーザーごとの音声録音**: 各参加者の発言を個別に記録
- 🤖 **Gemini AIによる分析**: Google Gemini APIで音声を文字起こし・分析・要約
- 🔍 **ファクトチェック**: Google検索機能で発言内容の正確性を確認（議論モード）
- 📊 **2つのモード**: 「議論分析（Debate）」と「会議要約（Summary）」を選択可能
- 💰 **完全無料**: サーバー代・API利用料は各自負担（BYOKモデル）
- 🐳 **Docker対応**: 簡単に自鯖でホスト可能

---

## 🚀 クイックスタート（アプリ版）

プログラミング知識不要で、Windows/Mac上でダブルクリックで動かせます。

### 1. 準備する
1. **Discord Bot Token**: [Developer Portal](https://discord.com/developers/applications)から取得（詳細は[こちら](https://github.com/reactiflux/discord-irc/wiki/Creating-a-discord-bot-&-getting-a-token)）
2. **Gemini API Key**: [Google AI Studio](https://aistudio.google.com/app/apikey)から取得

### 2. 起動する
1. [Releasesページ](https://github.com/NagataYushi0222/InsightDebateBot/releases)から最新のアプリをダウンロード
2. 起動すると、ターミナル（黒い画面）が開きます
3. 画面の指示に従い、用意したTokenとAPI Keyを貼り付けます（初回のみ）
4. ✅ バリデーションに成功すると、設定が保存されBotが起動します

---

## 🐳 クイックスタート（Docker版）

VPSや自宅サーバーで24時間稼働させるのに最適です。

### 1. セットアップ（初回のみ）
```bash
git clone https://github.com/NagataYushi0222/InsightDebateBot.git
cd InsightDebateBot

# 対話モードで設定を開始
docker compose run --rm bot
```
上記のコマンドを実行すると、ターミナル上でトークンとAPIキーの入力を求められます。
入力内容はローカルの `.env` ファイルに保存されます。

### 2. 本番起動
```bash
docker compose up -d
```
バックグラウンドで起動します。

### 💡 Hint: コマンドの反映を早くする
Discordのコマンド登録には時間がかかることがあります（最大1時間）。
即座に反映させたい場合は、`.env` ファイルを開き、`GUILD_ID=あなたのサーバーID` を追記して再起動してください。

---

## 🎮 使い方（コマンド一覧）

### 📊 メイン機能
| コマンド | 説明 |
| --- | --- |
| `/analyze_start` | VCの録音・分析を開始します |
| `/analyze_stop` | 分析を終了し、最後のレポートを出力してから退出します |
| `/analyze_now` | **(New)** 定期レポートを待たずに、今すぐ分析を実行します |

### ⚙️ 設定変更
| コマンド | 説明 |
| --- | --- |
| `/settings set_mode` | 分析モードを切替 (`debate`: 議論重視 / `summary`: 要約重視) |
| `/settings set_interval` | レポート間隔を変更（秒単位、デフォルト300秒） |

---

## 🛠 開発者向け情報

### ソースコードから実行
```bash
# 1. Clone
git clone https://github.com/NagataYushi0222/InsightDebateBot.git
cd InsightDebateBot

# 2. Install Dependencies
pip install -r insight_bot/requirements.txt

# 3. Run
python main.py
```

### 技術スタック
- **Language**: Python 3.10+
- **Framework**: py-cord (Discord API)
- **AI Model**: Google Gemini 1.5 Flash (via `google-genai` SDK)
- **Audio Processing**: ffmpeg

## コントリビューション
Pull Request は大歓迎です！機能追加、バグ修正、翻訳などお気軽にどうぞ。

## ライセンス
[MIT License](LICENSE)
