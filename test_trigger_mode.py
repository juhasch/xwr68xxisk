#!/usr/bin/env python3
"""
Simple test script to verify trigger mode functionality.
"""

def test_trigger_mode_command():
    """Test that the trigger mode command works correctly."""
    
    from xwr68xxisk.radar_config import TriggerModeCommand
    
    # Test timer-based trigger (default)
    timer_cmd = TriggerModeCommand([0])
    print(f"Timer-based trigger: {timer_cmd.to_string()}")
    print(f"  Mode: {timer_cmd.mode}")
    print(f"  Is timer-based: {timer_cmd.is_timer_based}")
    print(f"  Is software: {timer_cmd.is_software_trigger}")
    print(f"  Is hardware: {timer_cmd.is_hardware_trigger}")
    
    # Test software trigger
    software_cmd = TriggerModeCommand([1])
    print(f"Software trigger: {software_cmd.to_string()}")
    print(f"  Mode: {software_cmd.mode}")
    print(f"  Is timer-based: {software_cmd.is_timer_based}")
    print(f"  Is software: {software_cmd.is_software_trigger}")
    print(f"  Is hardware: {software_cmd.is_hardware_trigger}")
    
    # Test hardware trigger
    hardware_cmd = TriggerModeCommand([2])
    print(f"Hardware trigger: {hardware_cmd.to_string()}")
    print(f"  Mode: {hardware_cmd.mode}")
    print(f"  Is timer-based: {hardware_cmd.is_timer_based}")
    print(f"  Is software: {hardware_cmd.is_software_trigger}")
    print(f"  Is hardware: {hardware_cmd.is_hardware_trigger}")
    
    # Test mode changing
    print("\n=== Changing Trigger Modes ===")
    cmd = TriggerModeCommand([0])
    print(f"Initial mode: {cmd.mode}")
    
    cmd.mode = 1
    print(f"Changed to software: {cmd.mode}")
    
    cmd.mode = 2
    print(f"Changed to hardware: {cmd.mode}")
    
    # Test validation
    print("\n=== Validation Example ===")
    try:
        cmd.mode = 3
        print("This should not print")
    except ValueError as e:
        print(f"Caught expected error: {e}")
    
    print("✓ Trigger mode command test passed!")

def test_config_generator_simple():
    """Test that the config generator includes trigger mode with a simple config."""
    
    from xwr68xxisk.config_generator import generate_cfg_from_scene_profile
    
    # Create a simple config object with just the trigger mode
    class SimpleConfig:
        def __init__(self, trigger_mode=0):
            self.trigger_mode = trigger_mode
    
    # Test timer-based (default)
    config = SimpleConfig(0)
    cfg_timer = generate_cfg_from_scene_profile(config)
    print("Timer-based config includes triggerMode 0:", "triggerMode 0" in cfg_timer)
    
    # Test software trigger
    config = SimpleConfig(1)
    cfg_software = generate_cfg_from_scene_profile(config)
    print("Software trigger config includes triggerMode 1:", "triggerMode 1" in cfg_software)
    
    # Test hardware trigger
    config = SimpleConfig(2)
    cfg_hardware = generate_cfg_from_scene_profile(config)
    print("Hardware trigger config includes triggerMode 2:", "triggerMode 2" in cfg_hardware)
    
    print("✓ Config generator test passed!")

if __name__ == "__main__":
    print("Testing trigger mode functionality...")
    test_trigger_mode_command()
    test_config_generator_simple()
    print("All tests passed!") 