# BRD Generator – Setup Guide

A Django + ML-powered Business Requirements Document (BRD) Generator with optional Celery background processing and a PyQt frontend.

---

# 🚀 Quick Setup (Development Mode)

## 1️⃣ Prerequisites

Make sure you have:

* Python **3.8+**
* pip
* Redis (optional, for Celery)

Check:

```bash
python --version
pip --version
```

---

# 📦 Installation

## Option A — Automated (Linux/Mac)

```bash
chmod +x setup.sh
./setup.sh
```

## Option B — Automated (Windows)

```cmd
setup.bat
```

## Option C — Manual Setup

### Step 1 — Create Virtual Environment

```bash
python -m venv venv
```

### Step 2 — Activate

**Linux / Mac**

```bash
source venv/bin/activate
```

**Windows**

```cmd
venv\Scripts\activate
```

---

### Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
pip install -r frontend_requirements.txt
```

First installation may take time (ML models + torch).

---

### Step 4 — Setup Database

```bash
cd backend
python manage.py migrate
```

---

### Step 5 — Configure Environment Variables

Copy environment template:

```bash
cp .env.example .env
```

Edit `.env` if needed.

---

# Running the Application

## Terminal 1 — Start Django Backend

```bash
cd backend
python manage.py runserver
```

Backend runs at:

```
http://localhost:8000
```

---

## Terminal 2 — Start Frontend (PyQt)

```bash
python frontend/main.py
```

---

# Optional: Enable Background Processing (Celery)

If using background ML processing:

### Terminal 3 — Start Redis

```bash
redis-server
```

### Terminal 4 — Start Celery Worker

```bash
cd backend
celery -A brd_backend worker --loglevel=info
```

---

# Common Commands

### Create Admin User

```bash
python manage.py createsuperuser
```

### Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Run on Different Port

```bash
python manage.py runserver 8001
```

---

# First Run Notes

* ML models may download on first execution (2–3 GB)
* Initial startup may take 5–10 minutes
* Subsequent runs are much faster (cached locally)

---

# Project Structure

```
brd_generator_project/
├── backend/
│   ├── manage.py
│   ├── brd_backend/
│   ├── api/
│   ├── ml_models/
│   └── integrations/
├── frontend/
│   └── main.py
├── .env
├── requirements.txt
├── frontend_requirements.txt
└── README.md
```

---

# Troubleshooting

### Port Already in Use

```bash
python manage.py runserver 8001
```

### Module Not Found

```bash
pip install -r requirements.txt
```

### Database Locked

Stop all Django processes and restart.

---

# Sources
image assets from https://remixicon.com/
