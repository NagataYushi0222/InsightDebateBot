# Docker環境 検証手順書

このドキュメントでは、InsightDebateBotがDocker環境で正しく動作するかを検証する手順を説明します。

## 前提条件

### 1. Dockerのインストール

まず、Dockerがインストールされているか確認してください：

```bash
docker --version
```

インストールされていない場合は、以下からインストールしてください：
- **macOS/Windows**: [Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Linux**: [Docker Engine](https://docs.docker.com/engine/install/)

---

## 検証方法

### オプション A: 自動検証スクリプトを使用（推奨）

```bash
# スクリプトに実行権限を付与
chmod +x test-docker.sh

# 検証スクリプトを実行
./test-docker.sh
```

このスクリプトは以下を自動で行います：
1. ✅ Dockerのインストール確認
2. 🔨 Dockerイメージのビルド
3. 🧪 CLI動作確認（GUIなしで起動できるか）
4. 📊 イメージサイズの確認

---

### オプション B: 手動で検証

#### Step 1: Dockerイメージをビルド

```bash
docker build -t insightdebate-bot:test .
```

**期待される結果**: エラーなくビルドが完了すること

---

#### Step 2: CLI動作確認（環境変数なし）

```bash
docker run -it --rm insightdebate-bot:test
```

**期待される結果**:
- ❌ GUIエラーが出ない
- ✅ 以下のようなCLIプロンプトが表示される:
  ```
  GUI not available (running in CLI mode): ...
  
  === InsightDebateBot - Initial Setup ===
  Please enter your Discord Bot Token.
  ...
  Discord Bot Token: 
  ```

**確認ポイント**: `ModuleNotFoundError: No module named 'tkinter'` のようなエラーで落ちないこと

**終了方法**: `Ctrl+C` を押す

---

#### Step 3: 環境変数での起動確認

```bash
docker run -e DISCORD_TOKEN="test_dummy_token" --rm insightdebate-bot:test
```

**期待される結果**:
- ✅ GUIプロンプトをスキップして起動を試みる
- ✅ "Logged in as..." または Discord接続エラーが表示される（ダミートークンなので接続は失敗しますが、それは正常です）

**確認ポイント**: トークン入力を求められず、すぐに起動プロセスが始まること

**終了方法**: `Ctrl+C` を押す

---

#### Step 4: 実際のトークンでテスト（オプション）

実際のDiscord Bot Tokenを使ってテストする場合：

```bash
docker run -e DISCORD_TOKEN="your_actual_discord_token_here" --rm insightdebate-bot:test
```

**期待される結果**:
- ✅ Botが正常にDiscordに接続
- ✅ "Logged in as YourBotName" と表示される

---

## トラブルシューティング

### ❌ `docker: command not found`

**原因**: Dockerがインストールされていない、またはPATHが通っていない

**解決策**:
1. Docker Desktopをインストール
2. インストール後、ターミナルを再起動

---

### ❌ ビルド時に `libopus` エラー

**原因**: システム依存関係のインストール失敗

**解決策**: Dockerfileの以下の部分を確認：
```dockerfile
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus0 \
    libopus-dev \
    ...
```

---

### ❌ 起動時に `ImportError: tkinter`

**原因**: tkinterが条件付きインポートになっていない

**解決策**: `insight_bot/bot.py` の修正が正しく反映されているか確認
```python
# ❌ 間違い (トップレベルインポート)
import tkinter as tk

# ✅ 正しい (関数内で条件付きインポート)
def get_discord_token():
    if not token:
        try:
            import tkinter as tk
            ...
```

---

## 検証チェックリスト

以下の項目をすべて確認してください：

- [ ] Dockerイメージが正常にビルドできる
- [ ] 環境変数なしで起動した際、CLIプロンプトが表示される
- [ ] GUIライブラリ (tkinter) のImportErrorが発生しない
- [ ] 環境変数 `DISCORD_TOKEN` を設定すると、プロンプトなしで起動する
- [ ] 実際のトークンで起動し、Discordに接続できる（オプション）

---

## 本番環境へのデプロイ

検証が完了したら、以下の方法で本番環境にデプロイできます：

### Docker Compose を使用

```yaml
# docker-compose.yml
version: '3.8'

services:
  bot:
    build: .
    environment:
      - DISCORD_TOKEN=${DISCORD_TOKEN}
    restart: unless-stopped
```

起動:
```bash
DISCORD_TOKEN="your_token" docker-compose up -d
```

### Docker Hub / Container Registry

```bash
# イメージにタグを付ける
docker tag insightdebate-bot:test your-username/insightdebate-bot:latest

# レジストリにプッシュ
docker push your-username/insightdebate-bot:latest
```

---

## まとめ

このドキュメントの手順に従うことで、以下が確認できます：

1. ✅ **CLI環境対応**: GUIなしでも動作する
2. ✅ **Docker互換性**: コンテナ内で正常に起動する
3. ✅ **環境変数サポート**: トークンを安全に設定できる

問題が発生した場合は、GitHubのIssuesで報告してください。
