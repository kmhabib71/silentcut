#!/usr/bin/env python3
"""
Fast Transcript Generation Module
Optimized for speed and accuracy using multiple methods
"""

import os
import sys
import time
import threading
import tempfile
import subprocess
import json
from PyQt5.QtCore import QThread, pyqtSignal

class FastTranscriptGenerator(QThread):
    """Ultra-fast transcript generation using optimized methods"""

    progress_updated = pyqtSignal(int, str)  # progress, status
    transcript_ready = pyqtSignal(list)  # list of word objects with timestamps
    error_occurred = pyqtSignal(str)

    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path
        self.methods = [
            self.try_whisper_cpp,      # Fastest: whisper.cpp
            self.try_faster_whisper,   # Fast: faster-whisper
            self.try_openai_whisper,   # Medium: OpenAI Whisper
            self.try_vosk_offline,     # Fast offline: Vosk
            self.try_wav2vec2,         # Alternative: Wav2Vec2
        ]

    def run(self):
        """Try multiple methods in order of speed"""
        try:
            for i, method in enumerate(self.methods):
                self.progress_updated.emit(10 + i * 15, f"Trying method {i+1}/{len(self.methods)}...")

                try:
                    transcript = method()
                    if transcript:
                        self.transcript_ready.emit(transcript)
                        return
                except Exception as e:
                    print(f"Method {i+1} failed: {e}")
                    continue

            # If all methods fail, try basic fallback
            self.progress_updated.emit(90, "Using fallback method...")
            transcript = self.fallback_transcript()
            if transcript:
                self.transcript_ready.emit(transcript)
            else:
                self.error_occurred.emit("All transcript generation methods failed")

        except Exception as e:
            self.error_occurred.emit(f"Transcript generation error: {str(e)}")

    def try_whisper_cpp(self):
        """Try whisper.cpp (fastest method)"""
        try:
            # Check if whisper.cpp is available
            result = subprocess.run(['whisper', '--version'], capture_output=True, text=True)
            if result.returncode != 0:
                return None

            self.progress_updated.emit(20, "Using whisper.cpp (fastest)...")

            # Extract audio
            temp_audio = self.extract_audio_fast()
            if not temp_audio:
                return None

            # Run whisper.cpp
            cmd = [
                'whisper', temp_audio,
                '--model', 'tiny',  # Fastest model
                '--output-format', 'json',
                '--word-timestamps', 'true',
                '--language', 'en'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                # Parse JSON output
                json_file = temp_audio.replace('.wav', '.json')
                if os.path.exists(json_file):
                    with open(json_file, 'r') as f:
                        data = json.load(f)

                    transcript = self.parse_whisper_json(data)

                    # Cleanup
                    os.unlink(temp_audio)
                    os.unlink(json_file)

                    return transcript

        except Exception as e:
            print(f"whisper.cpp failed: {e}")

        return None

    def try_faster_whisper(self):
        """Try faster-whisper library"""
        try:
            from faster_whisper import WhisperModel

            self.progress_updated.emit(25, "Using faster-whisper...")

            # Use CPU with optimizations
            model = WhisperModel("tiny", device="cpu", compute_type="int8")

            # Extract audio
            temp_audio = self.extract_audio_fast()
            if not temp_audio:
                return None

            # Transcribe with word timestamps
            segments, info = model.transcribe(
                temp_audio,
                word_timestamps=True,
                language="en",
                beam_size=1,  # Faster
                best_of=1     # Faster
            )

            transcript = []
            word_id = 0

            for segment in segments:
                for word in segment.words:
                    transcript.append({
                        'id': word_id,
                        'word': word.word.strip(),
                        'start': word.start,
                        'end': word.end,
                        'confidence': getattr(word, 'probability', 0.9)
                    })
                    word_id += 1

            # Cleanup
            os.unlink(temp_audio)

            return transcript

        except ImportError:
            # Try to install faster-whisper
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "faster-whisper"],
                             capture_output=True, check=True)
                return self.try_faster_whisper()  # Retry
            except:
                pass
        except Exception as e:
            print(f"faster-whisper failed: {e}")

        return None

    def try_openai_whisper(self):
        """Try OpenAI Whisper (original)"""
        try:
            import whisper

            self.progress_updated.emit(30, "Using OpenAI Whisper...")

            # Load fastest model
            model = whisper.load_model("tiny")

            # Extract audio
            temp_audio = self.extract_audio_fast()
            if not temp_audio:
                return None

            # Transcribe
            result = model.transcribe(
                temp_audio,
                word_timestamps=True,
                language="en",
                fp16=False
            )

            transcript = []
            word_id = 0

            for segment in result.get("segments", []):
                for word_data in segment.get("words", []):
                    transcript.append({
                        'id': word_id,
                        'word': word_data.get('word', '').strip(),
                        'start': word_data.get('start', 0),
                        'end': word_data.get('end', 0),
                        'confidence': 1.0
                    })
                    word_id += 1

            # Cleanup
            os.unlink(temp_audio)

            return transcript

        except ImportError:
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "openai-whisper"],
                             capture_output=True, check=True)
                return self.try_openai_whisper()  # Retry
            except:
                pass
        except Exception as e:
            print(f"OpenAI Whisper failed: {e}")

        return None

    def try_vosk_offline(self):
        """Try Vosk for offline recognition"""
        try:
            import vosk
            import wave

            self.progress_updated.emit(35, "Using Vosk offline...")

            # Check for model
            model_path = "vosk-model-small-en-us-0.15"
            if not os.path.exists(model_path):
                # Try to download small model
                self.download_vosk_model()

            if not os.path.exists(model_path):
                return None

            model = vosk.Model(model_path)
            rec = vosk.KaldiRecognizer(model, 16000)
            rec.SetWords(True)

            # Extract audio as WAV
            temp_audio = self.extract_audio_wav()
            if not temp_audio:
                return None

            # Process audio
            wf = wave.open(temp_audio, 'rb')
            transcript = []
            word_id = 0

            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break

                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    if 'result' in result:
                        for word_data in result['result']:
                            transcript.append({
                                'id': word_id,
                                'word': word_data.get('word', ''),
                                'start': word_data.get('start', 0),
                                'end': word_data.get('end', 0),
                                'confidence': word_data.get('conf', 0.8)
                            })
                            word_id += 1

            # Final result
            final_result = json.loads(rec.FinalResult())
            if 'result' in final_result:
                for word_data in final_result['result']:
                    transcript.append({
                        'id': word_id,
                        'word': word_data.get('word', ''),
                        'start': word_data.get('start', 0),
                        'end': word_data.get('end', 0),
                        'confidence': word_data.get('conf', 0.8)
                    })
                    word_id += 1

            wf.close()
            os.unlink(temp_audio)

            return transcript

        except Exception as e:
            print(f"Vosk failed: {e}")

        return None

    def try_wav2vec2(self):
        """Try Wav2Vec2 model"""
        try:
            import torch
            import torchaudio
            from transformers import Wav2Vec2ForCTC, Wav2Vec2Tokenizer

            self.progress_updated.emit(40, "Using Wav2Vec2...")

            # Load model
            tokenizer = Wav2Vec2Tokenizer.from_pretrained("facebook/wav2vec2-base-960h")
            model = Wav2Vec2ForCTC.from_pretrained("facebook/wav2vec2-base-960h")

            # Extract audio
            temp_audio = self.extract_audio_fast()
            if not temp_audio:
                return None

            # Load audio
            waveform, sample_rate = torchaudio.load(temp_audio)

            # Resample if needed
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(sample_rate, 16000)
                waveform = resampler(waveform)

            # Transcribe
            input_values = tokenizer(waveform.squeeze().numpy(), return_tensors="pt", sampling_rate=16000).input_values

            with torch.no_grad():
                logits = model(input_values).logits

            predicted_ids = torch.argmax(logits, dim=-1)
            transcription = tokenizer.decode(predicted_ids[0])

            # Convert to word format (approximate timestamps)
            words = transcription.split()
            duration = len(waveform[0]) / 16000
            time_per_word = duration / len(words) if words else 0

            transcript = []
            for i, word in enumerate(words):
                transcript.append({
                    'id': i,
                    'word': word,
                    'start': i * time_per_word,
                    'end': (i + 1) * time_per_word,
                    'confidence': 0.8
                })

            os.unlink(temp_audio)
            return transcript

        except Exception as e:
            print(f"Wav2Vec2 failed: {e}")

        return None

    def fallback_transcript(self):
        """Fallback method using basic speech recognition"""
        try:
            import speech_recognition as sr

            self.progress_updated.emit(50, "Using fallback method...")

            # Extract audio
            temp_audio = self.extract_audio_wav()
            if not temp_audio:
                return None

            r = sr.Recognizer()
            with sr.AudioFile(temp_audio) as source:
                audio = r.record(source)

            # Try Google Speech Recognition
            text = r.recognize_google(audio)
            words = text.split()

            # Create approximate timestamps
            duration = self.get_audio_duration(temp_audio)
            time_per_word = duration / len(words) if words else 0

            transcript = []
            for i, word in enumerate(words):
                transcript.append({
                    'id': i,
                    'word': word,
                    'start': i * time_per_word,
                    'end': (i + 1) * time_per_word,
                    'confidence': 0.7
                })

            os.unlink(temp_audio)
            return transcript

        except Exception as e:
            print(f"Fallback method failed: {e}")

        return None

    def extract_audio_fast(self):
        """Extract audio quickly using FFmpeg"""
        try:
            temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_audio.close()

            cmd = [
                "ffmpeg", "-i", self.video_path,
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                "-y", temp_audio.name
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return temp_audio.name

        except Exception as e:
            print(f"Audio extraction failed: {e}")

        return None

    def extract_audio_wav(self):
        """Extract audio as WAV format"""
        return self.extract_audio_fast()  # Same implementation

    def get_audio_duration(self, audio_path):
        """Get audio duration"""
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                "-of", "csv=p=0", audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return float(result.stdout.strip())
        except:
            pass
        return 0

    def parse_whisper_json(self, data):
        """Parse whisper JSON output"""
        transcript = []
        word_id = 0

        for segment in data.get("segments", []):
            for word in segment.get("words", []):
                transcript.append({
                    'id': word_id,
                    'word': word.get('word', '').strip(),
                    'start': word.get('start', 0),
                    'end': word.get('end', 0),
                    'confidence': word.get('probability', 0.9)
                })
                word_id += 1

        return transcript

    def download_vosk_model(self):
        """Download Vosk model if needed"""
        try:
            import urllib.request
            import zipfile

            model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
            zip_path = "vosk-model.zip"

            self.progress_updated.emit(15, "Downloading Vosk model...")
            urllib.request.urlretrieve(model_url, zip_path)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall('.')

            os.unlink(zip_path)

        except Exception as e:
            print(f"Failed to download Vosk model: {e}")

# Export the main class
__all__ = ['FastTranscriptGenerator']
