#!/usr/bin/env python3
"""Vertical Monsoon: camera person detection -> serial Arduino controller.
Uses OpenCV's built-in HOG person detector (no model download required).
For best results, aim camera at standing people with sufficient lighting.
"""
import argparse
import json
import time
from pathlib import Path

import cv2
import serial
from serial import SerialException

HERE = Path(__file__).resolve().parent

def load_config():
    with open(HERE / "config.json", encoding="utf-8") as f:
        return json.load(f)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate", action="store_true", help="Do not connect to Arduino")
    parser.add_argument("--port", help="Override serial port (e.g. COM3, /dev/ttyACM0)")
    args = parser.parse_args()
    cfg = load_config()
    simulate = args.simulate or cfg["simulation_mode"]
    port = args.port or cfg["serial_port"]
    board = None
    camera = None
    active = False
    seen_count = 0
    last_seen = None
    last_send = 0.0
    frame_no = 0
    boxes = []
    try:
        if not simulate:
            board = serial.Serial(port, int(cfg["baud_rate"]), timeout=0.2, write_timeout=1)
            time.sleep(2.5)  # Arduino resets when serial opens
            board.reset_input_buffer()
            print(f"Connected to Arduino on {port}")
        else:
            print("SIMULATION MODE: no Arduino commands will be sent")

        camera = cv2.VideoCapture(int(cfg["camera_index"]))
        if not camera.isOpened():
            raise RuntimeError("Cannot open camera. Check camera_index and camera permissions.")

        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        print("Press Q in preview or Ctrl+C to quit.")
        while True:
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError("Camera stopped providing frames.")
            frame_no += 1
            now = time.monotonic()
            if frame_no % max(1, int(cfg["detect_every_n_frames"])) == 0:
                h, w = frame.shape[:2]
                scale = min(1.0, 640.0 / w)
                small = cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame
                found, weights = hog.detectMultiScale(small, winStride=(8, 8),
                                                     padding=(8, 8), scale=1.05)
                boxes = []
                for (x, y, bw, bh), weight in zip(found, weights):
                    if float(weight) >= float(cfg["confidence_threshold"]):
                        boxes.append((int(x / scale), int(y / scale),
                                      int(bw / scale), int(bh / scale)))
                if boxes:
                    seen_count += 1
                    last_seen = now
                else:
                    seen_count = 0

            if not active and seen_count >= int(cfg["trigger_confirm_frames"]):
                active = True
                print("PERSON DETECTED -> ON")
                last_send = 0
            if active and last_seen is not None and now - last_seen >= float(cfg["release_delay_seconds"]):
                active = False
                print("PERSON ABSENT -> OFF")
                last_send = 0

            if now - last_send >= float(cfg["command_repeat_seconds"]):
                cmd = "ON\n" if active else "OFF\n"
                if board:
                    board.write(cmd.encode("ascii"))
                last_send = now

            if cfg["show_preview"]:
                for x, y, bw, bh in boxes:
                    cv2.rectangle(frame, (x, y), (x+bw, y+bh), (0, 255, 0), 2)
                cv2.putText(frame, "PERSON DETECTED" if active else "WAITING",
                            (12, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                            (0, 255, 0) if active else (0, 200, 255), 2)
                cv2.imshow("Vertical Monsoon - press Q to quit", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except (SerialException, RuntimeError) as e:
        print(f"ERROR: {e}")
        raise SystemExit(1)
    except KeyboardInterrupt:
        pass
    finally:
        if board:
            try:
                board.write(b"OFF\n")
                board.flush()
                time.sleep(0.1)
            except SerialException:
                pass
            board.close()
        if camera:
            camera.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
