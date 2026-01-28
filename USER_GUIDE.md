# InsightDebateBot 利用ガイド

このBotは、あなたの環境に合わせて3つの方法で利用できます。

## 🔰 方法1: アプリ版を使う（一番かんたん！）
プログラミングの知識は不要です。WindowsやMacのアプリとして動かせます。

1. **ダウンロード**: [Releasesページ](https://github.com/NagataYushi0222/InsightDebateBot/releases)から、お使いのOS用ファイルをダウンロードしてください。
2. **起動**: ダウンロードしたファイルをダブルクリックします。
3. **設定**: 画面の指示に従って、「Discord Bot Token」を入力すれば完了です！

---

## 🐳 方法2: Dockerで使う（サーバー管理者向け・推奨）
VPSや自宅サーバーで24時間稼働させたい場合は、この方法が最適です。

### 必要なもの
- Docker / Docker Compose

### 手順
1. リポジトリをダウンロード
   ```bash
   git clone https://github.com/NagataYushi0222/InsightDebateBot.git
   cd InsightDebateBot
   ```

2. 設定ファイルを作成
   ```bash
   cp .env.example .env
   # .envファイルを開いて、DISCORD_TOKENを入力してください
   ```

3. 起動！
   ```bash
   docker-compose up -d
   ```
   これだけでバックグラウンドで動き出します！

---

## 💻 方法3: ソースコードから動かす（開発者向け）
Python環境がある方は、直接コードを実行できます。

### 必要なもの
- Python 3.10以上
- git
- ffmpeg (macなら `brew install ffmpeg`, winなら公式サイトから)

### 手順
1. 準備
   ```bash
   git clone https://github.com/NagataYushi0222/InsightDebateBot.git
   cd InsightDebateBot
   pip install -r insight_bot/requirements.txt
   ```

2. 起動
   ```bash
   python main.py
   ```
   
3. 設定
   - 初回起動時にトークンの入力を求められます。
   - **ポイント**: GUIが使えない環境（SSHなど）でも、自動的にコマンドライン入力モードになるので安心です！

---

## ❓ トラブルシューティング & よくある質問

### 🍎 macOSで「開発元を検証できません（Malware...）」と出る場合
これはAppleのセキュリティ機能です。ウイルスではありません。以下のどちらかで解決できます：

**方法A (右クリック):**
アプリアイコンを **右クリック（またはControl+クリック）** して「開く」を選び、ダイアログでもう一度「開く」を押してください。

**方法B (コマンド):**
ターミナルで以下を実行すると、警告が出なくなります。
```bash
xattr -cr InsightDebateBot.app
```

### その他の質問

**Q. 「Discord Bot Token」ってどこで手に入れるの？**
A. [Discord Developer Portal](https://discord.com/developers/applications)で作れます。詳しくはREADMEの「Botの作成方法」を見てください。

**Q. お金はかかりますか？**
A. Bot自体の利用は完全無料です！ただし、もしGemini APIを有料枠で使う場合はGoogleへの支払いが発生する場合があります（無料枠でも十分使えます）。
