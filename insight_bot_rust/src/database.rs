//! Database management for guild settings
//!
//! Uses SQLite to persist per-guild configuration

use rusqlite::{Connection, Result as SqliteResult, params};
use std::path::Path;
use std::sync::Mutex;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum DatabaseError {
    #[error("SQLite error: {0}")]
    Sqlite(#[from] rusqlite::Error),
    #[error("Lock error")]
    LockError,
}

/// Analysis mode for the bot
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AnalysisMode {
    Debate,
    Summary,
}

impl AnalysisMode {
    pub fn as_str(&self) -> &'static str {
        match self {
            AnalysisMode::Debate => "debate",
            AnalysisMode::Summary => "summary",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "debate" => Some(AnalysisMode::Debate),
            "summary" => Some(AnalysisMode::Summary),
            _ => None,
        }
    }
}

impl Default for AnalysisMode {
    fn default() -> Self {
        AnalysisMode::Debate
    }
}

/// Guild-specific settings
#[derive(Debug, Clone)]
pub struct GuildSettings {
    pub guild_id: u64,
    pub api_key: Option<String>,
    pub analysis_mode: AnalysisMode,
    pub recording_interval: u64,
}

impl Default for GuildSettings {
    fn default() -> Self {
        Self {
            guild_id: 0,
            api_key: None,
            analysis_mode: AnalysisMode::Debate,
            recording_interval: 300,
        }
    }
}

/// Database connection wrapper
pub struct Database {
    conn: Mutex<Connection>,
}

impl Database {
    /// Open or create database at the given path
    pub fn open<P: AsRef<Path>>(path: P) -> Result<Self, DatabaseError> {
        let conn = Connection::open(path)?;
        let db = Self {
            conn: Mutex::new(conn),
        };
        db.init()?;
        Ok(db)
    }

    /// Initialize database tables
    fn init(&self) -> Result<(), DatabaseError> {
        let conn = self.conn.lock().map_err(|_| DatabaseError::LockError)?;
        conn.execute(
            "CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                api_key TEXT,
                analysis_mode TEXT DEFAULT 'debate',
                recording_interval INTEGER DEFAULT 300
            )",
            [],
        )?;
        Ok(())
    }

    /// Get settings for a guild (returns defaults if not found)
    pub fn get_guild_settings(&self, guild_id: u64) -> Result<GuildSettings, DatabaseError> {
        let conn = self.conn.lock().map_err(|_| DatabaseError::LockError)?;
        
        let mut stmt = conn.prepare(
            "SELECT guild_id, api_key, analysis_mode, recording_interval 
             FROM guild_settings WHERE guild_id = ?"
        )?;
        
        let result = stmt.query_row([guild_id], |row| {
            let mode_str: String = row.get(2)?;
            Ok(GuildSettings {
                guild_id: row.get(0)?,
                api_key: row.get(1)?,
                analysis_mode: AnalysisMode::from_str(&mode_str).unwrap_or_default(),
                recording_interval: row.get(3)?,
            })
        });

        match result {
            Ok(settings) => Ok(settings),
            Err(rusqlite::Error::QueryReturnedNoRows) => {
                Ok(GuildSettings {
                    guild_id,
                    ..Default::default()
                })
            }
            Err(e) => Err(e.into()),
        }
    }

    /// Update a specific setting for a guild
    pub fn update_guild_setting(
        &self,
        guild_id: u64,
        key: &str,
        value: &str,
    ) -> Result<(), DatabaseError> {
        let mut settings = self.get_guild_settings(guild_id)?;
        
        match key {
            "api_key" => settings.api_key = Some(value.to_string()),
            "analysis_mode" => {
                if let Some(mode) = AnalysisMode::from_str(value) {
                    settings.analysis_mode = mode;
                }
            }
            "recording_interval" => {
                if let Ok(interval) = value.parse() {
                    settings.recording_interval = interval;
                }
            }
            _ => {}
        }

        let conn = self.conn.lock().map_err(|_| DatabaseError::LockError)?;
        conn.execute(
            "INSERT OR REPLACE INTO guild_settings 
             (guild_id, api_key, analysis_mode, recording_interval)
             VALUES (?, ?, ?, ?)",
            params![
                guild_id,
                settings.api_key,
                settings.analysis_mode.as_str(),
                settings.recording_interval,
            ],
        )?;

        Ok(())
    }

    /// Update analysis mode for a guild
    pub fn set_analysis_mode(&self, guild_id: u64, mode: AnalysisMode) -> Result<(), DatabaseError> {
        self.update_guild_setting(guild_id, "analysis_mode", mode.as_str())
    }

    /// Update recording interval for a guild
    pub fn set_recording_interval(&self, guild_id: u64, interval: u64) -> Result<(), DatabaseError> {
        self.update_guild_setting(guild_id, "recording_interval", &interval.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_database_operations() {
        let db = Database::open(":memory:").unwrap();
        
        // Test default settings
        let settings = db.get_guild_settings(12345).unwrap();
        assert_eq!(settings.guild_id, 12345);
        assert_eq!(settings.analysis_mode, AnalysisMode::Debate);
        assert_eq!(settings.recording_interval, 300);
        
        // Test update
        db.set_analysis_mode(12345, AnalysisMode::Summary).unwrap();
        let settings = db.get_guild_settings(12345).unwrap();
        assert_eq!(settings.analysis_mode, AnalysisMode::Summary);
    }
}
