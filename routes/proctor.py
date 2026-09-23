import cv2
import numpy as np
import base64
import os
import json
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify
from models import db, Violation, ExamSession
from detection.engine import ProctoringEngine
from werkzeug.utils import secure_filename
from detection.face_detection import detect_faces
from detection.face_authentication import (
    enroll_from_frames, get_or_load_signature, MISMATCH_DISTANCE_THRESHOLD
)
from models import VerificationAttempt

identity_buffers = {}  # session_id -> list of landmark objects, collected live

proctor_bp = Blueprint('proctor', __name__)

active_engines = {}


@proctor_bp.route('/scan-frame', methods=['POST'])
def scan_frame():
    data = request.get_json()
    if not data or 'session_id' not in data or 'image' not in data:
        return jsonify({"error": "Missing session_id or image payload"}), 400

    try:
        session_id = int(data['session_id'])
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid session_id format"}), 400

    if session_id not in active_engines:
        active_engines[session_id] = ProctoringEngine()
    engine = active_engines[session_id]

    try:
        image_b64 = data['image'].split(',')[1] if ',' in data['image'] else data['image']
        nparr = np.frombuffer(base64.b64decode(image_b64), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return jsonify({"error": "Failed to decode frame"}), 400

        result = engine.process_frame(frame)

        logged_count = 0
        new_violation_ids = []

        if result.get('events'):
            for event in result['events']:
                event_name = event.get('event_type') if isinstance(event, dict) else str(event)
                severity_val = event.get('severity', 'high') if isinstance(event, dict) else 'high'
                confidence_val = event.get('confidence', None) if isinstance(event, dict) else None

                if event_name:
                    os.makedirs("static/violation_snapshots", exist_ok=True)
                    snapshot_filename = f"{session_id}_{event_name}_{int(datetime.utcnow().timestamp())}.jpg"
                    snapshot_path = f"static/violation_snapshots/{snapshot_filename}"
                    cv2.imwrite(snapshot_path, frame)

                    violation = Violation(
                        session_id=session_id,
                        event_type=str(event_name).upper(),
                        severity=severity_val,
                        confidence=confidence_val,
                        snapshot_path=snapshot_path
                    )
                    db.session.add(violation)
                    db.session.flush()
                    new_violation_ids.append({"id": violation.id, "event_type": violation.event_type})
                    logged_count += 1

            db.session.commit()
            print(f" SUCCESS: Saved {logged_count} violations for Session ID {session_id}")

        return jsonify({
            "face_count": result.get('face_count', 0),
            "events_logged": logged_count,
            "calibrating": result.get('calibrating', False),
            "calibration_done": result.get('calibration_done', False),
            "baseline_ready": result.get('baseline_ready', False),
            "new_violations": new_violation_ids
        })

    except Exception as e:
        db.session.rollback()
        print(f" ERROR inside /scan-frame: {str(e)}")
        return jsonify({"error": f"Frame scanning failed: {str(e)}"}), 500


@proctor_bp.route('/calibrate', methods=['POST'])
def start_calibration():
    data = request.get_json()
    if not data or 'session_id' not in data:
        return jsonify({"error": "Missing session_id"}), 400

    try:
        session_id = int(data['session_id'])
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid session_id"}), 400

    if session_id not in active_engines:
        active_engines[session_id] = ProctoringEngine()
    engine = active_engines[session_id]

    engine.start_calibration()
    return jsonify({"status": "calibration_started", "session_id": session_id})


@proctor_bp.route('/check-lighting', methods=['POST'])
def check_lighting():
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({"error": "Missing image"}), 400

    try:
        image_b64 = data['image'].split(',')[1] if ',' in data['image'] else data['image']
        nparr = np.frombuffer(base64.b64decode(image_b64), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return jsonify({"error": "Failed to decode frame"}), 400

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))

        MIN_BRIGHTNESS = 60

        return jsonify({
            "brightness": round(brightness, 1),
            "well_lit": brightness >= MIN_BRIGHTNESS
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@proctor_bp.route('/flag', methods=['POST'])
def log_client_flag():
    data = request.get_json()
    if not data or 'session_id' not in data or 'event_type' not in data:
        return jsonify({"error": "Missing session_id or event_type"}), 400

    try:
        session_id = int(data['session_id'])
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid session_id"}), 400

    violation = Violation(
        session_id=session_id,
        event_type=data['event_type'].upper(),
        severity=data.get('severity', 'high'),
        confidence=None
    )
    db.session.add(violation)
    db.session.commit()

    print(f" SUCCESS: Logged client-side flag '{data['event_type']}' for session {session_id}")

    return jsonify({"status": "logged"}), 201


@proctor_bp.route('/upload-clip/<int:violation_id>', methods=['POST'])
def upload_clip(violation_id):
    violation = Violation.query.get_or_404(violation_id)

    if 'clip' not in request.files:
        return jsonify({"error": "No clip file provided"}), 400

    clip_file = request.files['clip']
    if not clip_file or clip_file.filename == '':
        return jsonify({"error": "No clip file selected"}), 400

    clip_bytes = clip_file.read()
    if len(clip_bytes) == 0:
        return jsonify({"error": "The uploaded clip is empty"}), 400

    mime_type = (request.form.get('mime_type') or clip_file.mimetype or 'video/webm').lower()
    if not mime_type.startswith('video/') and mime_type != 'application/octet-stream':
        return jsonify({"error": "Unsupported clip MIME type"}), 400

    safe_event_name = secure_filename((violation.event_type or 'incident').replace(' ', '_')) or 'incident'
    requested_name = secure_filename(clip_file.filename)
    requested_ext = os.path.splitext(requested_name)[1].lower()

    if requested_ext in {'.webm', '.mp4'}:
        extension = requested_ext
    elif 'mp4' in mime_type:
        extension = '.mp4'
    else:
        extension = '.webm'

    unique_suffix = uuid.uuid4().hex[:8]
    filename = f"violation_{violation_id}_{safe_event_name}_{unique_suffix}{extension}"
    save_dir = os.path.join("static", "violation_clips")
    os.makedirs(save_dir, exist_ok=True)

    save_path = os.path.join(save_dir, filename)
    clip_file.stream.seek(0)
    clip_file.save(save_path)

    if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
        return jsonify({"error": "Clip upload failed during storage"}), 500

    rel_path = save_path.replace('\\', '/')
    violation.clip_path = rel_path

    event_elapsed_ms = request.form.get('event_elapsed_ms')
    clip_start_elapsed_ms = request.form.get('clip_start_elapsed_ms')
    clip_end_elapsed_ms = request.form.get('clip_end_elapsed_ms')

    metadata = {
        "violation_id": violation_id,
        "event_type": violation.event_type,
        "event_elapsed_ms": int(float(event_elapsed_ms)) if event_elapsed_ms not in (None, '') else None,
        "clip_start_elapsed_ms": int(float(clip_start_elapsed_ms)) if clip_start_elapsed_ms not in (None, '') else None,
        "clip_end_elapsed_ms": int(float(clip_end_elapsed_ms)) if clip_end_elapsed_ms not in (None, '') else None,
        "mime_type": mime_type,
        "created_at": datetime.utcnow().isoformat() + 'Z'
    }

    metadata_path = save_path + '.json'
    with open(metadata_path, 'w', encoding='utf-8') as metadata_file:
        json.dump(metadata, metadata_file)

    db.session.commit()

    return jsonify({
        "status": "success",
        "violation_id": violation.id,
        "clip_path": rel_path,
        "mime_type": mime_type,
        "event_elapsed_ms": metadata["event_elapsed_ms"],
        "clip_start_elapsed_ms": metadata["clip_start_elapsed_ms"],
        "clip_end_elapsed_ms": metadata["clip_end_elapsed_ms"],
        "metadata_path": metadata_path.replace('\\', '/')
    })




@proctor_bp.route('/verify-identity', methods=['POST'])
def verify_identity():
    data = request.get_json()
    if not data or 'session_id' not in data or 'student_id' not in data or 'image' not in data:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        session_id = int(data['session_id'])
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid session_id"}), 400

    student_id = data['student_id']

    enrolled_signature = get_or_load_signature(student_id)
    if enrolled_signature is None:
        return jsonify({"status": "not_enrolled", "message": "No face on file for this student"}), 400

    image_b64 = data['image'].split(',')[1] if ',' in data['image'] else data['image']
    nparr = np.frombuffer(base64.b64decode(image_b64), np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        return jsonify({"error": "Failed to decode frame"}), 400

    num_faces, faces = detect_faces(frame)

    if num_faces != 1:
        return jsonify({"status": "retry", "message": "Position your face clearly in view"})

    if session_id not in identity_buffers:
        identity_buffers[session_id] = []
    identity_buffers[session_id].append(faces[0])

    MIN_SAMPLES = 5
    if len(identity_buffers[session_id]) < MIN_SAMPLES:
        return jsonify({"status": "collecting", "progress": len(identity_buffers[session_id]), "needed": MIN_SAMPLES})

    frame_height, frame_width = frame.shape[:2]
    pairs = [(None, lm) for lm in identity_buffers[session_id]]
    live_signature = enroll_from_frames(pairs, frame_width, frame_height)
    identity_buffers[session_id] = []  # reset for next time

    if live_signature is None:
        return jsonify({"status": "retry", "message": "Could not get a clear reading, try again"})

    distance = float(np.linalg.norm(live_signature - enrolled_signature))
    passed = distance <= MISMATCH_DISTANCE_THRESHOLD

    attempt = VerificationAttempt(
        student_id=student_id,
        session_id=session_id,
        match_distance=distance,
        passed=passed
    )
    db.session.add(attempt)
    db.session.commit()

    return jsonify({"status": "done", "passed": passed, "distance": round(distance, 3)})