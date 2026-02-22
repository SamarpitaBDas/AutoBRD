# BRD Generator – AI-Powered Business Requirements Document System

An intelligent Business Requirements Document (BRD) Generator built with Django, Machine Learning, and a PyQt frontend.

The system extracts, classifies, and organizes business requirements from unstructured sources such as emails, meeting notes, and documents into structured BRDs.

---

# Video Demo
https://youtu.be/gSs_GQdMHMs

---

# Project Overview

This system automates the process of:

- Extracting requirements from raw text sources
- Classifying them into:
  - Functional Requirements
  - Business Requirements
  - Non-Functional Requirements
- Assigning priorities (High / Medium / Low)
- Identifying stakeholders
- Generating structured BRD documents

It significantly reduces manual documentation effort in software projects.

---

# Architecture

Frontend: **PyQt Desktop Application**  
Backend: **Django + Django REST Framework**  
ML Layer: **Scikit-learn / Transformers / Sentence-Transformers**  
Async Processing (Optional): **Celery + Redis**

```

PyQt Frontend  →  Django REST API  →  ML Processing Engine
↓
SQLite Database

```

---

# Key Features

✅ Automated requirement extraction  
✅ Requirement classification (FR / BR / NFR)  
✅ Stakeholder identification  
✅ Priority detection  
✅ BRD document generation  
✅ Admin dashboard  
✅ Background ML processing (Celery optional)  
✅ REST API architecture  

---

# Tech Stack

- Python
- Django 4.2
- Django REST Framework
- Celery
- Redis
- Scikit-learn
- Transformers
- Sentence-Transformers
- PyQt
- SQLite

---

# Installation

See full setup instructions here:

**SETUP.md**

Quick start:

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate (Windows)
pip install -r requirements.txt
cd backend
python manage.py migrate
python manage.py runserver
````

Then run frontend:

```bash
python frontend/main.py
```

---

# 📁 Project Structure

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
├── requirements.txt
├── frontend_requirements.txt
├── SETUP.md
└── README.md
```

---

# Example Output

The system generates structured BRDs including:

* Executive Summary
* Business Objectives
* Stakeholder Analysis
* Functional Requirements
* Non-Functional Requirements

Automatically extracted from raw stakeholder communications.

---

# Notes

* ML models may download during first execution
* Initial run may take several minutes

---

# Assets

UI icons sourced from:
[https://remixicon.com/](https://remixicon.com/)
