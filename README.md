# 🏦 Bank Form Assistant

<p align="center">
  <strong>An AI-powered conversational agent that helps you fill bank forms through natural chat — no more confusing paperwork.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.0+-000000?logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?logo=openai&logoColor=white" alt="OpenAI">
  <img src="https://img.shields.io/badge/Whisper-Local_STT-green?logo=openai&logoColor=white" alt="Whisper">
</p>

---

## ✨ Features

- **🤖 Conversational Form Filling** — Chat naturally with an LLM (GPT-4o-mini) that extracts form fields from your messages. No clicking through dropdowns — just talk.
- **🔍 Smart Form Detection** — Describe what you need ("I want to deposit money at the post office") and the assistant automatically identifies the correct form.
- **🎙️ Voice Input** — Click the mic button to speak instead of typing. Uses a locally-running Whisper model (`openai/whisper-small`) for speech-to-text — no audio leaves your machine.
- **🔊 Voice Output** — Responses are read aloud using the browser's built-in SpeechSynthesis API.
- **📄 PDF Generation** — Fills the actual bank PDF form at the correct coordinates, merges text onto the original, and gives you a downloadable filled PDF.
- **🎨 PDF Styling** — Customize font family, size, bold, and text color from the settings panel before generating the PDF.
- **📐 Multiline Fields** — Fields like addresses automatically word-wrap within bounding boxes with configurable line spacing.
- **🏦 Multi-Bank Support** — Organized sidebar with bank logos, collapsible dropdowns, and per-bank form listings.

---

## � Screenshots

<table>
  <tr>
    <td align="center"><strong>🏠 Initial Screen</strong></td>
    <td align="center"><strong>💬 Chatbot Conversation</strong></td>
    <td align="center"><strong>📋 Info Summary</strong></td>
  </tr>
  <tr>
    <td><img src="static/Initial%20screen.png" alt="Initial Screen" width="350"></td>
    <td><img src="static/Convo%20with%20chatbot.png" alt="Chatbot Conversation" width="350"></td>
    <td><img src="static/Summary%20of%20info.png" alt="Summary of Info" width="350"></td>
  </tr>
</table>

---

## �🗂️ Project Structure

```
Bank-Form-Assistance-Agent/
├── app.py                    # Flask backend — API routes, session management
├── chatbot.py                # LLM logic — form detection & form filling prompts
├── fill_form.py              # PDF generation — text overlay, multiline wrapping
├── voice_input.py            # Local Whisper STT — model loading & transcription
├── add_coordinates.py        # Utility — overlays coordinate grid on PDFs
├── field_coordinates.json    # Form field definitions (coords, descriptions)
├── available_forms.json      # Bank → forms registry
├── requirements.txt          # Python dependencies
├── .env                      # OpenAI API key (not committed)
├── static/
│   ├── sbi_logo.png              # SBI logo
│   ├── post_office_logo.png      # Post Office logo
│   ├── Initial screen.png        # Screenshot — home screen
│   ├── Convo with chatbot.png    # Screenshot — chat in action
│   └── Summary of info.png       # Screenshot — field summary
├── templates/
│   └── index.html                # Full web UI (sidebar, chat, settings)
└── forms/
    ├── Pay-in-Slip.pdf               # Post Office deposit slip
    ├── PO_Aadhar_link_form.pdf       # Post Office Aadhar linking form
    └── UID_Aadhar_linking_letter.pdf  # SBI Aadhar linking form
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **FFmpeg** — required for audio format conversion (voice input)
- **OpenAI API key** — for GPT-4o-mini chat completions

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/abhi0420/Bank-Form-Assistance-Agent.git
   cd Bank-Form-Assistance-Agent
   ```

2. **Create a virtual environment and install dependencies**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   # source .venv/bin/activate   # macOS/Linux
   pip install -r requirements.txt
   ```

3. **Set up environment variables**

   Create a `.env` file in the project root:

   ```
   OPENAI_API_KEY=sk-your-api-key-here
   ```

4. **Install FFmpeg** (for voice input)

   ```bash
   # Windows (via winget)
   winget install Gyan.FFmpeg

   # macOS
   brew install ffmpeg

   # Ubuntu/Debian
   sudo apt install ffmpeg
   ```

5. **Run the application**

   ```bash
   python app.py
   ```

   The app starts at **http://localhost:5000**. The Whisper model downloads automatically on first launch (~500 MB).

---

## 💬 How It Works

### Conversation Flow

```
User: "I need to deposit ₹5000 at the post office"
  │
  ▼
┌─────────────────────────┐
│  Form Detection (LLM)   │  ← Identifies "Pay-in-Slip" from description
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│  Form Filling (LLM)     │  ← Extracts Amount = 5000, asks for remaining fields
└───────────┬─────────────┘
            ▼
User: "Account number is 12345678, credit to Raj Kumar"
  │
  ▼
┌─────────────────────────┐
│  Aggressive Extraction   │  ← Fills Account Number + Credit To in one go
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│  PDF Generation          │  ← Overlays text onto original PDF at exact coords
└───────────┬─────────────┘
            ▼
       📄 Filled PDF ready for download
```

### Architecture

| Component | Technology | Role |
|-----------|-----------|------|
| **Frontend** | HTML/CSS/JS (single-page) | Chat UI, voice controls, PDF settings |
| **Backend** | Flask | API routes, session state, audio pipeline |
| **LLM** | OpenAI GPT-4o-mini | Natural language understanding & field extraction |
| **STT** | Whisper (local, `openai/whisper-small`) | Voice-to-text, runs entirely on-device |
| **TTS** | Browser SpeechSynthesis API | Reads responses aloud |
| **PDF Engine** | ReportLab + PyPDF2 | Text overlay generation & PDF merging |

---

## 📋 Supported Forms

| Bank | Form | Description |
|------|------|-------------|
| Post Office | Pay-in-Slip | Deposit money into post office savings account |
| Post Office | Aadhar Linking Form | Link Aadhar with Post Office account |
| State Bank of India | Aadhar Linking Form | Link Aadhar card with bank account |

---

## ➕ Adding New Forms

1. **Place the blank PDF** in the `forms/` directory.

2. **Generate a coordinate grid** to find field positions:

   Edit `INPUT_PDF` in `add_coordinates.py`, then run:

   ```bash
   python add_coordinates.py
   ```

   This creates a `_with_coordinates.pdf` showing X/Y positions.

3. **Add field definitions** to `field_coordinates.json`:

   ```json
   {
     "form_name": "Your Form Name",
     "bank": "Bank Name",
     "description": "What this form does",
     "pdf_path": "forms/your_form.pdf",
     "form_fields": [
       {
         "field": "Field Name",
         "description": "What this field is for",
         "start": [x, y],
         "end": [x2, y2],
         "value": "",
         "font_size": 10
       }
     ]
   }
   ```

   **Field options:**
   | Property | Description |
   |----------|-------------|
   | `start` / `end` | `[x, y]` coordinates (origin top-left) |
   | `spacing` | Character spacing for fields like dates or account numbers |
   | `font_size` | Override font size for this field |
   | `bold` | Override bold for this field |
   | `type` | Set to `"checkbox"` for tick-mark fields |
   | `multiline` | Set to `true` for bounding-box text wrapping |
   | `line_spacing` | Vertical spacing between lines (for multiline fields) |

4. **Register the form** in `available_forms.json`:

   ```json
   {
     "bank": "Bank Name",
     "forms": [
       {
         "form_name": "Your Form Name",
         "description": "What this form does",
         "aliases": ["alternate name", "common name"],
         "pdf_path": "forms/your_form.pdf",
         "coordinates_file": "field_coordinates.json"
       }
     ]
   }
   ```

---

## ⚙️ Configuration

| Setting | Location | Default |
|---------|----------|---------|
| LLM model | `app.py`, `chatbot.py` | `gpt-4o-mini` |
| LLM temperature | `app.py` | `0.4` |
| Whisper model | `voice_input.py` | `openai/whisper-small` |
| Audio sample rate | `voice_input.py` | `16000 Hz` |
| PDF font | UI Settings Panel | Helvetica, 10pt, bold, navy |
| Server port | `app.py` | `5000` |

---

## 📝 License

This project is for educational and personal use.

---

<p align="center">
  Made with ❤️ for hassle-free banking
</p>
