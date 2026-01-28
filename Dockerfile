# Python 3.11をベースイメージとして使用
FROM python:3.11-slim

# 作業ディレクトリを設定
WORKDIR /app

# システム依存関係をインストール
# - ffmpeg: 音声処理に必要
# - libopus0: Discord音声コーデック
# - ca-certificates: SSL証明書
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus0 \
    libopus-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Pythonの依存関係をコピーしてインストール
COPY insight_bot/requirements.txt /app/insight_bot/requirements.txt
RUN pip install --no-cache-dir -r insight_bot/requirements.txt

# アプリケーションコードをコピー
COPY . /app/

# 一時音声ファイル用のディレクトリを作成
RUN mkdir -p /app/temp_audio

# 環境変数のデフォルト値（実行時にオーバーライド可能）
ENV PYTHONUNBUFFERED=1
ENV DISCORD_TOKEN=""

# Botを起動
CMD ["python", "main.py"]
