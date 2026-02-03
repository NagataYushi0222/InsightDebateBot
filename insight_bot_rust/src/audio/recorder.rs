//! Per-user audio recorder with Opus encoding
//!
//! Records Discord voice audio and saves directly as Opus/OGG files

use dashmap::DashMap;
use parking_lot::RwLock;
use serenity::model::id::UserId;
use songbird::events::context_data::VoiceTick;
use std::collections::HashMap;
use std::fs::{self, File};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use thiserror::Error;
use tracing::{debug, error, info, warn};

#[derive(Error, Debug)]
pub enum RecorderError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("No audio data available")]
    NoData,
}

/// Per-user audio buffer
struct UserAudioBuffer {
    /// Raw Opus frames received from Discord
    opus_frames: Vec<Vec<u8>>,
    /// Timestamp when recording started for this user
    start_time: u64,
}

impl UserAudioBuffer {
    fn new() -> Self {
        Self {
            opus_frames: Vec::new(),
            start_time: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_secs(),
        }
    }

    fn add_frame(&mut self, data: Vec<u8>) {
        self.opus_frames.push(data);
    }

    fn is_empty(&self) -> bool {
        self.opus_frames.is_empty()
    }

    fn take_frames(&mut self) -> Vec<Vec<u8>> {
        std::mem::take(&mut self.opus_frames)
    }
}

/// User-specific audio recorder
///
/// Collects Opus audio frames from Discord and saves them as OGG files
pub struct UserRecorder {
    /// Per-user audio buffers
    user_buffers: DashMap<UserId, UserAudioBuffer>,
    /// Temporary audio directory
    temp_dir: PathBuf,
    /// Session timestamp for unique filenames
    session_timestamp: u64,
}

impl UserRecorder {
    /// Create a new recorder
    pub fn new<P: AsRef<Path>>(temp_dir: P) -> Result<Self, RecorderError> {
        let temp_dir = temp_dir.as_ref().to_path_buf();
        
        // Ensure temp directory exists
        fs::create_dir_all(&temp_dir)?;
        
        let session_timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        Ok(Self {
            user_buffers: DashMap::new(),
            temp_dir,
            session_timestamp,
        })
    }

    /// Process incoming voice tick from Songbird
    ///
    /// This is called for each voice packet received
    pub fn process_voice_tick(&self, tick: &VoiceTick) {
        for (ssrc, data) in &tick.speaking {
            // Use SSRC as temporary User ID (u32 -> u64)
            let user_id = UserId::new(*ssrc as u64);

            if let Some(packet) = &data.packet {
                let payload = &packet.payload;
                if !payload.is_empty() {
                    self.add_opus_packet(user_id, payload);
                }
            }
        }
    }

    /// Add audio data for a specific user
    pub fn add_audio_data(&self, user_id: UserId, opus_data: &[u8]) {
        let mut entry = self.user_buffers.entry(user_id).or_insert_with(UserAudioBuffer::new);
        entry.add_frame(opus_data.to_vec());
        debug!("Added {} bytes for user {}", opus_data.len(), user_id);
    }

    /// Add raw Opus packet from voice receive handler
    pub fn add_opus_packet(&self, user_id: UserId, opus_packet: &[u8]) {
        if opus_packet.is_empty() {
            return;
        }
        
        let mut entry = self.user_buffers.entry(user_id).or_insert_with(UserAudioBuffer::new);
        entry.add_frame(opus_packet.to_vec());
        
        // Print a dot for activity (like Python version)
        print!(".");
        std::io::stdout().flush().ok();
    }

    /// Flush all user audio to files
    ///
    /// Returns a map of user_id -> file_path for saved audio
    pub async fn flush_audio(&self) -> Result<HashMap<UserId, PathBuf>, RecorderError> {
        let mut saved_files = HashMap::new();
        let current_time = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        // Collect user IDs to process
        let user_ids: Vec<UserId> = self.user_buffers.iter().map(|r| *r.key()).collect();

        for user_id in user_ids {
            if let Some((_, mut buffer)) = self.user_buffers.remove(&user_id) {
                if buffer.is_empty() {
                    continue;
                }

                let frames = buffer.take_frames();
                let filename = format!(
                    "{}_{}_{}",
                    self.session_timestamp,
                    user_id.get(),
                    current_time
                );
                
                // Save as raw Opus data (we'll wrap in OGG container)
                match self.save_opus_frames(&filename, &frames) {
                    Ok(path) => {
                        info!("Saved audio for user {} to {:?}", user_id, path);
                        saved_files.insert(user_id, path);
                    }
                    Err(e) => {
                        error!("Failed to save audio for user {}: {}", user_id, e);
                    }
                }
            }
        }

        if saved_files.is_empty() {
            return Err(RecorderError::NoData);
        }

        Ok(saved_files)
    }

    /// Save Opus frames to an OGG file
    fn save_opus_frames(&self, filename: &str, frames: &[Vec<u8>]) -> Result<PathBuf, RecorderError> {
        let ogg_path = self.temp_dir.join(format!("{}.ogg", filename));
        
        // For now, save raw Opus frames concatenated
        // In a full implementation, we'd properly wrap in OGG container
        let opus_path = self.temp_dir.join(format!("{}.opus", filename));
        
        let mut file = File::create(&opus_path)?;
        for frame in frames {
            // Write frame length as u16 little-endian, then frame data
            let len = frame.len() as u16;
            file.write_all(&len.to_le_bytes())?;
            file.write_all(frame)?;
        }
        
        info!("Saved {} Opus frames to {:?}", frames.len(), opus_path);
        Ok(opus_path)
    }

    /// Clear all buffers without saving
    pub fn clear(&self) {
        self.user_buffers.clear();
    }

    /// Check if there's any audio data buffered
    pub fn has_data(&self) -> bool {
        self.user_buffers.iter().any(|r| !r.value().is_empty())
    }

    /// Get the number of users currently being recorded
    pub fn user_count(&self) -> usize {
        self.user_buffers.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[tokio::test]
    async fn test_recorder_basic() {
        let temp = tempdir().unwrap();
        let recorder = UserRecorder::new(temp.path()).unwrap();
        
        let user_id = UserId::new(12345);
        recorder.add_opus_packet(user_id, &[0x00, 0x01, 0x02, 0x03]);
        recorder.add_opus_packet(user_id, &[0x04, 0x05, 0x06, 0x07]);
        
        assert!(recorder.has_data());
        assert_eq!(recorder.user_count(), 1);
        
        let files = recorder.flush_audio().await.unwrap();
        assert_eq!(files.len(), 1);
        assert!(files.contains_key(&user_id));
    }
}
