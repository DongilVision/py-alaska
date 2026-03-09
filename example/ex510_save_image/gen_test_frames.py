# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
# Project : ALASKA 2.0 — Multiprocess Task Framework
# Date    : 2026-03-07
"""
gen_test_frames — SimCam 테스트 영상 생성기
==========================================
프레임 번호 + 아날로그 시계가 그려진 테스트 이미지를 생성한다.
SaveImage 출력 형식과 동일한 디렉토리/파일명 → SimCam의 replay_path로 직접 사용.

사용법:
    # 기본 — 100프레임, 2048x2448 BGR, 30fps, PNG
    python gen_test_frames.py --output D:/images_test --count 100

    # 커스텀
    python gen_test_frames.py --output D:/images_test --count 500 \\
        --width 1280 --height 1024 --channels 1 --fps 60

    # Python 코드에서
    from gen_test_frames import generate_test_frames
    path = generate_test_frames("D:/images_test", count=200, fps=30)

설계서: doc/6020____sim_cam기능설계.txt §15
"""

import json
import math
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


def _draw_clock(img, cx, cy, radius, frame_num, total, timestamp, color):
    """아날로그 시계 — 원형 + 눈금 + 분침(진행율) + 초침(시간)."""

    # 원형 외곽
    cv2.circle(img, (cx, cy), radius, color, 2)

    # 12/3/6/9시 눈금
    for hour, label in [(0, "12"), (3, "3"), (6, "6"), (9, "9")]:
        angle = math.radians(hour * 30 - 90)
        tx = int(cx + (radius + 20) * math.cos(angle))
        ty = int(cy + (radius + 20) * math.sin(angle))
        cv2.putText(img, label, (tx - 10, ty + 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # 분침 — 프레임 진행율 (0~total → 0~360)
    progress = frame_num / max(total, 1)
    min_angle = math.radians(progress * 360 - 90)
    min_len = int(radius * 0.7)
    mx = int(cx + min_len * math.cos(min_angle))
    my = int(cy + min_len * math.sin(min_angle))
    cv2.arrowedLine(img, (cx, cy), (mx, my), color, 3, tipLength=0.2)

    # 초침 — 시간 기반 (60초 1회전)
    sec = timestamp % 60
    sec_angle = math.radians(sec * 6 - 90)
    sec_len = int(radius * 0.9)
    sx = int(cx + sec_len * math.cos(sec_angle))
    sy = int(cy + sec_len * math.sin(sec_angle))
    red = (0, 0, 255) if len(img.shape) == 3 else color
    cv2.arrowedLine(img, (cx, cy), (sx, sy), red, 2, tipLength=0.15)

    # 중심점
    cv2.circle(img, (cx, cy), 5, color, -1)


def _render_frame(frame_num, total, width, height, channels,
                  timestamp, fps, bg_color, text_color):
    """단일 프레임 렌더링."""

    # 1. 배경 생성
    if channels == 3:
        img = np.full((height, width, 3), bg_color, dtype=np.uint8)
    else:
        img = np.full((height, width), bg_color[0], dtype=np.uint8)

    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = min(width, height) / 800.0

    # 2. 프레임 번호 (좌상단)
    text = f"FRAME: {frame_num:04d} / {total:04d}"
    cv2.putText(img, text, (50, int(80 * scale)),
                font, scale * 1.5, text_color, 3)

    # 3. 타임스탬프
    dt = datetime.fromtimestamp(timestamp)
    time_text = f"TIME: {dt.strftime('%H:%M:%S')}.{dt.microsecond // 1000:03d}"
    cv2.putText(img, time_text, (50, int(160 * scale)),
                font, scale, text_color, 2)

    # 4. 아날로그 시계 (화면 중앙)
    cx, cy = width // 2, height // 2
    radius = int(min(width, height) * 0.2)
    _draw_clock(img, cx, cy, radius, frame_num, total,
                timestamp, text_color)

    # 5. 하단 정보 바
    info = f"SimCam Test | {width}x{height} | {fps:.0f}fps"
    cv2.putText(img, info, (50, height - int(50 * scale)),
                font, scale * 0.7, text_color, 2)

    return img


def generate_test_frames(
    output_dir,
    count=100,
    width=2448,
    height=2048,
    channels=3,
    fps=30.0,
    image_format="png",
    session="S001",
    bg_color=(32, 32, 32),
    text_color=(0, 255, 0),
):
    """테스트 영상 시퀀스 생성.

    SaveImage 출력 형식과 동일한 디렉토리/파일명으로 생성:
        output_dir/YYYY/MM/DD/S001/img_0001_YYYYMMDD_HHMMSS_mmm.png

    SimCam의 replay_path로 직접 사용 가능.

    Returns:
        str: 생성된 세션 디렉토리 경로
    """
    now = datetime.now()
    base_dir = (Path(output_dir)
                / f"{now.year}" / f"{now.month:02d}" / f"{now.day:02d}"
                / session)
    base_dir.mkdir(parents=True, exist_ok=True)

    interval = 1.0 / fps
    base_ts = now.timestamp()
    ext = f".{image_format}"

    for i in range(1, count + 1):
        ts = base_ts + (i - 1) * interval
        dt = datetime.fromtimestamp(ts)
        ms = dt.microsecond // 1000

        # SaveImage 파일명 형식
        filename = (f"img_{i:04d}_{dt.strftime('%Y%m%d_%H%M%S')}"
                    f"_{ms:03d}{ext}")

        img = _render_frame(i, count, width, height, channels,
                            ts, fps, bg_color, text_color)

        filepath = str(base_dir / filename)
        cv2.imwrite(filepath, img)

        if i % 50 == 0 or i == count:
            print(f"  [{i}/{count}] {filename}")

    # manifest.json
    manifest = {
        "session": session,
        "camera": "test_generator",
        "shape": [height, width, channels] if channels > 1
                 else [height, width],
        "format": image_format,
        "fps": fps,
        "count": count,
        "start_time": datetime.fromtimestamp(base_ts).isoformat(),
        "end_time": datetime.fromtimestamp(
            base_ts + (count - 1) * interval).isoformat(),
    }
    with open(base_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated {count} frames -> {base_dir}")
    return str(base_dir)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="SimCam 테스트 영상 생성기")
    parser.add_argument("--output", "-o", required=True,
                        help="출력 디렉토리 (SimCam replay_path)")
    parser.add_argument("--count", "-n", type=int, default=100,
                        help="생성 프레임 수 (기본 100)")
    parser.add_argument("--width", type=int, default=2448,
                        help="이미지 너비 (기본 2448)")
    parser.add_argument("--height", type=int, default=2048,
                        help="이미지 높이 (기본 2048)")
    parser.add_argument("--channels", type=int, default=3, choices=[1, 3],
                        help="채널 수 (1=Gray, 3=BGR, 기본 3)")
    parser.add_argument("--fps", type=float, default=30.0,
                        help="가상 fps (기본 30)")
    parser.add_argument("--format", dest="image_format", default="png",
                        choices=["png", "bmp", "jpg"],
                        help="이미지 포맷 (기본 png)")
    parser.add_argument("--session", default="S001",
                        help="세션 디렉토리명 (기본 S001)")
    args = parser.parse_args()

    generate_test_frames(
        output_dir=args.output,
        count=args.count,
        width=args.width,
        height=args.height,
        channels=args.channels,
        fps=args.fps,
        image_format=args.image_format,
        session=args.session,
    )
