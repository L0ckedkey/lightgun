import cv2
import time

CAMERA_INDEX = 1
WIDTH = 1280
HEIGHT = 720
TEST_SECONDS = 3


def fourcc_str(cap):
    v = int(cap.get(cv2.CAP_PROP_FOURCC))
    return "".join(chr((v >> 8 * i) & 0xFF) for i in range(4))


def test(name, backend, order, manual_exposure):

    cap = cv2.VideoCapture(CAMERA_INDEX, backend)

    if not cap.isOpened():
        print(f"{name:<35} GAGAL DIBUKA")
        return

    mjpg = cv2.VideoWriter_fourcc(*"MJPG")

    if order == "before":
        cap.set(cv2.CAP_PROP_FOURCC, mjpg)

    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)

    if order == "after":
        cap.set(cv2.CAP_PROP_FOURCC, mjpg)

    if manual_exposure:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        cap.set(cv2.CAP_PROP_EXPOSURE, -8)

    # warm up
    for _ in range(10):
        cap.read()

    frames = 0
    start = time.time()

    while time.time() - start < TEST_SECONDS:
        ret, _ = cap.read()
        if ret:
            frames += 1

    fps = frames / (time.time() - start)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(
        f"{name:<35} "
        f"{w}x{h}  "
        f"format={fourcc_str(cap):<5} "
        f"FPS={fps:.1f}"
    )

    cap.release()


print()
print("Tes FPS murni (cuma cap.read, tanpa proses)")
print("Jangan tutup, tunggu sampai selesai...")
print()

test("DSHOW  MJPG-before  exposure-manual", cv2.CAP_DSHOW, "before", True)
test("DSHOW  MJPG-after   exposure-manual", cv2.CAP_DSHOW, "after", True)
test("DSHOW  MJPG-before  exposure-auto", cv2.CAP_DSHOW, "before", False)
test("DSHOW  tanpa-MJPG   exposure-manual", cv2.CAP_DSHOW, "none", True)
test("MSMF   MJPG-before  exposure-manual", cv2.CAP_MSMF, "before", True)
test("MSMF   default      exposure-auto", cv2.CAP_MSMF, "none", False)

print()
print("Selesai.")