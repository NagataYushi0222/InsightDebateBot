# InsightDebate Bot

Discord上のボイスチャットを自動録音・分析し、議論の要約や対立構造を可視化するAI Botです。

## 特徴
- 📹 **ユーザーごとの音声録音**: 各参加者の発言を個別に記録
- 🤖 **Gemini AIによる分析**: Google Gemini APIで音声を文字起こし・分析
- 🔍 **ファクトチェック**: Google検索機能で発言内容の正確性を確認
- 📊 **2つのモード**: 「議論分析」と「会議要約」を選択可能
- 💰 **完全無料**: サーバー代・API利用料は各自負担（BYOKモデル）
- 🐳 **Docker対応**: CLI環境・ヘッドレスサーバーでも動作可能

## クイックスタート（アプリ版）

### 1. Discord Botの作成
1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. 「New Application」をクリック
3. 名前を入力して作成
4. 左メニュー「Bot」→「Reset Token」→トークンをコピー（このトークンは二度と表示されないので注意！）
5. 下にスクロールして以下をONにする：
   - **Presence Intent**
   - **Server Members Intent**
   - **Message Content Intent**
6. 左メニュー「OAuth2」→「URL Generator」
   - Scopesで `bot` と `applications.commands` を選択
   - Bot Permissionsで以下を選択：
     - Send Messages
     - Send Messages in Threads
     - Create Public Threads
     - Connect (Voice)
     - Speak (Voice)
7. 生成されたURLをコピーして、ブラウザで開く → Botをサーバーに追加

### 2. Gemini APIキーの取得
1. [Google AI Studio](https://aistudio.google.com/app/apikey)にアクセス
2. 「Create API Key」をクリック
3. キーをコピー

### 3. アプリの起動
1. ダウンロードしたアプリを起動
   - **注意**: 黒い画面（ターミナル/コンソール）が開きますが、これはBotのログを表示するため正常な動作です。閉じないでください。
2. 初回起動時、GUI（設定ウィンドウ）が表示される
3. 手順1で取得したDiscord Bot Tokenを入力
4. 「保存して起動」をクリック

### 4. 使用方法
1. 分析したいボイスチャンネルに参加
2. テキストチャンネルで `/settings set_key <Gemini APIキー>` を実行
3. `/analyze_start` で分析開始
4. `/analyze_stop` で終了

## コマンド一覧
- `/analyze_start` - 録音・分析を開始
- `/analyze_stop` - 停止してVCから退出
- `/settings set_key <key>` - Gemini APIキーを設定
- `/settings set_mode <debate|summary>` - 分析モード変更
- `/settings set_interval <秒>` - レポート間隔変更（デフォルト300秒=5分）

## トラブルシューティング

### macOSで「開発元が未確認」と表示される
```bash
xattr -cr InsightDebateBot.app
```

### Windowsで「WindowsによってPCが保護されました」
「詳細情報」→「実行」をクリック

## Docker / CLI環境での実行

### 環境変数を使用する方法（推奨）
```bash
# Discord Tokenを環境変数で設定
export DISCORD_TOKEN="your_discord_bot_token_here"

# Botを起動
python main.py
```

### Docker環境での実行
```bash
# Dockerイメージをビルド
docker build -t insightdebate-bot .

# 環境変数でトークンを指定して起動
docker run -e DISCORD_TOKEN="your_token" insightdebate-bot

# または、token.txtファイルをマウント
docker run -v $(pwd)/token.txt:/app/token.txt insightdebate-bot
```

### CLI対応について
GUIが使えない環境（Docker、SSH接続など）でも動作します：
- **環境変数** `DISCORD_TOKEN` が設定されていれば、GUIなしで起動
- **token.txt** ファイルがあれば、そこからトークンを読み込み
- どちらもない場合は、CLIプロンプトでトークンを入力

## 開発者向け

### セットアップ（ソースコードから実行）
```bash
# リポジトリをクローン
git clone https://github.com/NagataYushi0222/InsightDebateBot.git
cd InsightDebateBot

# 依存関係をインストール
pip install -r insight_bot/requirements.txt

# 環境変数を設定（または token.txt を作成）
export DISCORD_TOKEN="your_token"

# 起動
python main.py
```

### 変更履歴の管理（Git）
コードの変更履歴はGitで自動的に管理されます。

#### 変更をコミット（保存）する
```bash
# 変更されたファイルを確認
git status

# 変更をステージング（保存準備）
git add insight_bot/bot.py  # 特定のファイルを追加
# または
git add .  # すべての変更を追加

# コミット（変更を記録）
git commit -m "Fix: Docker/CLI環境対応 - tkinterを条件付きインポートに変更"

# GitHubにプッシュ（アップロード）
git push origin main
```

#### 過去のバージョンを確認する
```bash
# コミット履歴を表示
git log --oneline

# 特定のファイルの変更履歴を見る
git log -p insight_bot/bot.py

# 過去のバージョンと比較
git diff HEAD~1 insight_bot/bot.py  # 1つ前のコミットと比較
```

#### 過去のバージョンに戻す
```bash
# 特定のファイルだけ戻す
git checkout <commit-hash> -- insight_bot/bot.py

# すべてを特定のコミットに戻す（注意！）
git reset --hard <commit-hash>
```

**💡 ヒント**: GitHubのウェブサイトでも変更履歴を視覚的に確認できます！
- リポジトリページ → 「Commits」タブ
- ファイルページ → 「History」ボタン

## ライセンス
MIT License
