# TrailerIQ — AI-Powered YouTube Trailer Metadata Extractor

Extract **50+ structured metadata fields** from any YouTube movie trailer using a 6-agent AI pipeline. Supports Hindi, Tamil, Telugu, Malayalam, Kannada, Bengali, Marathi, Punjabi, English and more.

---

## Architecture

```
YouTube URL
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                   AGENT PIPELINE                         │
│                                                          │
│  1. IngestionAgent   → yt-dlp download + frame extract  │
│  2. AudioAgent       → Whisper STT + language detect    │
│  3. VisionAgent      → CLIP scene/object classification │
│  4. NLPAgent         → GPT-4o genre/plot/themes         │
│  5. MetadataAgent    → GPT-4o cast/crew/trailer type    │
│  6. AggregatorAgent  → merge + confidence scoring       │
└─────────────────────────────────────────────────────────┘
    │
    ▼
Structured JSON (9 categories, 50+ fields, confidence scores)
```

---

## ⚡ Quick Start

### Prerequisites

1. **Python 3.10+** — [python.org](https://python.org)
2. **Node.js 18+** — [nodejs.org](https://nodejs.org)
3. **ffmpeg** — Required for audio extraction by yt-dlp and Whisper

   **Windows (with winget):**
   ```powershell
   winget install Gyan.FFmpeg
   ```
   **Windows (with Chocolatey):**
   ```powershell
   choco install ffmpeg
   ```
   After install, restart your terminal and confirm: `ffmpeg -version`

### 1. Clone & Setup

```powershell
cd e:\Video_Extraction

# Copy environment config
copy .env.example .env
# Edit .env and fill in your API keys
notepad .env
```

### 2. Install Backend

```powershell
cd e:\Video_Extraction

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install PyTorch (CPU version — smaller, works on any machine)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install all other dependencies
pip install -r backend/requirements.txt
```

> **GPU acceleration** (optional): If you have an NVIDIA GPU, install CUDA PyTorch instead:
> ```powershell
> pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
> ```

### 3. Install Frontend

```powershell
cd e:\Video_Extraction\frontend
npm install
```

### 4. Run

Open **two separate terminals**:

**Terminal 1 — Backend:**
```powershell
cd e:\Video_Extraction
venv\Scripts\activate
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**
```powershell
cd e:\Video_Extraction\frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## API Keys

| Key | Required | Purpose | Get it |
|-----|----------|---------|--------|
| `OPENAI_API_KEY` | ✅ Recommended | GPT-4o for NLP + metadata | [platform.openai.com](https://platform.openai.com/api-keys) |
| `YOUTUBE_API_KEY` | ⚡ Optional | Views, likes, captions | [Google Cloud Console](https://console.cloud.google.com) |

**Without OpenAI key:** The system still works — it falls back to keyword heuristics for genre/tone and regex for metadata. Quality is lower.

**Without YouTube API key:** yt-dlp provides title, description, tags, views, likes, thumbnail — so most fields are still filled.

---

##  Output Structure

```json
{
  "task_id": "abc123def456",
  "youtube_url": "https://youtube.com/watch?v=...",
  "basic_identification": {
    "movie_name": "KGF: Chapter 2",
    "trailer_title": "KGF Chapter 2 Official Trailer",
    "release_year": 2022,
    "languages": ["Kannada", "Hindi"],
    "country_of_origin": "India"
  },
  "creative_credits": {
    "director": "Prashanth Neel",
    "main_cast": ["Yash", "Sanjay Dutt", "Raveena Tandon"],
    "producers": ["Vijay Kiragandur"],
    "production_company": "Hombale Films",
    "music_composer": "Ravi Basrur"
  },
  "content_descriptors": {
    "genres": ["Action", "Crime", "Drama"],
    "subgenre": "Period Action",
    "plot_summary": "Rocky continues his rise to power in the gold mines...",
    "themes": ["power", "revenge", "loyalty", "brotherhood"],
    "tone": "Intense"
  },
  "trailer_specific": {
    "trailer_type": "Official Trailer",
    "duration": 180.5,
    "trailer_release_date": "2022-03-21"
  },
  "audience_classification": {
    "age_rating": "U/A",
    "content_warnings": ["Violence"],
    "target_audience": "Adults 18-40, action film fans"
  },
  "engagement_metadata": {
    "views": 250000000,
    "likes": 4500000,
    "thumbnail_url": "https://..."
  },
  "confidence_scores": {
    "genres": 0.92,
    "language": 0.97,
    "movie_name": 0.95,
    "director": 0.88
  },
  "trailer_score": {
    "overall_score": 84.5,
    "excitement_score": 92.0,
    "clarity_score": 78.0
  },
  "processing_time_seconds": 142.3,
  "errors": []
}
```

---

##  API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/extract` | Submit URL, returns `task_id` |
| `GET`  | `/api/status/{id}` | Poll task status |
| `GET`  | `/api/result/{id}` | Get completed JSON result |
| `GET`  | `/api/stream/{id}` | SSE real-time progress stream |
| `POST` | `/api/batch` | Submit up to 10 URLs at once |
| `GET`  | `/api/export/{id}` | Download result as `.json` |
| `GET`  | `/api/analytics` | Aggregated stats dashboard data |
| `GET`  | `/api/health` | Health check + model status |

---

##  Supported Languages

| Region | Languages |
|--------|-----------|
| **North India** | Hindi, Punjabi, Urdu |
| **South India** | Tamil, Telugu, Malayalam, Kannada |
| **East India**  | Bengali, Odia, Assamese |
| **West India**  | Marathi, Gujarati |
| **International** | English, French, Spanish, Korean, Japanese + more |

Language detection uses **OpenAI Whisper** (primary) + `langdetect` (supplementary).

---

##  Project Structure

```
e:\Video_Extraction\
├── backend/
│   ├── main.py                    # FastAPI app, pipeline orchestration
│   ├── config.py                  # Environment settings (pydantic-settings)
│   ├── models/
│   │   └── schemas.py             # Pydantic output schema
│   ├── agents/
│   │   ├── ingestion_agent.py     # yt-dlp + OpenCV frames
│   │   ├── audio_agent.py         # Whisper STT
│   │   ├── vision_agent.py        # CLIP scene detection
│   │   ├── nlp_agent.py           # GPT-4o content analysis
│   │   ├── metadata_agent.py      # GPT-4o + regex metadata
│   │   └── aggregator_agent.py    # Merge + confidence
│   ├── utils/
│   │   ├── youtube_api.py         # YouTube Data API v3 wrapper
│   │   ├── file_utils.py          # Temp file management
│   │   └── confidence.py          # Confidence scoring
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                # Main app + routing
│   │   ├── index.css              # Design system
│   │   └── components/
│   │       ├── UrlInput.jsx       # URL input + validation
│   │       ├── ProgressTracker.jsx # Live pipeline progress (SSE)
│   │       ├── MetadataDisplay.jsx # 10-tab metadata viewer
│   │       ├── JsonViewer.jsx      # Syntax-highlighted JSON
│   │       ├── ConfidenceBar.jsx   # Colored confidence bars
│   │       ├── BatchProcessor.jsx  # Multi-URL batch
│   │       └── AnalyticsDashboard.jsx # Chart.js analytics
│   └── package.json
├── .env.example                   # Configuration template
└── README.md
```

---

##  Configuration

All settings are in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | `""` | OpenAI API key |
| `YOUTUBE_API_KEY` | `""` | YouTube Data API key |
| `WHISPER_MODEL` | `base` | `tiny/base/small/medium/large` |
| `OPENAI_MODEL` | `gpt-4o` | Any OpenAI chat model |
| `MAX_FRAMES` | `30` | Max frames to sample per video |
| `FRAME_INTERVAL_SECONDS` | `2.5` | Seconds between frames |
| `TEMP_DIR` | `./temp` | Temp file directory |
| `PORT` | `8000` | Backend server port |

---

##  Performance Notes

- **First run**: Whisper (`~150 MB`) and CLIP (`~350 MB`) models download automatically
- **Processing time**: 2–5 min per trailer on CPU (Whisper is the bottleneck)
- **GPU**: Set `CUDA` PyTorch for 3–5× faster Whisper + CLIP
- **Temp files**: Automatically deleted after processing
- **Batch**: Up to 10 URLs processed in parallel background tasks

---

##  Troubleshooting

| Problem | Solution |
|---------|----------|
| `ffmpeg not found` | Install ffmpeg and restart terminal |
| `CUDA out of memory` | Reduce `MAX_FRAMES` or use CPU PyTorch |
| `yt-dlp unable to download` | Update yt-dlp: `pip install -U yt-dlp` |
| `OpenAI API error` | Check API key in `.env`, verify billing |
| `CLIP model download fails` | Check internet, or set `HF_ENDPOINT` env var |
| `Port 8000 in use` | Change `PORT=8001` in `.env` |
