import cv2
import os
import urllib.request
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# The model file gets downloaded once and cached locally next to this file
MODEL_PATH = os.path.join(os.path.dirname(__file__), "face_landmarker.task")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

if not os.path.exists(MODEL_PATH):
    print("Downloading face landmark model (first run only)...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    num_faces=2,
    running_mode=vision.RunningMode.IMAGE
)
landmarker = vision.FaceLandmarker.create_from_options(options)


class _FaceWrapper:
    """Mimics the shape of the old mediapipe.solutions face object,
    so engine.py and head_movement.py don't need to change at all —
    they access landmarks via face.landmark, same as before."""
    def __init__(self, landmark_list):
        self.landmark = landmark_list


def detect_faces(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    result = landmarker.detect(mp_image)

    faces_raw = result.face_landmarks
    num_faces = len(faces_raw)
    faces = [_FaceWrapper(face_landmarks) for face_landmarks in faces_raw]

    return num_faces, faces