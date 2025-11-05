import click
import numpy as np
import pandas as pd
import rerun as rr
import time
from datetime import datetime

# --- Utility functions ---
def scale_rcs_to_radius(rcs: np.ndarray, min_radius: float = 0.01, max_radius: float = 0.2) -> np.ndarray:
    """
    Scale RCS (radar cross section) values to radii for visualization.

    Parameters
    ----------
    rcs : np.ndarray
        Array of RCS values (dBsm).
    min_radius : float
        Minimum radius for visualization.
    max_radius : float
        Maximum radius for visualization.

    Returns
    -------
    np.ndarray
        Scaled radii.
    """
    # Normalize RCS to [0, 1] using percentiles for robustness
    rcs_min, rcs_max = np.percentile(rcs, 5), np.percentile(rcs, 95)
    rcs_clipped = np.clip(rcs, rcs_min, rcs_max)
    norm = (rcs_clipped - rcs_min) / (rcs_max - rcs_min + 1e-6)
    return min_radius + norm * (max_radius - min_radius)

def velocity_to_color(velocity: np.ndarray) -> np.ndarray:
    """
    Map velocity to RGB color for visualization.

    Parameters
    ----------
    velocity : np.ndarray
        Array of velocity values (m/s).

    Returns
    -------
    np.ndarray
        Array of uint8 RGB colors (N, 3).
    """
    # Normalize velocity to [0, 1] using percentiles
    vmin, vmax = np.percentile(velocity, 5), np.percentile(velocity, 95)
    vnorm = np.clip((velocity - vmin) / (vmax - vmin + 1e-6), 0, 1)
    # Use a simple blue-red colormap
    colors = np.zeros((len(velocity), 3), dtype=np.uint8)
    colors[:, 0] = (255 * vnorm).astype(np.uint8)  # Red channel
    colors[:, 2] = (255 * (1 - vnorm)).astype(np.uint8)  # Blue channel
    return colors

@click.command()
@click.argument('csv_file', type=click.Path(exists=True))
@click.option('--frame', type=int, default=None, help='Only show a specific frame (default: all)')
@click.option('--spawn/--no-spawn', default=True, help='Spawn rerun viewer window (default: True)')
@click.option('--play/--no-play', default=False, help='Play the CSV as a time sequence (default: False)')
@click.option('--speed', type=float, default=1.0, show_default=True, help='Playback speed multiplier for --play (1.0 = real time)')
@click.option('--fps', type=float, default=None, help='Override frame rate for playback (frames per second), ignores actual timing')
def main(csv_file: str, frame: int, spawn: bool, play: bool, speed: float, fps: float):
    """
    Visualize radar point cloud CSV_FILE as a 3D point cloud in rerun.
    """
    # Read CSV
    df = pd.read_csv(csv_file)
    if frame is not None and not play:
        df = df[df['frame'] == frame]
    if df.empty:
        click.echo(f"No data for frame {frame}" if frame is not None else "No data in file.")
        return

    rr.init("misc", spawn=spawn)

    if play:
        # Parse timestamps
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        timestamps = df['timestamp'].sort_values().unique()
        if len(timestamps) < 2:
            click.echo("Not enough timestamps for playback.")
            return
        
        # Get the first timestamp as reference point
        start_time = timestamps[0]
        click.echo(f"Starting playback from {start_time}")
        
        for i, ts in enumerate(timestamps):
            frame_df = df[df['timestamp'] == ts]
            positions = frame_df[['x', 'y', 'z']].to_numpy(dtype=np.float32)
            velocity = frame_df['velocity'].to_numpy(dtype=np.float32)
            rcs = frame_df['rcs'].to_numpy(dtype=np.float32)
            radii = scale_rcs_to_radius(rcs)
            colors = velocity_to_color(velocity)
            
            # Set time relative to start for proper temporal playback
            elapsed_seconds = (ts - start_time).total_seconds()
            rr.set_time(timestamp=elapsed_seconds)
            
            rr.log("radar/points", rr.Points3D(positions, colors=colors, radii=radii))
            click.echo(f"Frame {i+1}/{len(timestamps)}: {len(positions)} points at {ts} (t={elapsed_seconds:.3f}s)")
            
            # Sleep to simulate real time (unless last frame)
            if i < len(timestamps) - 1:
                if fps is not None:
                    # Use fixed frame rate
                    dt = 1.0 / fps
                else:
                    # Use actual timing from data
                    next_ts = timestamps[i+1]
                    dt = (next_ts - ts).total_seconds() / speed
                if dt > 0:
                    time.sleep(dt)
    else:
        # Single frame or all points
        if frame is not None:
            # Single frame mode
            positions = df[['x', 'y', 'z']].to_numpy(dtype=np.float32)
            velocity = df['velocity'].to_numpy(dtype=np.float32)
            rcs = df['rcs'].to_numpy(dtype=np.float32)
            radii = scale_rcs_to_radius(rcs)
            colors = velocity_to_color(velocity)
            rr.set_time_sequence("frame", frame)
            rr.log("radar/points", rr.Points3D(positions, colors=colors, radii=radii))
            click.echo(f"Sent {len(positions)} points from frame {frame} to rerun viewer.")
        else:
            # All frames mode - show each frame as a separate timeline entry
            frames = df['frame'].unique()
            click.echo(f"Visualizing {len(frames)} frames with {len(df)} total points")
            for frame_id in sorted(frames):
                frame_df = df[df['frame'] == frame_id]
                positions = frame_df[['x', 'y', 'z']].to_numpy(dtype=np.float32)
                velocity = frame_df['velocity'].to_numpy(dtype=np.float32)
                rcs = frame_df['rcs'].to_numpy(dtype=np.float32)
                radii = scale_rcs_to_radius(rcs)
                colors = velocity_to_color(velocity)
                rr.set_time_sequence("frame", frame_id)
                rr.log("radar/points", rr.Points3D(positions, colors=colors, radii=radii))
            click.echo(f"Sent {len(df)} points across {len(frames)} frames to rerun viewer.")

if __name__ == "__main__":
    main() 