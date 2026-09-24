import json
from flask import Blueprint, request, jsonify
from datetime import datetime
from models import db, Exam, ExamEnrollment, ExamSession, Violation, User

exam_bp = Blueprint('exam', __name__)

@exam_bp.route('/create', methods=['POST'])
def create_exam():
    data = request.get_json()
    exam = Exam(
        course_code=data['course_code'],
        course_title=data['course_title'],
        start_time=datetime.fromisoformat(data['start_time']),
        time_hours=data['time_hours'],
        created_by=data.get('admin_id')
    )
    db.session.add(exam)
    db.session.commit()

    for student_id in data['student_ids']:
        db.session.add(ExamEnrollment(exam_id=exam.id, student_id=student_id))
    db.session.commit()

    return jsonify({"status": "success", "exam_id": exam.id}), 201


@exam_bp.route('/start-session', methods=['POST'])
def start_session():
    data = request.get_json()
    session = ExamSession(exam_id=data['exam_id'], student_id=data['student_id'])
    db.session.add(session)
    db.session.commit()
    return jsonify({"status": "success", "session_id": session.id})


@exam_bp.route('/end-session/<int:session_id>', methods=['POST'])
def end_session(session_id):
    session = ExamSession.query.get_or_404(session_id)
    session.end_time = datetime.utcnow()
    session.status = 'completed'
    db.session.commit()
    return jsonify({"status": "success"})


@exam_bp.route('/my-exams/<student_id>')
def my_exams(student_id):
    enrollments = ExamEnrollment.query.filter_by(student_id=student_id).all()
    if not enrollments:
        return jsonify([])

    exam_ids = [e.exam_id for e in enrollments]
    exams = Exam.query.filter(Exam.id.in_(exam_ids)).all()
    
    return jsonify([{
        "exam_id": e.id,
        "course_code": e.course_code,
        "course_title": e.course_title,
        "start_time": e.start_time.isoformat(),
        "time_hours": e.time_hours
    } for e in exams])


@exam_bp.route('/admin/sessions')
def admin_sessions():
    sessions = ExamSession.query.order_by(ExamSession.start_time.desc()).all()

    result = []
    for s in sessions:
        student = User.query.filter_by(student_id=s.student_id).first()
        violation_count = Violation.query.filter_by(session_id=s.id).count()

        result.append({
            "session_id": s.id,
            "exam_id": s.exam_id,
            "student_id": s.student_id,
            "student_name": student.name if student else "Unknown",
            "student_email": student.email if student else "Unknown",
            "status": s.status,
            "start_time": s.start_time.isoformat(),
            "end_time": s.end_time.isoformat() if s.end_time else None,
            "violation_count": violation_count
        })

    return jsonify(result)


@exam_bp.route('/admin/session/<int:session_id>/violations')
def admin_session_violations(session_id):
    violations = Violation.query.filter_by(session_id=session_id).order_by(Violation.timestamp).all()

    result = []
    for v in violations:
        metadata = {}
        if v.clip_path:
            metadata_path = f"{v.clip_path}.json"
            try:
                with open(metadata_path, 'r', encoding='utf-8') as metadata_file:
                    metadata = json.load(metadata_file)
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                metadata = {}

        result.append({
            "event_type": v.event_type,
            "severity": v.severity,
            "confidence": v.confidence,
            "timestamp": v.timestamp.strftime("%H:%M:%S"),
            "snapshot_url": f"{request.host_url.rstrip('/')}/{v.snapshot_path}" if v.snapshot_path else None,
            "clip_url": f"{request.host_url.rstrip('/')}/{v.clip_path}" if v.clip_path else None,
            "event_elapsed_ms": metadata.get('event_elapsed_ms'),
            "clip_start_elapsed_ms": metadata.get('clip_start_elapsed_ms'),
            "clip_end_elapsed_ms": metadata.get('clip_end_elapsed_ms'),
            "video_offset_ms": metadata.get('video_offset_ms'),
        })

    return jsonify(result)




@exam_bp.route('/my-exams-detailed/<student_id>')
def my_exams_detailed(student_id):
    enrollments = ExamEnrollment.query.filter_by(student_id=student_id).all()
    exam_ids = [e.exam_id for e in enrollments]
    exams = Exam.query.filter(Exam.id.in_(exam_ids)).all()

    now = datetime.now()
    upcoming = []
    previous = []

    for e in exams:
        session = ExamSession.query.filter_by(exam_id=e.id, student_id=student_id).first()

        exam_data = {
            "exam_id": e.id,
            "course_code": e.course_code,
            "course_title": e.course_title,
            "start_time": e.start_time.isoformat(),
            "time_hours": e.time_hours,
            "session_status": session.status if session else "not_started"
        }

        if session and session.status == "completed":
            previous.append(exam_data)
        elif e.start_time < now and not session:
            previous.append(exam_data)  # exam time passed, never attempted — still "previous"
        else:
            upcoming.append(exam_data)

    return jsonify({"upcoming": upcoming, "previous": previous})