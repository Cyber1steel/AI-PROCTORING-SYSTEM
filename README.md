# AI-Powered Online Examination Proctoring System

An AI-assisted proctoring web application that monitors students during online exams using real-time computer vision (MediaPipe) for behavioral detection, geometric face-matching for identity verification, and a Flask backend for exam management, violation logging, and admin review.

Built as a data science project demonstrating full-stack integration of a Python/Flask backend, a SQLite database, browser-based computer vision (client capture + server-side inference), and a real-time admin review dashboard.

---

## Features

### Student Side
- **Registration** with an uploaded ID photo, used to enroll a geometric facial signature.
- **Login** with hashed-password authentication and JWT session tokens.
- **My Exams dashboard** shows exams split into *Upcoming* and *Previous*, with student name greeting.
- **Live exam monitoring page**:
  - Webcam and microphone access, with a live camera preview.
  - **Identity verification** before monitoring begins a live face capture is compared against the signature enrolled at registration.
  - **Lighting check** warns the student if the room is too dark for reliable detection.
  - **Calibration**  establishes a baseline head-pose reading before head-movement detection activates.
  - **Real-time behavioral monitoring**, flagging:
    - Prolonged absence (no face detected)
    - Multiple faces in frame
    - Head movement / looking away (post-calibration)
    - Identity mismatch (post-verification)
    - Tab switching / window minimizing
    - Camera disconnection or interruption
  - **Incident video clips**  a rolling buffer captures a short clip (before + after) automatically whenever a violation fires, in addition to a still snapshot.

### Admin Side
- **Registration and login**, separate role from students, same authentication system.
- **Create Exam** course code/title, scheduled start time, duration, and a list of enrolled student IDs.
- **Review Exams** a searchable, sortable list of every exam session, showing student name/ID/email and flag counts.
- **Per-student violation review** expandable view of every flag for a session, including timestamp, confidence score, snapshot image, and incident video clip.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask, Flask-SQLAlchemy, Flask-SocketIO, Flask-JWT-Extended |
| Database | SQLite |
| Computer Vision | MediaPipe (Face Landmarker / Face Mesh), OpenCV |
| Frontend | HTML, CSS, vanilla JavaScript |
| Auth | Werkzeug password hashing, JWT tokens |
| Real-time updates | Flask-SocketIO (WebSockets) |

---

## Project Structure

```
ai-proctoring-system/
├── app.py                      # Flask entry point, route registration
├── config.py                   # App configuration (secrets, database URI)
├── models.py                   # SQLAlchemy database models
├── routes/
│   ├── auth.py                 # Signup, login, admin registration
│   ├── exam.py                 # Exam creation, sessions, admin review endpoints
│   └── proctor.py              # Frame scanning, calibration, flags, clip uploads
├── detection/
│   ├── engine.py                # ProctoringEngine — orchestrates all detectors
│   ├── face_detection.py        # MediaPipe face landmark detection wrapper
│   ├── absence_detection.py     # Absence detection logic
│   ├── multiple_faces.py        # Multiple-face detection logic
│   ├── head_movement.py         # Calibrated head-pose deviation detection
│   └── face_authentication.py   # Geometric-ratio face signature enrollment/verification
├── templates/                   # HTML pages (student & admin)
├── static/
│   ├── css/                     # Stylesheets
│   ├── js/                      # (if any standalone scripts)
│   ├── id_photos/               # Uploaded student ID photos
│   ├── violation_snapshots/     # Still images captured per violation
│   ├── violation_clips/         # Short video clips captured per violation
│   └── recordings/              # Full session recordings (if implemented)
├── face_signatures/             # Persisted per-student facial signature files (.npy)
├── instance/
│   └── proctoring.db            # SQLite database (auto-created by Flask)
└── requirements.txt
```

---

## Database Schema (Overview)

- **User** — students and admins (role field), credentials, optional face signature reference.
- **Exam** — course code/title, scheduled start, duration, created-by admin.
- **ExamEnrollment** — which students are enrolled in which exam.
- **ExamSession** — one row per student per exam attempt (start/end time, status, recordings).
- **VerificationAttempt** — logs of each identity verification check (distance score, pass/fail).
- **Violation** — every flagged incident (type, severity, confidence, snapshot path, clip path, timestamp), linked to a session.

---

## Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/YOUR-USERNAME/ai-proctoring-system.git
cd ai-proctoring-system
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv
# Windows:
venv\Scripts\Activate.ps1
# Mac/Linux:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

> **Note:** `mediapipe` requires a compatible Python version. If installation issues occur with `face_recognition`/`dlib` (used only if biometric ID-document verification is extended further), see the Troubleshooting section below.

### 4. Run the application
```bash
python app.py
```

The app will be available at `http://127.0.0.1:5000`.

- Student login/registration: `/` and `/register`
- Admin login/registration: `/adlogin` and `/admin/register`
- Admin dashboard: `/admin`

---

## Known Limitations

- **Face authentication** uses a lightweight geometric-ratio comparison (MediaPipe landmark distances), not a trained deep-learning face embedding. This is intentionally a "catches an obvious swap" check, not a high-confidence biometric system — flagged for human review rather than used to auto-block an exam.
- **Camera/microphone access requires a secure context.** This works on `localhost`/`127.0.0.1` but will not prompt for permission over a plain `http://` connection from another device on the network — a real limitation of browser security policy, not the app itself.
- **Head-pose detection can be confused with absence** at extreme head-turn angles, since the underlying face-mesh model may lose tracking entirely at a profile view.

## Future work
1. Snapshots of tab switched too so model flags and also displays the tab student switched to
2. Liveness check 
3. Change exam creation method, to allow admin create exam and then students register for the exam and a lit of all registered students and their ID's be sent to the admin dashboard

## Excluding Files from Git

Not everything in this project should be committed — some folders contain regenerable data, local secrets, or student data that shouldn't live in version control. See `.gitignore` below.


## License / Academic Context

Built as a course/personal project. Not intended for production deployment without further security hardening (see Known Limitations).
