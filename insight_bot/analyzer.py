from google import genai
from google.genai import types
import os
import time
from .config import GEMINI_API_KEY, GEMINI_MODEL_FLASH

PROMPTS = {
    "debate": """
あなたはプロの議論アナリスト兼ファクトチェッカーです。提供された複数の音声ファイル（各ファイル名にユーザーIDまたは名前が含まれる）を分析し、以下の形式でレポートを作成してください。

分析ルール:
1. 各ファイルの声とユーザー名を正確に紐付けてください。
2. **Grounding (Google検索) は必須です**。議論の中で出た事実（例：「現在の失業率は〜」「〇〇というニュースがあった」）について、必ず検索機能を使用して最新情報を確認してください。
3. 以前の発言と矛盾している点があれば指摘してください。
4. **【重要】音声が無音、ノイズのみ、または意味のある会話が含まれていない場合は、無理に分析せず、「特に新しい議論はありませんでした。」とだけ出力してください。幻覚（ハルシネーション）を起こさないでください。**
5. 「前回の文脈」はあくまで参考情報です。**今回提供された音声ファイルに含まれていない発言を、前回の文脈から捏造してレポートに含めないでください。**

出力項目:
【議論の要約】: (300字以内)
【各ユーザーの立場】: (ユーザー名: 賛成/反対/中立などの属性と主要な意見)
【現在の対立構造】: (何がボトルネックで合意に至っていないか)
【争点と矛盾・ファクトチェック】: (発言の矛盾点や、最新のネット情報と照らし合わせた誤りの指摘)
【対立点の折衷案】: (対立点を解決するための折衷案の提案)

**前置き・挨拶・自己紹介は一切不要です。上記の出力項目のみをそのまま出力してください。**
""",
    "summary": """
あなたは会議の書記です。提供された音声ファイルを分析し、途中から参加した人でも状況がわかるような親切な要約を作成してください。

分析ルール:
1. 誰が何について話しているかを明確にしてください。
2. 専門用語や文脈依存の単語には簡単な補足を加えてください。
3. **【重要】音声が無音、ノイズのみ、または意味のある会話が含まれていない場合は、無理に分析せず、「特に新しい議論はありませんでした。」とだけ出力してください。**
4. 「前回の文脈」はあくまで参考情報です。**今回提供された音声ファイルに含まれていない発言を、前回の文脈から捏造してレポートに含めないでください。**

出力項目:
【現在のトピック】: (今何を話しているか、数行でシンプルに)
【これまでの流れ】: (時系列で主な発言と決定事項を箇条書き)
【未解決の課題】: (まだ決まっていないこと、次に話すべきこと)
【参加者の発言要旨】: (各参加者の主な主張)

**前置き・挨拶・自己紹介は一切不要です。上記の出力項目のみをそのまま出力してください。**
"""
}

def upload_to_gemini(client, file_path, mime_type="audio/mp3"):
    """
    Uploads a file to Gemini File API using google-genai SDK.
    """
    try:
        # Use proper file upload from the new client
        # It handles waiting for processing internally in some versions, but let's be safe
        file_ref = client.files.upload(file=file_path, config={'mime_type': mime_type})
        return file_ref
    except Exception as e:
        print(f"Upload failed: {e}")
        raise e

def wait_for_files_active(client, files):
    """
    Waits for files to proceed to ACTIVE state.
    """
    print("Waiting for file processing...")
    for file_ref in files:
        # file_ref might be just the object returned by upload.
        # We need to poll its execution state.
        
        while True:
            # Refresh file info
            try:
                current_file = client.files.get(name=file_ref.name)
                if current_file.state == "ACTIVE":
                    break
                if current_file.state == "FAILED":
                    raise Exception(f"File {current_file.name} failed to process")
                
                print(".", end="", flush=True)
                time.sleep(2)
            except Exception as e:
                print(f"Error checking file state: {e}")
                break
                
    print("...all files ready")

def analyze_discussion(audio_files_map, context_history="", user_map=None, api_key=None, mode="debate"):
    """
    analyzes the discussion.
    audio_files_map: dict of {user_id: mp3_file_path}
    user_map: dict of {user_id: user_name}
    api_key: str (Required) - User's API key.
    mode: str - "debate" or "summary"
    """
    
    # Determine API Key
    use_key = api_key
    if not use_key:
        return "❌ APIキーが設定されていません。`/settings set_apikey` で設定してください。"

    # Initialize Client with specific key
    try:
        # Pass the key directly to Client
        client = genai.Client(api_key=use_key)
    except Exception as e:
        return f"❌ APIクライアントの初期化に失敗しました: {e}"

    uploaded_files = []
    
    # Determine Prompt
    system_prompt = PROMPTS.get(mode, PROMPTS["debate"])

    # Construct content parts
    contents = []
    
    # Add System Prompt
    contents.append(types.Content(
        role="user",
        parts=[types.Part.from_text(text=system_prompt)]
    ))
    
    if context_history:
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"前回の文脈:\n{context_history}\n---\n今回の議論:")]
        ))

    current_turn_parts = []
    
    for user_id, file_path in audio_files_map.items():
        if os.path.exists(file_path):
            user_name = user_map.get(user_id, f"User_{user_id}") if user_map else f"User_{user_id}"
            
            try:
                uploaded_file = upload_to_gemini(client, file_path)
                uploaded_files.append(uploaded_file)
                
                current_turn_parts.append(types.Part.from_text(text=f"発言者: {user_name}"))
                # Pass file URI for processing
                current_turn_parts.append(types.Part.from_uri(
                    file_uri=uploaded_file.uri,
                    mime_type=uploaded_file.mime_type
                ))
            except Exception as e:
                print(f"Skipping file {file_path} due to upload error: {e}")

    if not current_turn_parts:
        return "音声データがありませんでした（アップロード失敗またはファイルなし）。"
    
    # Append the audio parts to contents
    contents.append(types.Content(
        role="user",
        parts=current_turn_parts
    ))

    try:
        wait_for_files_active(client, uploaded_files)
        
        # Configure tools
        # Enable Google Search
        tool_config = types.Tool(
            google_search=types.GoogleSearch()
        )
        
        generate_config = types.GenerateContentConfig(
            tools=[tool_config],
            response_modalities=["TEXT"] # Ensure text output
        )
        
        response = client.models.generate_content(
            model=GEMINI_MODEL_FLASH,
            contents=contents,
            config=generate_config
        )
        
        # Clean up files
        for f in uploaded_files:
            try:
                client.files.delete(name=f.name)
            except:
                pass
            
        return response.text

    except Exception as e:
        print(f"Analysis Error: {e}")
        if "429" in str(e) or "Quota exceeded" in str(e):
             return "⚠️ 分析のリクエスト制限（Quota Limit）に達しました。"
        return f"分析中にエラーが発生しました: {e}"
