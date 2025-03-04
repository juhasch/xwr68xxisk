import argparse
import ast
import os
import logging
import re

import pyarrow as pa
from dora import Node
import panel as pn
from .gui import RadarGUI
from .record import main as record_main

RUNNER_CI = True if os.getenv("CI") == "true" else False


def start_gui(args):
    """Start the Panel GUI server."""
    radar_gui = RadarGUI()
    pn.serve(radar_gui.layout, port=args.port, show=True)


def send_data(args):
    """Send data using PyArrow."""
    data = os.getenv("DATA", args.data)

    node = Node(
        args.name,
    )  # provide the name to connect to the dataflow if dynamic node

    if data is None:
        raise ValueError(
            "No data provided. Please specify `DATA` environment argument or as `--data` argument",
        )
    try:
        data = ast.literal_eval(data)
    except ValueError:
        print("Passing input as string")
    if isinstance(data, list):
        data = pa.array(data)  # initialize pyarrow array
    elif isinstance(data, str) or isinstance(data, int) or isinstance(data, float):
        data = pa.array([data])
    else:
        data = pa.array(data)  # initialize pyarrow array
    node.send_output("data", data)


def validate_serial(value):
    """Validate serial number format (8 hexadecimal characters)."""
    if not re.match(r'^[0-9A-F]{8}$', value):
        raise argparse.ArgumentTypeError('Serial number must be 8 hexadecimal characters (0-9, A-F)')
    return value


def main():
    parser = argparse.ArgumentParser(description="XWR68XX ISK Radar Tools")
    parser.add_argument('--log-level', 
                       default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Set the logging level (default: INFO)')
    parser.add_argument('--serial-number',
                       type=validate_serial,
                       help='Radar serial number in hex format "1234ABCD"')

    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # GUI subcommand
    gui_parser = subparsers.add_parser('gui', help='Start the radar GUI')
    gui_parser.add_argument('--port', type=int, default=5006,
                           help='Port to run the Panel server on (default: 5006)')
    gui_parser.set_defaults(func=start_gui)

    # Record subcommand
    record_parser = subparsers.add_parser('record', help='Record radar data to CSV file')
    record_parser.set_defaults(func=lambda _: record_main(serial_number=args.serial_number))

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(module)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    
    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
