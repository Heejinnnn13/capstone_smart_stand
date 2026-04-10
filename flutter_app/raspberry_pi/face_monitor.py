# -*- coding: utf-8 -*-
"""
face_monitor.py
---------------
MediaPipe Face Mesh 기반 집중도 모니터링 모듈.

감지 항목:
  - absent     : 얼굴 없음 (자리이탈)
  - drowsy     : 졸음 1단계 — 눈 감김 TD(1s) 이상
  - sleep      : 졸음 2단계 — 눈 감김 TS(2s) 이상
  - distracted : 딴짓 (yaw 또는 pitch 과도)
  - focused    : 정상

집중도:
  - 눈깜빡임 BPM 기반 (WARMUP_SECONDS 이후 유효)
  - blink/min 이 0 이면 100%, NORMAL_BPM 이상이면 0%

조명 ON  → start()
조명 OFF → stop()
누적 시간 → get_stats() 로 조회
"""

import time
import threading
import cv2
import mediapipe as mp
import numpy as np

# ───────────────────────────── 상수 ─────────────────────────────
EAR_THRESHOLD   = 0.22   # 이 값 이하면 눈 감김
TD              = 1.0    # 졸음 1단계 임계 (초)
TS              = 2.0    # 졸음 2단계 임계 (초)
YAW_THRESHOLD   = 25     # 좌우 고개 회전 한계 (도)
PITCH_THRESHOLD = 20     # 상하 고개 회전 한계 (도)
NORMAL_BPM      = 17.5   # 정상 눈깜빡임 횟수/분
WARMUP_SECONDS  = 30     # 집중도 계산 워밍업 시간 (초)

# EAR 계산에 쓸 눈 랜드마크 인덱스 (MediaPipe Face Mesh 468점 기준)
LEFT_EYE  = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33,  160, 158, 133, 153, 144]

# 얼굴 방향 추정용 랜드마크 인덱스
NOSE_TIP    = 1
CHIN        = 152
LEFT_EYE_L  = 263
RIGHT_EYE_R = 33
LEFT_MOUTH  = 287
RIGHT_MOUTH = 57


# ───────────────────────────── 유틸 함수 ─────────────────────────────
def _ear(landmarks, indices, w, h):
    """Eye Aspect Ratio 계산"""
    pts = np.array([[landmarks[i].x * w, landmarks[i].y * h] for i in indices])
    v1 = np.linalg.norm(pts[1] - pts[5])
    v2 = np.linalg.norm(pts[2] - pts[4])
    ho = np.linalg.norm(pts[0] - pts[3])
    return (v1 + v2) / (2.0 * ho + 1e-6)


def _head_pose(landmarks, w, h):
    """
    간이 head pose 추정 → (yaw_deg, pitch_deg) 반환.
    solvePnP 대신 랜드마크 비율로 빠르게 계산.
    """
    def pt(idx):
        return np.array([landmarks[idx].x * w, landmarks[idx].y * h])

    nose   = pt(NOSE_TIP)
    chin   = pt(CHIN)
    l_eye  = pt(LEFT_EYE_L)
    r_eye  = pt(RIGHT_EYE_R)
    l_mouth = pt(LEFT_MOUTH)
    r_mouth = pt(RIGHT_MOUTH)

    face_w = np.linalg.norm(l_eye - r_eye) + 1e-6
    face_h = np.linalg.norm(chin - ((l_eye + r_eye) / 2)) + 1e-6

    mid_eye    = (l_eye + r_eye) / 2
    nose_off_x = (nose[0] - mid_eye[0]) / face_w
    yaw_deg    = nose_off_x * 90

    nose_off_y = (nose[1] - mid_eye[1]) / face_h
    pitch_deg  = (nose_off_y - 0.35) * 120

    return float(yaw_deg), float(pitch_deg)


def _find_usb_camera(max_index=10):
    """사용 가능한 USB 카메라 인덱스를 자동으로 탐색"""
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
        if cap.isOpened():
            ret, _ = cap.read()
            cap.release()
            if ret:
                print(f"[FACE] USB 카메라 발견: /dev/video{idx} (index={idx})", flush=True)
                return idx
    return None


def _draw_overlay(image, state, status_text, status_color, drowsy_level,
                  avg_ear, closed_time, concentration, elapsed,
                  blink_count, yaw, pitch):
    """cv2 창에 상태 정보 오버레이"""
    h, w = image.shape[:2]

    # 상단 상태 바
    cv2.rectangle(image, (0, 0), (w, 50), status_color, -1)
    text_size = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0]
    text_x = (w - text_size[0]) // 2
    cv2.putText(image, status_text,
                (text_x, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    # EAR
    ear_color = (0, 0, 255) if avg_ear < EAR_THRESHOLD else (0, 255, 0)
    cv2.putText(image, f'EAR: {avg_ear:.2f}',
                (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, ear_color, 2)

    # 눈 감긴 시간
    if closed_time > 0:
        cv2.putText(image, f'Closed: {closed_time:.2f}s  (>{TD}s DROWSY / >{TS}s SLEEP)',
                    (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 140, 255), 2)

    # 집중도 바
    if concentration < 0:
        remaining = max(0, int(WARMUP_SECONDS - elapsed))
        cv2.putText(image, f'Concentration: measuring... ({remaining}s)',
                    (20, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 2)
    else:
        bar_color = (0, 200, 100) if concentration > 50 else (0, 100, 255)
        cv2.rectangle(image, (20, 120), (20 + concentration * 2, 140), bar_color, -1)
        cv2.rectangle(image, (20, 120), (220, 140), (200, 200, 200), 1)
        cv2.putText(image, f'Concentration: {concentration}%',
                    (20, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # BPM / 경과 시간
    elapsed_min = max(elapsed / 60.0, 0.01)
    current_bpm = blink_count / elapsed_min
    cv2.putText(image, f'Blink/min: {current_bpm:.1f}  (Normal: {NORMAL_BPM})',
                (20, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    cv2.putText(image, f'Time: {int(elapsed)}s  Blinks: {blink_count}',
                (20, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # Yaw / Pitch
    yaw_color   = (0, 0, 255) if abs(yaw)   > YAW_THRESHOLD   else (200, 200, 200)
    pitch_color = (0, 0, 255) if abs(pitch) > PITCH_THRESHOLD else (200, 200, 200)
    cv2.putText(image, f'Yaw: {yaw:.1f}',
                (20, 235), cv2.FONT_HERSHEY_SIMPLEX, 0.5, yaw_color, 1)
    cv2.putText(image, f'Pitch: {pitch:.1f}',
                (20, 258), cv2.FONT_HERSHEY_SIMPLEX, 0.5, pitch_color, 1)

    # 졸음 테두리 경고
    if drowsy_level == 1:
        cv2.rectangle(image, (0, 0), (w - 1, h - 1), (0, 0, 255), 6)
    elif drowsy_level >= 2:
        cv2.rectangle(image, (0, 0), (w - 1, h - 1), (0, 0, 180), 12)


# ───────────────────────────── 메인 클래스 ─────────────────────────────
class FaceMonitor:
    """
    사용법:
        monitor = FaceMonitor(shared_state)
        monitor.start()    # 조명 ON 시 호출
        monitor.stop()     # 조명 OFF 시 호출
        stats = monitor.get_stats()
    """

    def __init__(self, shared_state: dict):
        self.shared_state = shared_state
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # 누적 시간 (초)
        self._stats = {
            "absent":     0.0,
            "drowsy":     0.0,
            "sleep":      0.0,
            "distracted": 0.0,
            "focused":    0.0,
        }
        # 집중도 (0~100, -1 = 워밍업 중)
        self._concentration: int = -1
        self._session_start: float | None = None

    # ── 외부 인터페이스 ──────────────────────────────────────────
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._session_start = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[FACE] 모니터링 시작", flush=True)

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
        cv2.destroyAllWindows()
        print("[FACE] 모니터링 중지", flush=True)
        print(f"[FACE] 세션 통계: {self.get_stats()}", flush=True)

    def get_stats(self) -> dict:
        with self._lock:
            stats = dict(self._stats)
            conc  = self._concentration
        total = sum(stats.values())
        stats["total_seconds"] = round(total, 1)
        stats["concentration"] = conc  # -1 이면 워밍업 중
        return {k: round(v, 1) if isinstance(v, float) else v
                for k, v in stats.items()}

    def reset_stats(self):
        with self._lock:
            for k in self._stats:
                self._stats[k] = 0.0
            self._concentration = -1
        self._session_start = time.time()

    # ── 내부 루프 ────────────────────────────────────────────────
    def _run(self):
        cam_idx = _find_usb_camera()
        if cam_idx is None:
            print("[FACE] USB 카메라를 찾을 수 없습니다.", flush=True)
            return

        cap = cv2.VideoCapture(cam_idx, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 15)

        mp_face_mesh  = mp.solutions.face_mesh
        mp_drawing    = mp.solutions.drawing_utils
        mp_draw_style = mp.solutions.drawing_styles

        face_mesh = mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        # 상태 변수
        eye_closed_start: float | None = None
        is_eye_open_prev = True
        blink_count      = 0
        start_time       = time.time()
        prev_time        = start_time
        prev_state       = "focused"

        try:
            while not self._stop_event.is_set():
                ret, image = cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue

                now       = time.time()
                dt        = now - prev_time
                prev_time = now
                elapsed   = now - start_time

                h, w = image.shape[:2]
                image.flags.writeable = False
                rgb    = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                result = face_mesh.process(rgb)
                image.flags.writeable = True

                # 기본값
                status_text  = "AWAKE"
                status_color = (0, 200, 0)
                closed_time  = 0.0
                drowsy_level = 0
                avg_ear      = 0.0
                yaw          = 0.0
                pitch        = 0.0
                state        = "absent"
                concentration = self._concentration

                if not result.multi_face_landmarks:
                    status_text  = "NO FACE"
                    status_color = (100, 100, 100)
                    eye_closed_start = None

                else:
                    lm = result.multi_face_landmarks[0].landmark

                    # ── EAR 계산 ──
                    left_ear  = _ear(lm, LEFT_EYE,  w, h)
                    right_ear = _ear(lm, RIGHT_EYE, w, h)
                    avg_ear   = (left_ear + right_ear) / 2.0
                    is_closed = avg_ear < EAR_THRESHOLD

                    # 깜빡임 카운트 (닫힘→열림 전환 시점)
                    if not is_closed and not is_eye_open_prev:
                        blink_count += 1
                    is_eye_open_prev = not is_closed

                    # 눈 감긴 지속 시간
                    if is_closed:
                        if eye_closed_start is None:
                            eye_closed_start = now
                        closed_time = now - eye_closed_start
                    else:
                        eye_closed_start = None
                        closed_time = 0.0

                    # ── 졸음 단계 판정 ──
                    if closed_time >= TS:
                        drowsy_level = 2
                        status_text  = "SLEEP WARNING!"
                        status_color = (0, 0, 180)
                        state        = "sleep"
                    elif closed_time >= TD:
                        drowsy_level = 1
                        status_text  = "DROWSY!"
                        status_color = (0, 0, 255)
                        state        = "drowsy"
                    else:
                        # ── Head pose (딴짓) ──
                        yaw, pitch = _head_pose(lm, w, h)
                        if abs(yaw) > YAW_THRESHOLD or abs(pitch) > PITCH_THRESHOLD:
                            status_text  = "DISTRACTED"
                            status_color = (0, 165, 255)
                            state        = "distracted"
                        else:
                            status_text  = "AWAKE"
                            status_color = (0, 200, 0)
                            state        = "focused"

                    # ── 집중도 계산 (워밍업 후) ──
                    if elapsed >= WARMUP_SECONDS:
                        elapsed_min = elapsed / 60.0
                        current_bpm = blink_count / elapsed_min
                        if current_bpm <= 0:
                            concentration = 100
                        elif current_bpm >= NORMAL_BPM:
                            concentration = 0
                        else:
                            concentration = int((1 - current_bpm / NORMAL_BPM) * 100)
                    else:
                        concentration = -1

                    with self._lock:
                        self._concentration = concentration

                    # ── Face Mesh 그리기 ──
                    mp_drawing.draw_landmarks(
                        image=image,
                        landmark_list=result.multi_face_landmarks[0],
                        connections=mp_face_mesh.FACEMESH_TESSELATION,
                        landmark_drawing_spec=None,
                        connection_drawing_spec=mp_draw_style.get_default_face_mesh_tesselation_style(),
                    )
                    mp_drawing.draw_landmarks(
                        image=image,
                        landmark_list=result.multi_face_landmarks[0],
                        connections=mp_face_mesh.FACEMESH_CONTOURS,
                        landmark_drawing_spec=None,
                        connection_drawing_spec=mp_draw_style.get_default_face_mesh_contours_style(),
                    )
                    # 눈 랜드마크 강조
                    for idx in LEFT_EYE + RIGHT_EYE:
                        x = int(lm[idx].x * w)
                        y = int(lm[idx].y * h)
                        cv2.circle(image, (x, y), 3, (0, 255, 255), -1)

                # ── 누적 시간 저장 ──
                with self._lock:
                    self._stats[state] += dt

                # shared_state 업데이트 (상태 변경 시)
                if state != prev_state:
                    self.shared_state["face_state"] = state
                    print(f"[FACE] 상태 변경: {prev_state} → {state}", flush=True)
                    prev_state = state

                # ── cv2 오버레이 + 창 표시 ──
                _draw_overlay(
                    image, state, status_text, status_color, drowsy_level,
                    avg_ear, closed_time, concentration,
                    elapsed, blink_count, yaw, pitch,
                )
                cv2.imshow("SmartStand - Face Monitor", image)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        finally:
            cap.release()
            face_mesh.close()
            cv2.destroyAllWindows()
