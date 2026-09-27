import cv2
import numpy as np

# =========================================================
# COLOR PICKER
#
# Tool bantu untuk mengganti warna LED.
# Klik di glow LED -> tool menghitung warna dominan,
# menyarankan nilai rasio, dan mencetak kode yang
# tinggal ditempel ke calibration.py dan led_mouse.py.
# =========================================================


# =========================================================
# CONFIG (samakan dengan script utama)
# =========================================================

CAMERA_INDEX = 1

WIDTH = 1280
HEIGHT = 720

CAMERA_FPS = 30

AUTO_EXPOSURE = 0.25
EXPOSURE = -8

BRIGHTNESS_THRESHOLD = 100

# Nilai minimal channel utama (sama dengan "> 80" di script)
MIN_CHANNEL = 80

# Radius area yang dirata-rata saat klik (pixel)
SAMPLE_RADIUS = 2

# Rasio saran = rasio terukur x faktor ini
# (0.5 = setengahnya, cukup longgar tapi tetap aman)
SUGGEST_FACTOR = 0.5

# Rasio minimal yang disarankan
MIN_SUGGESTED_RATIO = 1.05


CHANNEL_NAMES = {
    "B": "BLUE",
    "G": "GREEN",
    "R": "RED"
}


# =========================================================
# CAMERA
# =========================================================

cap = cv2.VideoCapture(
    CAMERA_INDEX,
    cv2.CAP_DSHOW
)

if not cap.isOpened():
    raise RuntimeError("Webcam tidak bisa dibuka.")

cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)

# MJPG setelah resolusi (khusus DSHOW)
cap.set(
    cv2.CAP_PROP_FOURCC,
    cv2.VideoWriter_fourcc(*"MJPG")
)

cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, AUTO_EXPOSURE)
cap.set(cv2.CAP_PROP_EXPOSURE, EXPOSURE)


# =========================================================
# STATE
# =========================================================

frame = None

samples = []      # list of (b, g, r)
points = []       # posisi klik

suggestion = None  # (main, others, ratios)

show_mask = False


# =========================================================
# ANALYZE
# =========================================================

def analyze():

    arr = np.array(samples)

    b, g, r = arr.mean(axis=0)

    values = {
        "B": b,
        "G": g,
        "R": r
    }

    main = max(values, key=values.get)

    # urutan R, G, B tanpa channel utama
    others = [c for c in ["R", "G", "B"] if c != main]

    measured = [
        values[main] / max(values[o], 1.0)
        for o in others
    ]

    suggested = [
        round(max(MIN_SUGGESTED_RATIO, m * SUGGEST_FACTOR), 2)
        for m in measured
    ]

    return values, main, others, measured, suggested


# =========================================================
# PRINT RESULT
# =========================================================

def print_result(values, main, others, measured, suggested):

    name = CHANNEL_NAMES[main]

    c1 = f"{name}_{others[0]}_RATIO"
    c2 = f"{name}_{others[1]}_RATIO"

    print()
    print("====================================================")
    print(f"Jumlah sampel : {len(samples)}")
    print(
        f"Rata-rata     : "
        f"B={values['B']:.0f}  "
        f"G={values['G']:.0f}  "
        f"R={values['R']:.0f}"
    )
    print(f"Warna dominan : {name}")
    print()

    for o, m, s in zip(others, measured, suggested):
        print(
            f"  {main}/{o} terukur = {m:.2f}  ->  "
            f"saran rasio = {s:.2f}"
        )

    if min(measured) < 1.3:
        print()
        print(
            "  PERINGATAN: channel utama tidak terlalu dominan."
        )
        print(
            "  Kemungkinan warnanya campuran (kuning/cyan/ungu),"
        )
        print(
            "  atau sampel diambil di area yang terlalu putih."
        )

    # -----------------------------------------------------
    # Snippet siap tempel
    # -----------------------------------------------------

    print()
    print("---------------- TEMPEL KE KEDUA SCRIPT ----------------")
    print()
    print("# ===== CONFIG =====")
    print(f"{c1} = {suggested[0]:.2f}")
    print(f"{c2} = {suggested[1]:.2f}")
    print()
    print("# ===== ganti isi blue_mask =====")
    print("    blue_mask = (")
    print(f"        ({main}f > {others[0]}f * {c1})")
    print("        &")
    print(f"        ({main}f > {others[1]}f * {c2})")
    print("        &")
    print(f"        ({main}f > {MIN_CHANNEL})")
    print("    )")
    print()
    print("# ===== ganti isi local_blue =====")
    print("        local_blue = (")
    print(f"            (local_{main} > local_{others[0]} * {c1})")
    print("            &")
    print(f"            (local_{main} > local_{others[1]} * {c2})")
    print("        )")
    print()
    print("--------------------------------------------------------")
    print()


# =========================================================
# MASK PREVIEW
# =========================================================

def build_mask(img, main, others, ratios):

    B, G, R = cv2.split(img.astype(np.float32))

    ch = {
        "B": B,
        "G": G,
        "R": R
    }

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    mask = (
        (gray >= BRIGHTNESS_THRESHOLD)
        &
        (ch[main] > ch[others[0]] * ratios[0])
        &
        (ch[main] > ch[others[1]] * ratios[1])
        &
        (ch[main] > MIN_CHANNEL)
    )

    return mask.astype(np.uint8) * 255


# =========================================================
# MOUSE CALLBACK
# =========================================================

def mouse_callback(event, x, y, flags, param):

    global suggestion

    if event != cv2.EVENT_LBUTTONDOWN:
        return

    if frame is None:
        return

    r = SAMPLE_RADIUS

    region = frame[
        max(0, y - r):y + r + 1,
        max(0, x - r):x + r + 1
    ].reshape(-1, 3).astype(np.float32)

    b, g, rr = region.mean(axis=0)

    print(
        f"Sampel ({x}, {y}) -> "
        f"B={b:.0f}  G={g:.0f}  R={rr:.0f}"
    )

    if min(b, g, rr) >= 230:
        print(
            "  Diabaikan: pixel hampir putih (overexposed). "
            "Klik di pinggir glow, bukan di tengah LED."
        )
        return

    if max(b, g, rr) < MIN_CHANNEL:
        print(
            "  Diabaikan: pixel terlalu gelap. "
            "Klik di area glow LED."
        )
        return

    samples.append((b, g, rr))
    points.append((x, y))

    values, main, others, measured, suggested = analyze()

    suggestion = (main, others, suggested)

    print_result(values, main, others, measured, suggested)


# =========================================================
# WINDOW
# =========================================================

WINDOW_NAME = "Color Picker"

cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
cv2.setMouseCallback(WINDOW_NAME, mouse_callback)


print()
print("====================================")
print("         LED COLOR PICKER")
print("====================================")
print()
print("KLIK KIRI : ambil sampel di glow LED (bukan di tengah yang putih)")
print("M         : tampilkan/sembunyikan preview mask")
print("R         : reset sampel")
print("Q         : keluar")
print()
print("Ambil 3-5 sampel di beberapa sisi glow untuk hasil lebih stabil.")
print()


# =========================================================
# LOOP
# =========================================================

while True:

    ret, img = cap.read()

    if not ret:
        continue

    frame = img

    display = img.copy()

    # titik sampel
    for (px, py) in points:
        cv2.circle(display, (px, py), 6, (0, 0, 255), 2)

    # info
    if suggestion is not None:

        main, others, ratios = suggestion

        info = (
            f"{CHANNEL_NAMES[main]}  "
            f"{main}/{others[0]}={ratios[0]:.2f}  "
            f"{main}/{others[1]}={ratios[1]:.2f}  "
            f"({len(samples)} sampel)"
        )

    else:

        info = "Klik kiri di glow LED"

    cv2.putText(
        display,
        info,
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2
    )

    cv2.putText(
        display,
        "KLIK = sampel   M = mask   R = reset   Q = keluar",
        (20, HEIGHT - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2
    )

    cv2.imshow(WINDOW_NAME, display)

    # preview mask
    if show_mask and suggestion is not None:

        main, others, ratios = suggestion

        cv2.imshow(
            "Mask Preview",
            build_mask(img, main, others, ratios)
        )

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

    elif key == ord("r"):

        samples.clear()
        points.clear()
        suggestion = None

        print("Sampel direset.")

    elif key == ord("m"):

        show_mask = not show_mask

        if not show_mask:
            try:
                cv2.destroyWindow("Mask Preview")
            except cv2.error:
                pass

        elif suggestion is None:
            print("Ambil sampel dulu sebelum melihat mask.")


cap.release()
cv2.destroyAllWindows()
