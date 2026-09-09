import random
import cv2
import numpy as np
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from models import db, User
from detection.face_authentication import enroll_from_image, set_signature

auth_bp = Blueprint("auth", __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.form if request.form else request.get_json()

    email = data.get('email')
    password = data.get('password')
    name = data.get('name', '')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email is already registered"}), 400

    # ID/passport photo is now mandatory at registration — this becomes the
    # reference signature that verify.html compares live camera frames
    # against before every exam.
    if 'id_photo' not in request.files:
        return jsonify({"error": "An ID or passport photo is required to register"}), 400

    photo = request.files['id_photo']
    file_bytes = np.frombuffer(photo.read(), np.uint8)
    image_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if image_bgr is None:
        return jsonify({"error": "Could not read the uploaded photo, please try another"}), 400

    signature = enroll_from_image(image_bgr)
    if signature is None:
        return jsonify({"error": "Could not detect a clear face in that photo, please try another"}), 400

    auto_student_id = f"STU-{random.randint(1000, 9999)}"
    hashed_password = generate_password_hash(password)

    id_photo_path = f"static/id_photos/{auto_student_id}.jpg"
    import os
    os.makedirs("static/id_photos", exist_ok=True)
    cv2.imwrite(id_photo_path, image_bgr)

    set_signature(auto_student_id, signature)

    new_user = User(
        name=name,
        email=email,
        password_hash=hashed_password,
        role="student",
        student_id=auto_student_id,
        id_photo_path=id_photo_path
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": f"Account created! Your Student ID is {auto_student_id}",
        "student_id": auto_student_id,
        "face_enrolled": True
    }), 201


@auth_bp.route('/admin-register', methods=['POST'])
def admin_register():
    data = request.form if request.form else request.get_json()

    email = data.get('email')
    password = data.get('password')
    name = data.get('name', '')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email is already registered"}), 400

    new_admin = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
        role="admin"
    )
    db.session.add(new_admin)
    db.session.commit()

    return jsonify({"status": "success", "message": "Admin account created"}), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.form if request.form else request.get_json()

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = create_access_token(identity={
        "id": user.id,
        "role": user.role,
        "student_id": user.student_id
    })

    return jsonify({
        "status": "success",
        "token": token,
        "role": user.role,
        "student_id": user.student_id,
        "user_id": user.id,
        "name": user.name
    }), 200