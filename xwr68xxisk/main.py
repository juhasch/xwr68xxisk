import argparse
import os
import logging
import re

from .record import main as record_main
from .radar import DEFAULT_BRIDGE_CONTROL_ENDPOINT, DEFAULT_BRIDGE_DATA_ENDPOINT

RUNNER_CI = True if os.getenv("CI") == "true" else False

def start_gui(args):
    """Start the Panel GUI server."""
    # Import panel and RadarGUI only when needed
    import panel as pn
    from .gui import RadarGUI
    radar_gui = RadarGUI(
        transport=args.transport,
        control_endpoint=args.bridge_control,
        data_endpoint=args.bridge_data,
    )
    
    # Configure origins for websocket connections
    origins = [f'localhost:{args.port}']
    
    # Add the server IP to origins if remote access is enabled
    if args.remote:
        origins.append(f'0.0.0.0:{args.port}')
        address='0.0.0.0'
    else:
        address='localhost'
    
    # Configure and serve the application
    pn.serve(
        radar_gui.layout,
        port=args.port,
        address=address,
        allow_websocket_origin=origins,
        show=not args.noshow,
        start=True
    )


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
    parser.add_argument(
        '--transport',
        choices=['auto', 'serial', 'network'],
        default='auto',
        help='Select connection transport (auto=prefer serial, fallback to network bridge)'
    )
    parser.add_argument(
        '--bridge-control',
        default=DEFAULT_BRIDGE_CONTROL_ENDPOINT,
        help='Radar bridge ZeroMQ control endpoint (when using network transport)'
    )
    parser.add_argument(
        '--bridge-data',
        default=DEFAULT_BRIDGE_DATA_ENDPOINT,
        help='Radar bridge ZeroMQ data endpoint (when using network transport)'
    )

    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # GUI subcommand
    gui_parser = subparsers.add_parser('gui', help='Start the radar GUI')
    gui_parser.add_argument('--port', type=int, default=5006,
                           help='Port to run the Panel server on (default: 5006)')
    gui_parser.add_argument('--noshow', action='store_true',
                           help='Do not automatically open the browser')
    gui_parser.add_argument('--remote', action='store_true',
                           help='Enable remote access to the GUI')
    gui_parser.set_defaults(func=start_gui)

    # Record subcommand
    record_parser = subparsers.add_parser('record', help='Record radar data to CSV file')
    record_parser.add_argument('--profile', default=os.path.join('configs', 'user_profile.cfg'),
                           help='Path to the radar profile configuration file')
    record_parser.set_defaults(
        func=lambda args: record_main(
            args.serial_number,
            args.profile,
            args.transport,
            args.bridge_control,
            args.bridge_data,
        )
    )

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
