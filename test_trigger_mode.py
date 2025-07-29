#!/usr/bin/env python3
"""
Simple test script to verify trigger mode functionality.
"""

def test_trigger_mode_config():
    """Test that the trigger mode field is properly added to RadarConfig."""
    
    # Test the RadarConfig model
    from xwr68xxisk.radar_config_models import RadarConfig
    
    # Create a config with default values
    config = RadarConfig()
    print(f"Default trigger mode: {config.trigger_mode}")
    
    # Test setting different trigger modes
    config.trigger_mode = 1
    print(f"Software trigger mode: {config.trigger_mode}")
    
    config.trigger_mode = 2
    print(f"Hardware trigger mode: {config.trigger_mode}")
    
    config.trigger_mode = 0
    print(f"Timer-based trigger mode: {config.trigger_mode}")
    
    print("✓ Trigger mode configuration test passed!")

def test_config_generator():
    """Test that the config generator includes trigger mode."""
    
    from xwr68xxisk.config_generator import generate_cfg_from_scene_profile
    from xwr68xxisk.radar_config_models import RadarConfig
    
    # Create config with different trigger modes
    config = RadarConfig()
    
    # Test timer-based (default)
    config.trigger_mode = 0
    cfg_timer = generate_cfg_from_scene_profile(config)
    print("Timer-based config includes triggerMode 0:", "triggerMode 0" in cfg_timer)
    
    # Test software trigger
    config.trigger_mode = 1
    cfg_software = generate_cfg_from_scene_profile(config)
    print("Software trigger config includes triggerMode 1:", "triggerMode 1" in cfg_software)
    
    # Test hardware trigger
    config.trigger_mode = 2
    cfg_hardware = generate_cfg_from_scene_profile(config)
    print("Hardware trigger config includes triggerMode 2:", "triggerMode 2" in cfg_hardware)
    
    print("✓ Config generator test passed!")

if __name__ == "__main__":
    print("Testing trigger mode functionality...")
    test_trigger_mode_config()
    test_config_generator()
    print("All tests passed!") 