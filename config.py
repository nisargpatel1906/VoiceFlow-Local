"""
VoiceFlow Local - Configuration Settings

Default settings for the voice dictation application.
Modify these values to customize behavior.
"""

import os

# =============================================================================
# HOTKEY SETTINGS
# =============================================================================
# Global hotkey to trigger push-to-talk recording
# Format: 'modifier+key' (e.g., 'ctrl+alt', 'windows+space')
HOTKEY = 'ctrl+space'

# =============================================================================
# WHISPER MODEL SETTINGS
# =============================================================================
# Model size: 'tiny', 'base', 'small', 'medium', 'large-v3'
# Larger = more accurate but slower and more VRAM
MODEL_SIZE = 'medium'

# Device: 'cuda' for NVIDIA GPU, 'cpu' for CPU-only
DEVICE = 'cuda'

# Compute type for GPU inference
# Options: 'float16', 'int8', 'int8_float16', 'float32'
# 'float16' recommended for most CUDA GPUs
COMPUTE_TYPE = 'float16'

# Language code for transcription
# 'en' = English, 'es' = Spanish, 'fr' = French, etc.
LANGUAGE = 'en'

# Preload model during startup. If False, loads on first dictation instead.
PRELOAD_MODEL_ON_START = False

# =============================================================================
# TEXT PROCESSING
# =============================================================================
# Remove common filler words from transcription
REMOVE_FILLERS = True

# List of filler words to remove (case-insensitive matching)
FILLER_WORDS = [
    'um', 'uh', 'like', 'you know', 'basically',
    'actually', 'literally', 'right', 'so', 'well'
]

# =============================================================================
# HISTORY & STORAGE
# =============================================================================
# Maximum number of transcriptions to keep in history
HISTORY_LIMIT = 50

# Directory for storing models and temp files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'models')
TEMP_DIR = os.path.join(BASE_DIR, 'temp')
LOG_FILE = os.path.join(BASE_DIR, 'voiceflow_log.txt')
