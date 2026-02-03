//! Gemini API analyzer module
//!
//! Handles audio file upload and analysis via Gemini REST API

use crate::database::AnalysisMode;
use reqwest::{multipart, Client};
use serde::{Deserialize, Serialize};
use serenity::model::id::UserId;
use std::collections::HashMap;
use std::path::PathBuf;
use std::time::Duration;
use thiserror::Error;
use tokio::fs::File;
use tokio::io::AsyncReadExt;
use tracing::{debug, error, info, warn};

const GEMINI_API_BASE: &str = "https://generativelanguage.googleapis.com/v1beta";
const GEMINI_UPLOAD_BASE: &str = "https://generativelanguage.googleapis.com/upload/v1beta";

#[derive(Error, Debug)]
pub enum AnalyzerError {
    #[error("HTTP request failed: {0}")]
    Http(#[from] reqwest::Error),
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("API error: {0}")]
    Api(String),
    #[error("No audio files provided")]
    NoAudioFiles,
    #[error("Rate limit exceeded")]
    RateLimitExceeded,
}

/// Prompts for different analysis modes
pub mod prompts {
    use crate::database::AnalysisMode;
    
    pub const DEBATE: &str = r#"
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
"#;

    pub const SUMMARY: &str = r#"
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
"#;

    pub fn get_prompt(mode: &AnalysisMode) -> &'static str {
        match mode {
            AnalysisMode::Debate => DEBATE,
            AnalysisMode::Summary => SUMMARY,
        }
    }
}

/// Response from Gemini file upload
#[derive(Debug, Deserialize)]
struct UploadResponse {
    file: FileInfo,
}

#[derive(Debug, Deserialize)]
struct FileInfo {
    name: String,
    uri: String,
    #[serde(rename = "mimeType")]
    mime_type: String,
    state: String,
}

/// Response from Gemini content generation
#[derive(Debug, Deserialize)]
struct GenerateResponse {
    candidates: Option<Vec<Candidate>>,
    error: Option<ApiError>,
}

#[derive(Debug, Deserialize)]
struct Candidate {
    content: Content,
}

#[derive(Debug, Deserialize)]
struct Content {
    parts: Vec<Part>,
}

#[derive(Debug, Deserialize)]
struct Part {
    text: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ApiError {
    code: i32,
    message: String,
}

/// Request body for content generation
#[derive(Debug, Serialize)]
struct GenerateRequest {
    contents: Vec<ContentRequest>,
    tools: Option<Vec<Tool>>,
}

#[derive(Debug, Serialize)]
struct ContentRequest {
    role: String,
    parts: Vec<PartRequest>,
}

#[derive(Debug, Serialize)]
#[serde(untagged)]
enum PartRequest {
    Text { text: String },
    FileData { file_data: FileData },
}

#[derive(Debug, Serialize)]
struct FileData {
    file_uri: String,
    mime_type: String,
}

#[derive(Debug, Serialize)]
struct Tool {
    google_search: GoogleSearch,
}

#[derive(Debug, Serialize)]
struct GoogleSearch {}

/// Gemini API client for audio analysis
pub struct Analyzer {
    client: Client,
    api_key: String,
    model: String,
}

impl Analyzer {
    /// Create a new analyzer with the given API key
    pub fn new(api_key: String) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(300))
            .build()
            .expect("Failed to create HTTP client");

        Self {
            client,
            api_key,
            model: "gemini-2.0-flash".to_string(),
        }
    }

    /// Upload a file to Gemini File API
    async fn upload_file(&self, path: &PathBuf, mime_type: &str) -> Result<FileInfo, AnalyzerError> {
        let mut file = File::open(path).await?;
        let mut buffer = Vec::new();
        file.read_to_end(&mut buffer).await?;

        let file_name = path.file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("audio.opus");

        let url = format!(
            "{}/files?key={}",
            GEMINI_UPLOAD_BASE, self.api_key
        );

        // Create multipart form
        let part = multipart::Part::bytes(buffer)
            .file_name(file_name.to_string())
            .mime_str(mime_type)?;

        let form = multipart::Form::new()
            .part("file", part);

        let response = self.client
            .post(&url)
            .multipart(form)
            .send()
            .await?;

        if !response.status().is_success() {
            let status = response.status();
            let text = response.text().await.unwrap_or_default();
            error!("Upload failed: {} - {}", status, text);
            return Err(AnalyzerError::Api(format!("Upload failed: {}", status)));
        }

        let upload_response: UploadResponse = response.json().await?;
        info!("Uploaded file: {}", upload_response.file.name);
        
        Ok(upload_response.file)
    }

    /// Wait for file to become active
    async fn wait_for_file_active(&self, file_name: &str) -> Result<(), AnalyzerError> {
        let url = format!(
            "{}/files/{}?key={}",
            GEMINI_API_BASE, file_name, self.api_key
        );

        for _ in 0..30 {
            let response = self.client.get(&url).send().await?;
            
            if response.status().is_success() {
                let file_info: FileInfo = response.json().await?;
                if file_info.state == "ACTIVE" {
                    return Ok(());
                }
                if file_info.state == "FAILED" {
                    return Err(AnalyzerError::Api("File processing failed".to_string()));
                }
            }
            
            tokio::time::sleep(Duration::from_secs(2)).await;
        }

        Err(AnalyzerError::Api("File processing timeout".to_string()))
    }

    /// Delete a file from Gemini API
    async fn delete_file(&self, file_name: &str) -> Result<(), AnalyzerError> {
        let url = format!(
            "{}/files/{}?key={}",
            GEMINI_API_BASE, file_name, self.api_key
        );

        let _ = self.client.delete(&url).send().await;
        Ok(())
    }

    /// Analyze audio files from multiple users
    pub async fn analyze_discussion(
        &self,
        audio_files: HashMap<UserId, PathBuf>,
        context_history: &str,
        user_map: HashMap<UserId, String>,
        mode: AnalysisMode,
    ) -> Result<String, AnalyzerError> {
        if audio_files.is_empty() {
            return Err(AnalyzerError::NoAudioFiles);
        }

        let prompt = prompts::get_prompt(&mode);
        let mut uploaded_files = Vec::new();
        let mut content_parts = Vec::new();

        // Add system prompt
        content_parts.push(PartRequest::Text {
            text: prompt.to_string(),
        });

        // Add context if available
        if !context_history.is_empty() {
            content_parts.push(PartRequest::Text {
                text: format!("前回の文脈:\n{}\n---\n今回の議論:", context_history),
            });
        }

        // Upload each audio file
        for (user_id, file_path) in &audio_files {
            let user_name = user_map
                .get(user_id)
                .cloned()
                .unwrap_or_else(|| format!("User_{}", user_id));

            // Get MIME type
            let mime_type = crate::audio::AudioProcessor::get_mime_type(file_path);

            match self.upload_file(file_path, mime_type).await {
                Ok(file_info) => {
                    // Wait for file to be ready
                    if let Err(e) = self.wait_for_file_active(&file_info.name).await {
                        warn!("File not ready: {}", e);
                        continue;
                    }

                    content_parts.push(PartRequest::Text {
                        text: format!("発言者: {}", user_name),
                    });
                    content_parts.push(PartRequest::FileData {
                        file_data: FileData {
                            file_uri: file_info.uri.clone(),
                            mime_type: file_info.mime_type.clone(),
                        },
                    });
                    uploaded_files.push(file_info.name);
                }
                Err(e) => {
                    warn!("Failed to upload file for user {}: {}", user_name, e);
                }
            }
        }

        if uploaded_files.is_empty() {
            return Err(AnalyzerError::NoAudioFiles);
        }

        // Generate content
        let request = GenerateRequest {
            contents: vec![ContentRequest {
                role: "user".to_string(),
                parts: content_parts,
            }],
            tools: Some(vec![Tool {
                google_search: GoogleSearch {},
            }]),
        };

        let url = format!(
            "{}/models/{}:generateContent?key={}",
            GEMINI_API_BASE, self.model, self.api_key
        );

        let response = self.client
            .post(&url)
            .json(&request)
            .send()
            .await?;

        // Clean up uploaded files
        for file_name in &uploaded_files {
            let _ = self.delete_file(file_name).await;
        }

        if !response.status().is_success() {
            let status = response.status();
            let text = response.text().await.unwrap_or_default();
            
            if status.as_u16() == 429 || text.contains("Quota exceeded") {
                return Err(AnalyzerError::RateLimitExceeded);
            }
            
            return Err(AnalyzerError::Api(format!("Generation failed: {} - {}", status, text)));
        }

        let gen_response: GenerateResponse = response.json().await?;

        if let Some(error) = gen_response.error {
            return Err(AnalyzerError::Api(error.message));
        }

        // Extract text from response
        let text = gen_response
            .candidates
            .and_then(|c| c.into_iter().next())
            .and_then(|c| c.content.parts.into_iter().next())
            .and_then(|p| p.text)
            .unwrap_or_else(|| "分析結果を取得できませんでした。".to_string());

        Ok(text)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_prompt_selection() {
        assert!(prompts::get_prompt(&AnalysisMode::Debate).contains("議論アナリスト"));
        assert!(prompts::get_prompt(&AnalysisMode::Summary).contains("会議の書記"));
    }
}
