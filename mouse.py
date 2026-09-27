import cv2
import numpy as np
import ctypes
import time


# =========================================================
# CONFIG
# =========================================================

CAMERA_INDEX = 1

# HARUS SAMA DENGAN CALIBRATION
WIDTH = 1280
HEIGHT = 720

# FPS yang diminta ke kamera (MJPG)
CAMERA_FPS = 30

# =========================================================
# DETECTION
# =========================================================

BRIGHTNESS_THRESHOLD = 100

MIN_AREA = 2

# HARUS SAMA DENGAN CALIBRATION
MAX_AREA = 50000

# Green dominance (HARUS SAMA DENGAN CALIBRATION)
GREEN_R_RATIO = 1.20
GREEN_B_RATIO = 1.10

# =========================================================
# ROI
# =========================================================

ROI_SIZE = 250

# Jarak maksimum LED boleh berpindah
BASE_MAX_JUMP = 150

# Kalau gerak cepat, batas bisa membesar
MAX_ADAPTIVE_JUMP = 300

# =========================================================
# LOST TRACK
# =========================================================

LOST_FRAMES_LIMIT = 5


# =========================================================
# PREDICTION
# =========================================================

PREDICTION_FACTOR = 0.8


# =========================================================
# SCORING
# =========================================================

WEIGHT_BLUE = 60
WEIGHT_BRIGHTNESS = 20
WEIGHT_AREA = 10
WEIGHT_DISTANCE = 30
WEIGHT_PREDICTION = 30


# =========================================================
# DEBUG
# =========================================================

DEBUG = True


# =========================================================
# EXPOSURE (HARUS SAMA DENGAN CALIBRATION)
# =========================================================

AUTO_EXPOSURE = 0.25
EXPOSURE = -8


# =========================================================
# LOAD CALIBRATION
# =========================================================

homography = np.load(
    "calibration.npy"
)


# =========================================================
# SCREEN
# =========================================================

user32 = ctypes.windll.user32

SCREEN_W = user32.GetSystemMetrics(0)
SCREEN_H = user32.GetSystemMetrics(1)


# =========================================================
# MOUSE
# =========================================================

def move_mouse(x, y):

    user32.SetCursorPos(
        int(x),
        int(y)
    )


# =========================================================
# CAMERA
# =========================================================

cap = cv2.VideoCapture(
    CAMERA_INDEX,
    cv2.CAP_DSHOW
)


if not cap.isOpened():

    raise RuntimeError(
        "Camera gagal dibuka."
    )


cap.set(
    cv2.CAP_PROP_FPS,
    CAMERA_FPS
)


cap.set(
    cv2.CAP_PROP_FRAME_WIDTH,
    WIDTH
)

cap.set(
    cv2.CAP_PROP_FRAME_HEIGHT,
    HEIGHT
)


# ---------------------------------------------------------
# MJPG
# HARUS SETELAH set resolusi (khusus DSHOW).
# Kalau di-set sebelum resolusi, kamera balik ke
# YUY2 dan FPS mentok ~10 di 720p.
# ---------------------------------------------------------

cap.set(
    cv2.CAP_PROP_FOURCC,
    cv2.VideoWriter_fourcc(*"MJPG")
)


# Manual exposure

cap.set(
    cv2.CAP_PROP_AUTO_EXPOSURE,
    AUTO_EXPOSURE
)

cap.set(
    cv2.CAP_PROP_EXPOSURE,
    EXPOSURE
)


# =========================================================
# CHECK ACTUAL CAMERA SETTING
# =========================================================

actual_width = int(
    cap.get(cv2.CAP_PROP_FRAME_WIDTH)
)

actual_height = int(
    cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
)

actual_fps = cap.get(
    cv2.CAP_PROP_FPS
)

fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
fourcc_str = "".join(
    chr((fourcc_int >> 8 * i) & 0xFF)
    for i in range(4)
)


print(f"Camera : {actual_width} x {actual_height}")
print(f"FPS cam: {actual_fps}")
print(f"Format : {fourcc_str}")
print(f"Screen : {SCREEN_W} x {SCREEN_H}")


if actual_width != WIDTH or actual_height != HEIGHT:

    print()
    print("WARNING: Resolusi kamera tidak sesuai!")
    print(f"Expected : {WIDTH} x {HEIGHT}")
    print(f"Actual   : {actual_width} x {actual_height}")
    print()


# =========================================================
# TRACKING STATE
# =========================================================

last_x = None
last_y = None

prev_x = None
prev_y = None

velocity_x = 0
velocity_y = 0

lost_frames = 0


# =========================================================
# DISTANCE
# =========================================================

def distance(
    x1,
    y1,
    x2,
    y2
):

    return np.sqrt(
        (x1 - x2) ** 2 +
        (y1 - y2) ** 2
    )


# =========================================================
# DETECT CANDIDATES
# =========================================================

def detect_candidates(
    img,
    offset_x=0,
    offset_y=0
):

    # =====================================================
    # CHANNEL
    # =====================================================

    B, G, R = cv2.split(img)

    Bf = B.astype(np.float32)
    Gf = G.astype(np.float32)
    Rf = R.astype(np.float32)


    # =====================================================
    # GRAYSCALE
    # =====================================================

    gray = cv2.cvtColor(
        img,
        cv2.COLOR_BGR2GRAY
    )


    # =====================================================
    # BRIGHTNESS
    # =====================================================

    bright_mask = (
        gray >= BRIGHTNESS_THRESHOLD
    )


    # =====================================================
    # GREEN
    # =====================================================

    blue_mask = (

        (Gf > Rf * GREEN_R_RATIO)

        &

        (Gf > Bf * GREEN_B_RATIO)

        &

        (Gf > 80)
    )


    # =====================================================
    # COMBINE
    # =====================================================

    mask = (

        bright_mask

        &

        blue_mask

    ).astype(
        np.uint8
    ) * 255


    # =====================================================
    # MORPHOLOGY
    # =====================================================

    kernel = np.ones(
        (3, 3),
        np.uint8
    )


    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        kernel
    )


    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        kernel
    )


    # =====================================================
    # CONTOURS
    # =====================================================

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )


    candidates = []


    # =====================================================
    # LOOP
    # =====================================================

    for contour in contours:

        area = cv2.contourArea(
            contour
        )


        if area < MIN_AREA:
            continue


        if area > MAX_AREA:
            continue


        # =================================================
        # BOUNDING BOX
        # =================================================

        x, y, w, h = cv2.boundingRect(
            contour
        )


        # =================================================
        # ASPECT RATIO
        # =================================================

        aspect_ratio = max(
            w / max(h, 1),
            h / max(w, 1)
        )


        # Lampu panjang -> reject

        if aspect_ratio > 4.0:
            continue


        # =================================================
        # CENTROID
        # =================================================

        M = cv2.moments(
            contour
        )


        if M["m00"] == 0:
            continue


        cx = M["m10"] / M["m00"]
        cy = M["m01"] / M["m00"]


        # =================================================
        # GLOBAL COORDINATE
        # =================================================

        real_x = cx + offset_x
        real_y = cy + offset_y


        # =================================================
        # LOCAL REGION
        # =================================================

        pad = 6

        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(img.shape[1], x + w + pad)
        y2 = min(img.shape[0], y + h + pad)


        local_B = Bf[y1:y2, x1:x2]
        local_G = Gf[y1:y2, x1:x2]
        local_R = Rf[y1:y2, x1:x2]


        # =================================================
        # GREEN RATIO
        # =================================================

        local_blue = (

            (local_G > local_R * GREEN_R_RATIO)

            &

            (local_G > local_B * GREEN_B_RATIO)

        )


        blue_ratio = np.mean(
            local_blue
        )


        # =================================================
        # BRIGHTNESS
        # =================================================

        brightness = np.mean(
            gray[y1:y2, x1:x2]
        )


        # =================================================
        # SCORES
        # =================================================

        blue_score = min(
            blue_ratio * 2.0,
            1.0
        )


        brightness_score = min(
            brightness / 255.0,
            1.0
        )


        # =================================================
        # AREA SCORE
        # =================================================

        ideal_area = 80


        area_score = 1.0 - min(
            abs(area - ideal_area)
            / ideal_area,
            1.0
        )


        # =================================================
        # COMPACTNESS
        # =================================================

        bounding_area = w * h


        fill_ratio = (
            area /
            max(bounding_area, 1)
        )


        compactness_score = min(
            fill_ratio * 1.5,
            1.0
        )


        # =================================================
        # CANDIDATE
        # =================================================

        candidates.append({

            "x": real_x,

            "y": real_y,

            "area": area,

            "blue_ratio": blue_ratio,

            "brightness": brightness,

            "blue_score": blue_score,

            "brightness_score":
                brightness_score,

            "area_score":
                area_score,

            "compactness_score":
                compactness_score,

            "aspect_ratio":
                aspect_ratio,

            "contour":
                contour

        })


    return candidates


# =========================================================
# SELECT BEST CANDIDATE
# =========================================================

def select_candidate(
    candidates,
    last_position,
    velocity
):

    if not candidates:
        return None


    # =====================================================
    # NO PREVIOUS POSITION
    # =====================================================

    if last_position is None:

        best = None
        best_score = -999999


        for c in candidates:

            score = (

                c["blue_score"]
                * WEIGHT_BLUE

                +

                c["brightness_score"]
                * WEIGHT_BRIGHTNESS

                +

                c["area_score"]
                * WEIGHT_AREA

                +

                c["compactness_score"]
                * 10
            )


            if score > best_score:

                best_score = score

                best = c


        return best


    # =====================================================
    # PREVIOUS POSITION
    # =====================================================

    px, py = last_position

    vx, vy = velocity


    # =====================================================
    # PREDICT NEXT POSITION
    # =====================================================

    predicted_x = px + vx * PREDICTION_FACTOR
    predicted_y = py + vy * PREDICTION_FACTOR


    # =====================================================
    # ADAPTIVE MAX JUMP
    # =====================================================

    speed = np.sqrt(
        vx ** 2 +
        vy ** 2
    )


    max_jump = min(
        BASE_MAX_JUMP + speed * 1.5,
        MAX_ADAPTIVE_JUMP
    )


    valid_candidates = []


    # =====================================================
    # FILTER BY DISTANCE
    # =====================================================

    for c in candidates:

        x = c["x"]
        y = c["y"]


        dist_previous = distance(
            x, y,
            px, py
        )


        dist_prediction = distance(
            x, y,
            predicted_x, predicted_y
        )


        # -------------------------------------------------
        # Candidate terlalu jauh
        # -------------------------------------------------

        if dist_previous > max_jump:

            continue


        valid_candidates.append(
            (
                c,
                dist_previous,
                dist_prediction
            )
        )


    # =====================================================
    # NOTHING VALID
    # =====================================================

    if not valid_candidates:

        return None


    # =====================================================
    # SCORE
    # =====================================================

    best = None
    best_score = -999999


    for (
        c,
        dist_previous,
        dist_prediction
    ) in valid_candidates:


        # -------------------------------------------------
        # DISTANCE SCORE
        # -------------------------------------------------

        distance_score = max(
            0.0,
            1.0 -
            dist_previous /
            max(max_jump, 1)
        )


        # -------------------------------------------------
        # PREDICTION SCORE
        # -------------------------------------------------

        prediction_score = max(
            0.0,
            1.0 -
            dist_prediction /
            max(max_jump, 1)
        )


        # -------------------------------------------------
        # TOTAL
        # -------------------------------------------------

        score = (

            c["blue_score"]
            * WEIGHT_BLUE

            +

            c["brightness_score"]
            * WEIGHT_BRIGHTNESS

            +

            c["area_score"]
            * WEIGHT_AREA

            +

            c["compactness_score"]
            * 10

            +

            distance_score
            * WEIGHT_DISTANCE

            +

            prediction_score
            * WEIGHT_PREDICTION
        )


        if score > best_score:

            best_score = score

            best = c


    return best


# =========================================================
# FPS
# =========================================================

fps_count = 0

fps_timer = time.time()


# =========================================================
# START
# =========================================================

print()
print("====================================")
print("       LED MOUSE TRACKING")
print("====================================")
print()
print("Q = EXIT")
print()


# =========================================================
# MAIN LOOP
# =========================================================

while True:

    ret, frame = cap.read()


    if not ret:
        continue


    found = None


    # =====================================================
    # PREDICT POSITION
    # =====================================================

    if last_x is not None:

        predicted_x = last_x + velocity_x * PREDICTION_FACTOR
        predicted_y = last_y + velocity_y * PREDICTION_FACTOR

    else:

        predicted_x = None
        predicted_y = None


    # =====================================================
    # ROI SEARCH
    # =====================================================

    if last_x is not None:

        roi_center_x = (
            predicted_x
            if predicted_x is not None
            else last_x
        )

        roi_center_y = (
            predicted_y
            if predicted_y is not None
            else last_y
        )


        x1 = max(0, int(roi_center_x - ROI_SIZE))
        x2 = min(WIDTH, int(roi_center_x + ROI_SIZE))

        y1 = max(0, int(roi_center_y - ROI_SIZE))
        y2 = min(HEIGHT, int(roi_center_y + ROI_SIZE))


        roi = frame[
            y1:y2,
            x1:x2
        ]


        candidates = detect_candidates(
            roi,
            x1,
            y1
        )


        found = select_candidate(
            candidates,
            (last_x, last_y),
            (velocity_x, velocity_y)
        )


    # =====================================================
    # FULL FRAME REACQUISITION
    # =====================================================

    if found is None:

        lost_frames += 1


        # Jangan langsung full search
        if lost_frames <= LOST_FRAMES_LIMIT:

            found = None


        else:

            candidates = detect_candidates(
                frame
            )


            # Saat reacquire,
            # jangan pakai distance lock terlalu ketat

            found = select_candidate(
                candidates,
                None,
                (0, 0)
            )


            if found is not None:

                lost_frames = 0


    # =====================================================
    # LED FOUND
    # =====================================================

    if found is not None:

        cam_x = found["x"]
        cam_y = found["y"]


        # =================================================
        # VELOCITY
        # =================================================

        if last_x is not None:

            velocity_x = cam_x - last_x
            velocity_y = cam_y - last_y


        # =================================================
        # UPDATE POSITION
        # =================================================

        prev_x = last_x
        prev_y = last_y

        last_x = cam_x
        last_y = cam_y

        lost_frames = 0


        # =================================================
        # HOMOGRAPHY
        # =================================================

        p = np.array(
            [[[cam_x, cam_y]]],
            dtype=np.float32
        )


        screen = cv2.perspectiveTransform(
            p,
            homography
        )


        sx = screen[0][0][0]
        sy = screen[0][0][1]


        # =================================================
        # CLAMP
        # =================================================

        sx = max(0, min(SCREEN_W - 1, sx))
        sy = max(0, min(SCREEN_H - 1, sy))


        # =================================================
        # MOVE MOUSE
        # =================================================

        move_mouse(
            sx,
            sy
        )


        # =================================================
        # DEBUG
        # =================================================

        if DEBUG:

            cv2.circle(
                frame,
                (
                    int(cam_x),
                    int(cam_y)
                ),
                10,
                (0, 0, 255),
                -1
            )


            cv2.putText(
                frame,
                f"CAM: {int(cam_x)}, {int(cam_y)}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )


            cv2.putText(
                frame,
                f"SCREEN: {int(sx)}, {int(sy)}",
                (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )


            cv2.putText(
                frame,
                f"GREEN: {found['blue_ratio']:.2f}",
                (20, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )


            cv2.putText(
                frame,
                f"AREA: {found['area']:.1f}",
                (20, 130),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )


            cv2.putText(
                frame,
                f"LOST: {lost_frames}",
                (20, 160),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )


            cv2.circle(
                frame,
                (
                    int(predicted_x)
                    if predicted_x is not None
                    else int(cam_x),

                    int(predicted_y)
                    if predicted_y is not None
                    else int(cam_y)
                ),
                5,
                (255, 0, 255),
                -1
            )


    # =====================================================
    # DEBUG WINDOW
    # =====================================================

    if DEBUG:

        fps_count += 1


        if (time.time() - fps_timer) >= 1:

            print(
                "FPS:",
                fps_count,
                "| LED:",
                "LOCKED"
                if found is not None
                else "LOST"
            )


            fps_count = 0

            fps_timer = time.time()


        cv2.imshow(
            "LED Tracking",
            frame
        )


        key = cv2.waitKey(1) & 0xFF


        if key == ord("q"):

            break


    else:

        # tetap perlu waitKey
        # untuk OpenCV event processing

        if cv2.waitKey(1) & 0xFF == ord("q"):

            break


# =========================================================
# END
# =========================================================

cap.release()

cv2.destroyAllWindows()