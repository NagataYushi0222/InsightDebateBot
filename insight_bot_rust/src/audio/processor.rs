//! Audio processor for format conversion
//!
//! Handles conversion between audio formats if needed for Gemini API

use std::fs;
use std::path::{Path, PathBuf};
use thiserror::Error;
use tracing::{debug, info, warn};

#[derive(Error, Debug)]
pub enum ProcessorError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("File not found: {0}")]
    NotFound(PathBuf),
}

/// Audio processor for format operations
pub struct AudioProcessor;

impl AudioProcessor {
    /// Check if a file needs conversion for Gemini API
    ///
    /// Gemini API accepts: audio/mp3, audio/wav, audio/ogg, audio/flac
    /// Since we save as Opus (.opus files), we may need to wrap in OGG container
    pub fn needs_conversion(path: &Path) -> bool {
        // Opus raw files might need to be converted to OGG for API compatibility
        path.extension()
            .and_then(|e| e.to_str())
            .map(|e| e == "opus")
            .unwrap_or(false)
    }

    /// Get MIME type for audio file
    pub fn get_mime_type(path: &Path) -> &'static str {
        match path.extension().and_then(|e| e.to_str()) {
            Some("ogg") => "audio/ogg",
            Some("opus") => "audio/ogg", // Opus in OGG container
            Some("mp3") => "audio/mp3",
            Some("wav") => "audio/wav",
            Some("flac") => "audio/flac",
            Some("pcm") => "audio/pcm",
            _ => "audio/ogg",
        }
    }

    /// Convert Opus file to OGG container if needed
    ///
    /// For now, we keep Opus as-is since Gemini should accept audio/ogg
    pub fn prepare_for_upload(path: &Path) -> Result<PathBuf, ProcessorError> {
        if !path.exists() {
            return Err(ProcessorError::NotFound(path.to_path_buf()));
        }

        // For now, just return the path as-is
        // In a full implementation, we might wrap raw Opus in OGG container
        Ok(path.to_path_buf())
    }

    /// Clean up temporary audio files
    pub fn cleanup_files(paths: &[PathBuf]) {
        for path in paths {
            if path.exists() {
                match fs::remove_file(path) {
                    Ok(_) => debug!("Removed temp file: {:?}", path),
                    Err(e) => warn!("Failed to remove {:?}: {}", path, e),
                }
            }
        }
    }

    /// Get audio duration in seconds (approximate based on file size)
    ///
    /// For Opus at ~64kbps, we can estimate duration
    pub fn estimate_duration(path: &Path) -> f64 {
        match fs::metadata(path) {
            Ok(meta) => {
                let size = meta.len() as f64;
                // Opus typically ~8KB/sec at 64kbps
                size / 8000.0
            }
            Err(_) => 0.0,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mime_types() {
        assert_eq!(AudioProcessor::get_mime_type(Path::new("test.ogg")), "audio/ogg");
        assert_eq!(AudioProcessor::get_mime_type(Path::new("test.opus")), "audio/ogg");
        assert_eq!(AudioProcessor::get_mime_type(Path::new("test.mp3")), "audio/mp3");
    }
}
