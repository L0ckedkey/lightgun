/*
  Lightgun Trigger - ESP32 BLE Mouse
  -----------------------------------
  Tactile switch di trigger -> klik kiri mouse via Bluetooth (BLE HID).
  Gerakan kursor tetap dari script Python (webcam + IR), ESP32 cuma ngurus klik.

  Board  : ESP32 / ESP32-C3 / ESP32-S3 (yang punya BLE)
  Library: ESP32-BLE-Mouse by T-vK  -> https://github.com/T-vK/ESP32-BLE-Mouse
           (Sketch > Include Library > Add .ZIP Library)

  Wiring:
    Tactile switch kaki 1 -> GPIO 4
    Tactile switch kaki 2 -> GND
    (switch 4 kaki: pakai dua kaki yang diagonal biar pasti beda sisi)
    Gak perlu resistor, udah pakai INPUT_PULLUP internal.
*/

#include <BleMouse.h>

// ---------- Konfigurasi ----------
const int TRIGGER_PIN = 14;              // GPIO trigger (aman di ESP32, C3, S3)
const unsigned long DEBOUNCE_MS = 8;    // debounce, kecil biar respons cepat

BleMouse bleMouse("Lightgun Hans", "DIY", 100);  // nama bluetooth, pabrikan, baterai %

// ---------- State ----------
bool stableState   = HIGH;   // HIGH = dilepas (pull-up), LOW = ditekan
bool lastReading   = HIGH;
unsigned long lastChangeMs = 0;
bool wasConnected  = false;

void setup() {
  Serial.begin(115200);
  pinMode(TRIGGER_PIN, INPUT_PULLUP);

  bleMouse.begin();
  Serial.println("Lightgun BLE siap, menunggu koneksi...");
}

void loop() {
  // --- status koneksi ---
  bool connected = bleMouse.isConnected();
  if (connected != wasConnected) {
    wasConnected = connected;
    Serial.println(connected ? "Terhubung ke PC" : "Terputus");
  }

  // --- baca switch + debounce ---
  bool reading = digitalRead(TRIGGER_PIN);
  if (reading != lastReading) {
    lastReading  = reading;
    lastChangeMs = millis();
  }

  if ((millis() - lastChangeMs) >= DEBOUNCE_MS && reading != stableState) {
    stableState = reading;

    if (stableState == LOW) {
      Serial.println("TEMBAK");
      if (connected) bleMouse.press(MOUSE_LEFT);    // tahan = klik ditahan (buat game auto-fire)
    } else {
      Serial.println("lepas");
      if (connected) bleMouse.release(MOUSE_LEFT);
    }
  }

  delay(1);
}