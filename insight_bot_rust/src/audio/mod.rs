//! Audio module for recording and processing
//!
//! Handles per-user audio recording with Opus encoding

pub mod recorder;
pub mod processor;

pub use recorder::UserRecorder;
pub use processor::AudioProcessor;
