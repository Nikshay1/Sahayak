"""
Audio Buffer Utility
Phase 2: Handles audio streaming and silence detection
"""

import io
import wave
import struct
from typing import List, Optional
from datetime import datetime
import numpy as np


class AudioBuffer:
    """
    Buffer for streaming audio with silence detection
    Ensures we don't cut off elderly users who speak slowly
    """
    
    def __init__(
        self,
        sample_rate: int = 8000,  # Telephony standard
        sample_width: int = 2,     # 16-bit audio
        channels: int = 1,         # Mono
        silence_threshold: float = 0.02  # Amplitude threshold for silence
    ):
        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self.channels = channels
        self.silence_threshold = silence_threshold
        
        self.chunks: List[bytes] = []
        self.start_time: Optional[datetime] = None
        self.total_samples = 0
        
    def add_chunk(self, chunk: bytes):
        """Add audio chunk to buffer"""
        if self.start_time is None:
            self.start_time = datetime.now()
        
        self.chunks.append(chunk)
        self.total_samples += len(chunk) // self.sample_width
    
    def is_silence(self, chunk: bytes, threshold: Optional[float] = None) -> bool:
        """
        Check if audio chunk is silence
        
        Args:
            chunk: Audio bytes
            threshold: Optional custom threshold
            
        Returns:
            True if chunk is below silence threshold
        """
        threshold = threshold or self.silence_threshold
        
        try:
            # Convert bytes to numpy array
            if self.sample_width == 2:
                samples = np.frombuffer(chunk, dtype=np.int16)
            else:
                samples = np.frombuffer(chunk, dtype=np.int8)
            
            # Normalize to 0-1 range
            max_val = 32768 if self.sample_width == 2 else 128
            normalized = np.abs(samples.astype(float) / max_val)
            
            # Calculate RMS amplitude
            rms = np.sqrt(np.mean(normalized ** 2))
            
            return rms < threshold
            
        except Exception:
            return False
    
    def get_audio(self) -> bytes:
        """Get complete audio as bytes"""
        return b''.join(self.chunks)
    
    def get_wav(self) -> bytes:
        """Get audio as WAV format bytes"""
        audio_data = self.get_audio()
        
        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.sample_width)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_data)
        
        wav_buffer.seek(0)
        return wav_buffer.read()
    
    @property
    def duration_seconds(self) -> float:
        """Get duration of buffered audio in seconds"""
        return self.total_samples / self.sample_rate
    
    def clear(self):
        """Clear the buffer"""
        self.chunks = []
        self.start_time = None
        self.total_samples = 0


class SilenceDetector:
    """
    Advanced silence detection for elderly speech patterns
    """
    
    def __init__(
        self,
        min_silence_duration: float = 1.5,  # Minimum 1.5s silence
        max_pause_duration: float = 3.0,    # Max pause between words
        sample_rate: int = 8000
    ):
        self.min_silence_duration = min_silence_duration
        self.max_pause_duration = max_pause_duration
        self.sample_rate = sample_rate
        
        self.silence_start: Optional[datetime] = None
        self.speech_detected = False
        
    def process_chunk(self, chunk: bytes, is_silence: bool) -> dict:
        """
        Process audio chunk and determine state
        
        Returns:
            Dict with:
            - is_complete: True if user has finished speaking
            - silence_duration: Current silence duration
            - should_prompt: True if we should prompt user
        """
        now = datetime.now()
        
        if is_silence:
            if self.silence_start is None:
                self.silence_start = now
            
            silence_duration = (now - self.silence_start).total_seconds()
            
            # User finished speaking (1.5s silence after speech)
            if self.speech_detected and silence_duration >= self.min_silence_duration:
                return {
                    "is_complete": True,
                    "silence_duration": silence_duration,
                    "should_prompt": False
                }
            
            # Long pause - might need to prompt
            if silence_duration >= self.max_pause_duration:
                return {
                    "is_complete": False,
                    "silence_duration": silence_duration,
                    "should_prompt": True
                }
            
            return {
                "is_complete": False,
                "silence_duration": silence_duration,
                "should_prompt": False
            }
        else:
            # Speech detected
            self.speech_detected = True
            self.silence_start = None
            
            return {
                "is_complete": False,
                "silence_duration": 0,
                "should_prompt": False
            }
    
    def reset(self):
        """Reset detector state"""
        self.silence_start = None
        self.speech_detected = False