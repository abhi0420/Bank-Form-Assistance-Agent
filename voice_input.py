import sounddevice as sd
import numpy as np
from transformers import WhisperProcessor, WhisperForConditionalGeneration
import torch

# Configuration
MODEL_NAME = "openai/whisper-small"  # Options: whisper-tiny, whisper-base, whisper-small, whisper-medium, whisper-large
SAMPLE_RATE = 16000  # Whisper expects 16kHz audio
RECORDING_DURATION = 5  # seconds (reduced for faster testing)

print(f"Loading Whisper model: {MODEL_NAME}...")
print("(This may take a minute on first run as it downloads the model)\n")

# Load model and processor
processor = WhisperProcessor.from_pretrained(MODEL_NAME)
model = WhisperForConditionalGeneration.from_pretrained(MODEL_NAME)

# Use GPU if available
device = "cuda" if torch.cuda.is_available() else "cpu"
model = model.to(device)
print(f"Model loaded on: {device}")


def record_audio(duration=RECORDING_DURATION, sample_rate=SAMPLE_RATE):
    """Record audio from microphone."""
    print(f"\n🎤 Recording for {duration} seconds...")
    print("   Speak now! (Press Ctrl+C to stop early)\n")
    
    try:
        # Show countdown while recording
        import time
        audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
        
        for i in range(duration, 0, -1):
            print(f"   ⏱️  {i} seconds remaining...", end='\r')
            time.sleep(1)
            # Check if we have enough audio (user might stop early)
            if not sd.get_stream().active:
                break
        
        sd.wait()  # Wait until recording is finished
        print("   ✅ Recording complete!          ")
        
    except KeyboardInterrupt:
        sd.stop()
        print("\n   ⏹️  Recording stopped early")
    
    # Flatten to 1D array
    audio = audio.flatten()
    
    # Check if audio was captured
    max_amp = np.max(np.abs(audio))
    print(f"   📊 Audio level: {max_amp:.3f}")
    if max_amp < 0.01:
        print("   ⚠️  Warning: Very low audio level - check your microphone!")
    
    return audio


def transcribe(audio, sample_rate=SAMPLE_RATE):
    """Transcribe audio using Whisper."""
    print("📝 Transcribing...")
    
    # Process audio for Whisper
    input_features = processor(
        audio, 
        sampling_rate=sample_rate, 
        return_tensors="pt"
    ).input_features.to(device)
    
    # Generate transcription
    with torch.no_grad():
        predicted_ids = model.generate(input_features)
    
    # Decode to text
    transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
    return transcription.strip()


def main():
    print("\n" + "="*50)
    print("🎙️  Voice Input for Bank Form")
    print("="*50)
    
    while True:
        input("\nPress Enter to start recording (or Ctrl+C to exit)...")
        
        # Record
        audio = record_audio()
        
        # Transcribe
        text = transcribe(audio)
        
        print("\n" + "-"*50)
        print("📄 Transcription:")
        print(f"   {text}")
        print("-"*50)
        
        # Ask if user wants to continue
        again = input("\nRecord again? (y/n): ").strip().lower()
        if again != 'y':
            break
    
    print("\n👋 Done!")


if __name__ == "__main__":
    main()
