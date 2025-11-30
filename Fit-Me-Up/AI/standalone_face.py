# standalone_face.py
import sys, cv2, numpy as np, mediapipe as mp

if len(sys.argv) < 2:
    print("Usage: python standalone_face.py <image_path>")
    sys.exit(1)

img_path = sys.argv[1]
bgr = cv2.imread(img_path)
if bgr is None:
    print(f"Failed to read image: {img_path}")
    sys.exit(2)

mp_face_mesh = mp.solutions.face_mesh
rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
h, w = rgb.shape[:2]

with mp_face_mesh.FaceMesh(static_image_mode=True, refine_landmarks=True,
                           max_num_faces=1, min_detection_confidence=0.5) as mesh:
    res = mesh.process(rgb)

if not res.multi_face_landmarks:
    print({"face_shape":"unknown", "debug":"no_face"})
    sys.exit(0)

lm = res.multi_face_landmarks[0].landmark
def P(idx):
    p = lm[idx]
    return np.array([p.x * w, p.y * h])

left_face, right_face = P(234), P(454)
face_width = np.linalg.norm(right_face - left_face)
forehead, chin = P(10), P(152)
face_length = np.linalg.norm(chin - forehead)
brow_left, brow_right = P(70), P(300)
forehead_width = np.linalg.norm(brow_right - brow_left)
jaw_width = face_width * 0.9

ratio_len_width = face_length / (face_width + 1e-6)
ratio_jaw_forehead = jaw_width / (forehead_width + 1e-6)

fs = "oval"
if ratio_len_width <= 1.1 and 0.95 <= ratio_jaw_forehead <= 1.05:
    fs = "round"
elif ratio_len_width <= 1.15 and ratio_jaw_forehead > 1.05:
    fs = "square"
elif ratio_len_width > 1.55:
    fs = "oblong"
elif ratio_jaw_forehead < 0.9:
    fs = "heart"

print({
  "face_shape": fs,
  "metrics": {
    "face_width": float(face_width),
    "face_length": float(face_length),
    "forehead_width": float(forehead_width),
    "ratio_len_width": float(ratio_len_width),
    "ratio_jaw_forehead": float(ratio_jaw_forehead),
  },
  "debug":"ok"
})
