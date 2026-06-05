# Hackathon Alert System

## Overview

Automated pipeline that fetches hackathons from Devpost,
deduplicates them using SQLite,
and delivers alerts through Telegram.

## Architecture

```mermaid
flowchart TD

	A[Scheduler] --> B[Fetchers]

	B --> C[Devpost API]
	B --> D[Devfolio Scraper]
	B --> E[Unstop Scraper]

	B --> F[Normalization Engine]

	F --> G[(SQLite Database)]

	G --> H[User Filters]

	H --> I[Telegram Bot]

	I --> J[Users]
```

<img width="738" height="1541" alt="WhatsApp Image 2026-06-05 at 1 02 04 PM" src="https://github.com/user-attachments/assets/c02490ea-c185-4a0f-ac21-e20ff313c088" />
<img width="738" height="1538" alt="WhatsApp Image 2026-06-05 at 1 01 49 PM" src="https://github.com/user-attachments/assets/05ba985b-717c-4823-afd0-55b4ffbd4135" />
<img width="1920" height="1080" alt="Screenshot 2026-06-01 114132" src="https://github.com/user-attachments/assets/ab98edfa-af84-4eed-b0fd-d1c82ce08ace" />
=======

## Features

- Automated ingestion
- Persistent deduplication
- Telegram notifications
- Scheduled execution
- Modular fetchers

## Tech Stack

- Python
- Requests
- SQLite
- Telegram Bot API
- Schedule

## Run

Install dependencies and start the scheduler:

```bash
pip install -r requirements.txt
python scheduler.py
```
