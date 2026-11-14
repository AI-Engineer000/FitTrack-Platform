# 🏋️‍♂️ FitTrack: AI-Powered Fitness Assessment & Athlete Management Platform

FitTrack is a production-ready, multi-tenant web application designed to automate physical fitness testing and athlete management. It uses Computer Vision (YOLO26-Pose) to track body keypoints in real-time, calculate joint angles, count repetitions, and provide instant audio-visual feedback on exercise form.

Built for trainers, academies, and athletes, FitTrack replaces subjective manual counting with objective, data-driven assessments.

## ✨ Key Features

- **Real-Time Pose Estimation:** Tracks 17 body keypoints with confidence filtering using YOLO26-Pose.
- **8 Exercise Analyzers:** Vertical Jump, Broad Jump, Sit-ups, Sit & Reach, Sprint, Medicine Ball, Shuttle Run, and Endurance Run.
- **Smart Form Correction:** Skeleton turns Red/Green based on posture. Includes **Audio Coaching** (Web Speech API) to guide the athlete (e.g., "Go deeper").
- **Biomechanical Analytics:** Live Chart.js time-series graphs showing joint angles and range of motion (ROM).
- **Dual Dashboards (B2B2C):**
  - *Trainer Portal:* Manage athletes, view team analytics, and download PDF reports.
  - *Athlete Portal:* View personal progress, team leaderboard rank, BMI, and change passwords.
- **Automated PDF Reports:** Generates premium, sports-academy style PDF report cards using `xhtml2pdf`.
- **Asynchronous Processing:** Uses Celery + Redis to offload heavy AI inference, ensuring the web server never freezes.
- **Strict Security:** Multi-tenant data isolation. 17/17 Access Control tests passed (zero cross-trainer data leakage).

## 🛠️ Tech Stack

- **Backend:** Django (Python)
- **AI / Vision:** Ultralytics YOLO26-Pose, OpenCV, NumPy
- **Async Queue:** Celery, Redis
- **Frontend:** HTML5, CSS3, Vanilla JavaScript, Chart.js
- **Database:** SQLite (Local) / PostgreSQL (Production)
- **Reporting:** xhtml2pdf

## 🚀 Local Setup Guide

### 1. Clone the Repository
```bash
git clone https://github.com/AI-Engineer000/FitTrack-Platform.git
cd FitTrack-Platform
