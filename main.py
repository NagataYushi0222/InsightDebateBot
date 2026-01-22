#!/usr/bin/env python3
import sys
import os

# Fix SSL certificate issue for PyInstaller builds - MUST be before any SSL imports
if getattr(sys, 'frozen', False):
    import certifi
    cert_path = certifi.where()
    os.environ['SSL_CERT_FILE'] = cert_path
    os.environ['SSL_CERT_DIR'] = os.path.dirname(cert_path)
    os.environ['REQUESTS_CA_BUNDLE'] = cert_path

from insight_bot.bot import run_bot

if __name__ == "__main__":
    run_bot()
