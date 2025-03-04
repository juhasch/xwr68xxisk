""" Dora-rs node"""

import logging
import os
import ast
import pyarrow as pa
from dora import Node
import numpy as np
import time
import random
import json
from xwr68xxisk.radar import RadarConnection, create_radar
from xwr68xxisk.parse import RadarData

DEFAULT_CONFIG_FILE = "configs/xwr68xxconfig.cfg"
serial_number = None



def start_dora_node():
    """Start the dora-rs node interface."""
    node = Node("RadarNode")
    radar = None
    radar_base = RadarConnection()
    
    print("Starting radar")
    radar_type, config_file = radar_base.detect_radar_type()
    if not radar_type:
        raise RadarConnectionError("No supported radar detected")
    
    print(f"Creating {radar_type} radar instance")
    radar = create_radar(radar_type)            
    radar.connect(config_file)
    radar.configure_and_start()


    for event in node:
        if event["type"] == "STOP":
            print("Stopping radar")
            radar.stop()
            radar.disconnect()
        elif event["type"] == "INPUT" and event["id"] == "tick":
            data = RadarData(radar)
            print('new data')
            if data is not None and data.pc is not None:
                x, y, z, velocity, snr, rcs = data.pc
                frame_number = data.frame_number if data.frame_number is not None else 0
                
                metadata = event["metadata"]
                metadata['frame_number'] = frame_number
                metadata['num_points'] = len(x)
                metadata['dimensions'] = json.dumps({0:'x', 1:'y', 2:'z', 3:'doppler', 4:'snr', 5:'rcs'})

                pc = np.array([x,y,z,velocity,snr,rcs]).ravel()
                pointcloud_array = pa.array(pc, type=pa.float32())
                print(f'Sending pointcloud {frame_number}')
                # Senden des Arrays
                node.send_output("pointcloud", pointcloud_array, metadata)


#start_dora_node()
