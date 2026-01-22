import sqlite3
import os

DB_PATH = "bot_settings.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            api_key TEXT,
            analysis_mode TEXT DEFAULT 'debate',
            recording_interval INTEGER DEFAULT 300
        )
    ''')
    conn.commit()
    conn.close()

def get_guild_settings(guild_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM guild_settings WHERE guild_id = ?', (guild_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(row)
    else:
        # Return defaults if not found
        return {
            'guild_id': guild_id,
            'api_key': None,
            'analysis_mode': 'debate',
            'recording_interval': 300
        }

def update_guild_setting(guild_id, key, value):
    settings = get_guild_settings(guild_id)
    settings[key] = value
    
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO guild_settings (guild_id, api_key, analysis_mode, recording_interval)
        VALUES (?, ?, ?, ?)
    ''', (guild_id, settings['api_key'], settings['analysis_mode'], settings['recording_interval']))
    conn.commit()
    conn.close()
