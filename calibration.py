import cv2
import numpy as np
import pyautogui

# =========================================================
# CONFIG
# =========================================================

CAMERA_INDEX = 1

# HARUS SAMA DENGAN SCRIPT MOUSE
WIDTH = 1280
HEIGHT = 720

# FPS yang diminta ke kamera (MJPG)
CAMERA_FPS = 30

# ---------------------------------------------------------
# Detection
# ---------------------------------------------------------

BRIGHTNESS_THRESHOLD = 100

MIN_AREA = 3

# HARUS SAMA DENGAN SCRIPT MOUSE
MAX_AREA = 50000

# ---------------------------------------------------------
# Green detection (HARUS SAMA DENGAN SCRIPT MOUSE)
# ---------------------------------------------------------

GREEN_R_RATIO = 1.20
GREEN_B_RATIO = 1.10

# ---------------------------------------------------------
# Scoring
# ---------------------------------------------------------

WEIGHT_BRIGHTNESS = 25
WEIGHT_BLUE = 60
WEIGHT_AREA = 15

# ---------------------------------------------------------
# Exposure (HARUS SAMA DENGAN SCRIPT MOUSE)
# ---------------------------------------------------------

AUTO_EXPOSURE = 0.25
EXPOSURE = -8


# =========================================================
# SCREEN
# =========================================================

SCREEN_W, SCREEN_H = pyautogui.size()

SCREEN_POINTS = np.array([
    [0, 0],
    [SCREEN_W - 1, 0],
    [SCREEN_W - 1, SCREEN_H - 1],
    [0, SCREEN_H - 1]
], dtype=np.float32)


LABELS = [
    "KIRI ATAS",
    "KANAN ATAS",
    "KANAN BAWAH",
    "KIRI BAWAH"
]


# =========================================================
# CAMERA
# =========================================================

cap = cv2.VideoCapture(
    CAMERA_INDEX,
    cv2.CAP_DSHOW
)

if not cap.isOpened():
    raise RuntimeError(
        "Webcam tidak bisa dibuka."
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


# ---------------------------------------------------------
# Manual exposure
# ---------------------------------------------------------

cap.set(
    cv2.CAP_PROP_AUTO_EXPOSURE,
    AUTO_EXPOSURE
)

cap.set(
    cv2.CAP_PROP_EXPOSURE,
    EXPOSURE
)


# ---------------------------------------------------------
# Check actual camera setting
# ---------------------------------------------------------

actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
actual_fps = cap.get(cv2.CAP_PROP_FPS)

fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
fourcc_str = "".join(
    chr((fourcc_int >> 8 * i) & 0xFF)
    for i in range(4)
)

print(
    "Actual camera:",
    actual_width,
    "x",
    actual_height
)

print(
    "FPS cam:",
    actual_fps
)

print(
    "Format :",
    fourcc_str
)

if actual_width != WIDTH or actual_height != HEIGHT:

    print()
    print("WARNING: Resolusi kamera tidak sesuai!")
    print(f"Expected : {WIDTH} x {HEIGHT}")
    print(f"Actual   : {actual_width} x {actual_height}")
    print()


# =========================================================
# GLOBAL
# =========================================================

captured_points = []

step = 0

mouse_clicked = False


# =========================================================
# MOUSE CALLBACK
# =========================================================

def mouse_callback(
    event,
    x,
    y,
    flags,
    param
):

    global mouse_clicked

    if event == cv2.EVENT_LBUTTONDOWN:

        mouse_clicked = True


# =========================================================
# FIND LED
# =========================================================

def find_led(frame):

    # =====================================================
    # CHANNEL
    # =====================================================

    B, G, R = cv2.split(frame)

    Bf = B.astype(np.float32)
    Gf = G.astype(np.float32)
    Rf = R.astype(np.float32)


    # =====================================================
    # BRIGHTNESS
    # =====================================================

    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY
    )

    bright_mask = (
        gray >= BRIGHTNESS_THRESHOLD
    )


    # =====================================================
    # GREEN DOMINANCE
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
    ).astype(np.uint8) * 255


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
    # FIND CONTOURS
    # =====================================================

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )


    candidates = []


    # =====================================================
    # ANALYZE
    # =====================================================

    for contour in contours:

        area = cv2.contourArea(
            contour
        )


        # -------------------------------------------------
        # AREA
        # -------------------------------------------------

        if area < MIN_AREA:
            continue

        if area > MAX_AREA:
            continue


        # -------------------------------------------------
        # BOUNDING BOX
        # -------------------------------------------------

        x, y, w, h = cv2.boundingRect(
            contour
        )


        # =================================================
        # SHAPE FILTER
        # =================================================

        aspect_ratio = max(
            w / max(h, 1),
            h / max(w, 1)
        )


        # Lampu panjang (emergency lamp) -> reject,
        # LED lebih compact

        if aspect_ratio > 4.0:
            continue


        # -------------------------------------------------
        # CENTROID
        # -------------------------------------------------

        M = cv2.moments(
            contour
        )

        if M["m00"] == 0:
            continue


        cx = M["m10"] / M["m00"]
        cy = M["m01"] / M["m00"]


        # =================================================
        # LOCAL REGION
        # =================================================

        pad = 5

        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(frame.shape[1], x + w + pad)
        y2 = min(frame.shape[0], y + h + pad)


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
        # GREEN SCORE
        # =================================================

        blue_score = min(
            blue_ratio * 2.0,
            1.0
        )


        # =================================================
        # BRIGHTNESS SCORE
        # =================================================

        brightness_score = min(
            brightness / 255.0,
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


        # LED biasanya lebih compact
        compactness_score = min(
            fill_ratio * 1.5,
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
        # TOTAL SCORE
        # =================================================

        score = (

            blue_score * 60

            +

            brightness_score * 20

            +

            compactness_score * 10

            +

            area_score * 10

        )


        candidates.append({

            "score": score,

            "cx": cx,

            "cy": cy,

            "area": area,

            "contour": contour,

            "blue_ratio": blue_ratio,

            "brightness": brightness,

            "aspect_ratio": aspect_ratio

        })


    # =====================================================
    # NO CANDIDATE
    # =====================================================

    if not candidates:
        return None


    # =====================================================
    # BEST
    # =====================================================

    candidates.sort(
        key=lambda x: x["score"],
        reverse=True
    )


    return candidates[0]


# =========================================================
# WINDOW
# =========================================================

WINDOW_NAME = "LED Calibration"


cv2.namedWindow(
    WINDOW_NAME,
    cv2.WINDOW_NORMAL
)


cv2.setMouseCallback(
    WINDOW_NAME,
    mouse_callback
)


# =========================================================
# START
# =========================================================

print()
print("====================================")
print("       LED MONITOR CALIBRATION")
print("====================================")
print()

print(f"Screen : {SCREEN_W} x {SCREEN_H}")
print(f"Camera : {WIDTH} x {HEIGHT}")

print()
print("Arahkan LED ke setiap pojok monitor.")
print("KLIK KIRI untuk menyimpan posisi.")
print("Q untuk keluar.")
print()


# =========================================================
# CALIBRATION LOOP
# =========================================================

while step < 4:

    ret, frame = cap.read()


    if not ret:

        print(
            "Gagal membaca frame."
        )

        continue


    # -----------------------------------------------------
    # Detect
    # -----------------------------------------------------

    result = find_led(
        frame
    )


    # -----------------------------------------------------
    # Display
    # -----------------------------------------------------

    display = frame.copy()


    # =====================================================
    # LED FOUND
    # =====================================================

    if result is not None:

        cx = result["cx"]
        cy = result["cy"]

        area = result["area"]

        contour = result["contour"]

        score = result["score"]

        blue_ratio = result["blue_ratio"]


        # -------------------------------------------------
        # Draw contour
        # -------------------------------------------------

        cv2.drawContours(
            display,
            [contour],
            -1,
            (0, 255, 0),
            2
        )


        # -------------------------------------------------
        # Draw center
        # -------------------------------------------------

        cv2.circle(
            display,
            (
                int(cx),
                int(cy)
            ),
            8,
            (0, 0, 255),
            -1
        )


        status = (
            f"LED ({cx:.0f}, {cy:.0f})"
        )


    else:

        cx = None
        cy = None

        status = (
            "LED TIDAK TERDETEKSI"
        )


    # =====================================================
    # TEXT
    # =====================================================

    cv2.putText(
        display,
        f"TARGET: {LABELS[step]}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )


    cv2.putText(
        display,
        status,
        (20, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0)
        if result is not None
        else (0, 0, 255),
        2
    )


    # -----------------------------------------------------
    # Debug information
    # -----------------------------------------------------

    if result is not None:

        cv2.putText(
            display,
            f"Score: {score:.1f}",
            (20, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )


        cv2.putText(
            display,
            f"Green: {blue_ratio:.2f}",
            (20, 140),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )


        cv2.putText(
            display,
            f"Area: {area:.1f}",
            (20, 170),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )


    cv2.putText(
        display,
        "LEFT CLICK = SAVE    Q = EXIT",
        (20, HEIGHT - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2
    )


    # =====================================================
    # SHOW
    # =====================================================

    cv2.imshow(
        WINDOW_NAME,
        display
    )


    # =====================================================
    # LEFT CLICK
    # =====================================================

    if mouse_clicked:

        mouse_clicked = False


        if result is not None:

            captured_points.append([
                cx,
                cy
            ])


            print(
                f"{LABELS[step]} -> "
                f"({cx:.2f}, {cy:.2f})"
            )


            step += 1


            if step < 4:

                print(
                    f"Arahkan LED ke "
                    f"{LABELS[step]}"
                )


        else:

            print(
                "LED tidak terdeteksi, "
                "posisi tidak disimpan."
            )


    # =====================================================
    # KEYBOARD
    # =====================================================

    key = cv2.waitKey(1) & 0xFF


    if key == ord("q"):

        print(
            "Calibration dibatalkan."
        )


        cap.release()

        cv2.destroyAllWindows()

        raise SystemExit


# =========================================================
# FINISH
# =========================================================

cap.release()

cv2.destroyAllWindows()


# =========================================================
# VALIDATE
# =========================================================

if len(captured_points) != 4:

    raise RuntimeError(
        "Calibration gagal. "
        "Tidak mendapatkan 4 titik."
    )


camera_points = np.array(
    captured_points,
    dtype=np.float32
)


# =========================================================
# HOMOGRAPHY
# =========================================================

homography = cv2.getPerspectiveTransform(
    camera_points,
    SCREEN_POINTS
)


# =========================================================
# SAVE
# =========================================================

np.save(
    "calibration.npy",
    homography
)


# =========================================================
# RESULT
# =========================================================

print()
print("====================================")
print("       CALIBRATION SELESAI")
print("====================================")
print()

print("Camera points:")
print(camera_points)
print()

print("Homography:")
print(homography)
print()

print("Disimpan:")
print("calibration.npy")
print()