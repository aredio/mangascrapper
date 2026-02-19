# MangaDex Chapter Downloader

A Python project to handle MangaDex Chapter UUIDs and organize chapter downloads.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the main script:
```bash
python main.py
```

## Project Structure

```
.
├── main.py          # Main application logic
├── requirements.txt # Python dependencies
├── downloads/       # Base directory for chapter downloads
└── README.md        # This file
```

## Usage

The `MangaDexDownloader` class handles MangaDex Chapter UUIDs and creates folders for each chapter:

```python
from main import MangaDexDownloader

downloader = MangaDexDownloader()
chapter_folder = downloader.handle_chapter("d9f90199-79fb-403f-a313-a054f1a77b0c")
```

This will create a folder `downloads/d9f90199-79fb-403f-a313-a054f1a77b0c/` for the chapter.
