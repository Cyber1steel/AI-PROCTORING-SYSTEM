#

# importing the tools we need 
from flask import Flask, render_template
from flask_socketio import SocketIO
from flask_jwt_extended import JWTManager
from config import Config
from models import db

# web app creation and connection
app = Flask(__name__)
app.config.from_object(Config)

# connecting database 
db.init_app(app)

# login tokens
jwt = JWTManager(app)

# used for real time messaging (live updating the admin dashboard)
socketio = SocketIO(app, cors_allowed_origins="*")

# Register Blueprints
from routes.auth import auth_bp
app.register_blueprint(auth_bp, url_prefix='/api/auth')

from routes.exam import exam_bp
app.register_blueprint(exam_bp, url_prefix='/api/exam')

from routes.proctor import proctor_bp
app.register_blueprint(proctor_bp, url_prefix='/api/proctor')

# Connecting the main pages of the site
@app.route("/")
def student_home():
    return render_template("Student_login.html")

@app.route("/my-exams")
def my_exams_page():
    return render_template("my_exams.html")

@app.route("/register")
def register_page():
    return render_template("register.html")

@app.route("/admin")
def admin_home():
    return render_template("admin_dashboard.html")

@app.route("/adlogin")
def admin_login():
    return render_template("admin_login.html")

@app.route("/adreg")
def admin_reg():
    return render_template("admin_register.html")

@app.route("/admin/register")
def admin_register():
    return render_template("admin_register.html")

@app.route("/demo")
@app.route("/index.html")
def webcam_demo():
    return render_template("index.html")

@app.route('/verify')
def verify_page():
    return render_template('verify.html')

@app.route('/recording-test')
def recording_test_page():
    return render_template('recording-test.html')


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    # Runs using SocketIO server for real-time webcams & flags
    socketio.run(app, host="0.0.0.0", debug=True, port=5000)