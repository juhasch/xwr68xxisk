import click
import rerun as rr
import re
from typing import List, Tuple, Dict, Optional
from datetime import datetime
import time
import cv2

# --- SRT Parsing Utility ---
def parse_dji_srt(srt_path: str) -> List[Dict]:
    """
    Parse a DJI SRT file and extract frame timestamps and metadata.

    Parameters
    ----------
    srt_path : str
        Path to the SRT file.

    Returns
    -------
    List[Dict]
        List of dicts with keys: 'frame', 'start', 'end', 'timestamp', 'meta'.
    """
    pattern_time = re.compile(r"(\d+):(\d+):(\d+),(\d+)")
    pattern_dji_ts = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")
    frames = []
    with open(srt_path, 'r') as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        if lines[i].strip().isdigit():
            frame_idx = int(lines[i].strip())
            time_range = lines[i+1].strip()
            start_str, end_str = time_range.split(' --> ')
            def parse_time(s):
                m = pattern_time.match(s)
                if not m:
                    return 0.0
                h, m_, s_, ms = map(int, m.groups())
                return h*3600 + m_*60 + s_ + ms/1000.0
            start_sec = parse_time(start_str)
            end_sec = parse_time(end_str)
            # Next lines: metadata
            meta_lines = []
            j = i+2
            while j < len(lines) and not lines[j].strip().isdigit():
                meta_lines.append(lines[j].strip())
                j += 1
            # Extract DJI timestamp (YYYY-MM-DD HH:MM:SS.sss)
            dji_ts = None
            for l in meta_lines:
                m = pattern_dji_ts.match(l)
                if m:
                    dji_ts = m.group(1)
                    break
            frames.append({
                'frame': frame_idx,
                'start': start_sec,
                'end': end_sec,
                'timestamp': dji_ts,
                'meta': meta_lines
            })
            i = j
        else:
            i += 1
    return frames

@click.command()
@click.argument('video_file', type=click.Path(exists=True))
@click.argument('srt_file', type=click.Path(exists=True))
@click.option('--spawn/--no-spawn', default=True, help='Spawn rerun viewer window (default: True)')
@click.option('--play/--no-play', default=False, help='Play the video as a time sequence (default: False)')
@click.option('--speed', type=float, default=1.0, show_default=True, help='Playback speed multiplier for --play (1.0 = real time)')
@click.option('--resize', type=(int, int), default=None, help='Resize frames to WIDTH HEIGHT (e.g. --resize 640 360)')
@click.option('--max-fps', type=float, default=None, help='Maximum frames per second to send (default: all frames)')
def main(video_file: str, srt_file: str, spawn: bool, play: bool, speed: float, resize: Optional[Tuple[int, int]], max_fps: Optional[float]):
    """
    Stream VIDEO_FILE to rerun, using SRT_FILE for frame timestamps and metadata.
    Extracts frames using OpenCV and sends them as compressed images to rerun.
    """
    # Parse SRT
    frames = parse_dji_srt(srt_file)
    if not frames:
        click.echo("No frames found in SRT file.")
        return
    rr.init("video", spawn=spawn)
    # Open video
    cap = cv2.VideoCapture(video_file)
    if not cap.isOpened():
        click.echo(f"Failed to open video file: {video_file}")
        return
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    click.echo(f"Video: {total_frames} frames @ {video_fps:.2f} fps")
    # Throttle logic
    if max_fps is not None and max_fps > 0:
        frame_interval = int(round(video_fps / max_fps))
    else:
        frame_interval = 1
    # Main loop
    sent_count = 0
    for i, frame_info in enumerate(frames):
        frame_idx = frame_info['frame'] - 1  # SRT is 1-based, OpenCV is 0-based
        # Throttle frame rate
        if frame_interval > 1 and (frame_idx % frame_interval != 0):
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, img_bgr = cap.read()
        if not ret:
            click.echo(f"Failed to read frame {frame_idx+1}")
            continue
        if resize is not None:
            img_bgr = cv2.resize(img_bgr, resize)
        # Use DJI timestamp if available, else fallback to start_sec
        ts = frame_info['timestamp']
        if ts:
            try:
                # Parse DJI timestamp to datetime, then to unix timestamp (float seconds)
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S.%f")
                timestamp = dt.timestamp()
            except Exception:
                timestamp = frame_info['start']
        else:
            timestamp = frame_info['start']
        # Set rerun time for this frame
        rr.set_time(timeline="video/frames", timestamp=timestamp)
        # Log the image (compressed JPEG)
        rr.log("world/camera/image/rgb", rr.Image(img_bgr, color_model="BGR").compress(jpeg_quality=95))
        sent_count += 1
        click.echo(f"Sent frame {frame_idx+1}/{total_frames} (SRT idx {i+1}/{len(frames)}) at t={timestamp:.3f}s")
        # Playback timing
        if play and i < len(frames) - 1:
            next_info = frames[i+1]
            next_ts = next_info['timestamp']
            if next_ts:
                try:
                    next_dt = datetime.strptime(next_ts, "%Y-%m-%d %H:%M:%S.%f")
                    next_time = next_dt.timestamp()
                except Exception:
                    next_time = next_info['start']
            else:
                next_time = next_info['start']
            dt = next_time - timestamp
            if dt > 0:
                time.sleep(dt / speed)
    cap.release()
    click.echo(f"Sent {sent_count} frames to rerun viewer.")

if __name__ == "__main__":
    main() 