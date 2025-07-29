#!/usr/bin/env python3
"""
Simple test script for trigger mode functionality.
This can be run without pytest to verify the implementation works.
"""

import sys
import os

# Add the project root to the path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from xwr68xxisk.radar_config import TriggerModeCommand, RadarProfile
    print("✓ Successfully imported radar_config module")
except ImportError as e:
    print(f"✗ Failed to import radar_config module: {e}")
    print("This might be due to missing dependencies. Try installing with:")
    print("pip install -e .")
    sys.exit(1)


def test_trigger_mode_command():
    """Test basic trigger mode command functionality"""
    print("\n=== Testing TriggerModeCommand ===")
    
    # Test creation
    try:
        cmd = TriggerModeCommand([0])
        print("✓ Created timer-based trigger command")
        assert cmd.name == 'triggerMode'
        assert cmd.mode == 0
        assert cmd.is_timer_based is True
        assert cmd.is_software_trigger is False
        assert cmd.is_hardware_trigger is False
        print("✓ Timer-based trigger properties correct")
    except Exception as e:
        print(f"✗ Failed to create timer-based trigger: {e}")
        return False
    
    # Test software trigger
    try:
        cmd = TriggerModeCommand([1])
        print("✓ Created software trigger command")
        assert cmd.mode == 1
        assert cmd.is_software_trigger is True
        print("✓ Software trigger properties correct")
    except Exception as e:
        print(f"✗ Failed to create software trigger: {e}")
        return False
    
    # Test hardware trigger
    try:
        cmd = TriggerModeCommand([2])
        print("✓ Created hardware trigger command")
        assert cmd.mode == 2
        assert cmd.is_hardware_trigger is True
        print("✓ Hardware trigger properties correct")
    except Exception as e:
        print(f"✗ Failed to create hardware trigger: {e}")
        return False
    
    # Test mode changing
    try:
        cmd = TriggerModeCommand([0])
        cmd.mode = 1
        assert cmd.mode == 1
        cmd.mode = 2
        assert cmd.mode == 2
        print("✓ Mode changing works correctly")
    except Exception as e:
        print(f"✗ Failed to change modes: {e}")
        return False
    
    # Test validation
    try:
        cmd = TriggerModeCommand([0])
        cmd.mode = 3  # Invalid mode
        print("✗ Should have raised ValueError for invalid mode")
        return False
    except ValueError:
        print("✓ Correctly rejected invalid trigger mode")
    except Exception as e:
        print(f"✗ Unexpected error during validation: {e}")
        return False
    
    # Test string conversion
    try:
        cmd = TriggerModeCommand([1])
        assert cmd.to_string() == "triggerMode 1"
        print("✓ String conversion works correctly")
    except Exception as e:
        print(f"✗ Failed string conversion: {e}")
        return False
    
    return True


def test_radar_profile_integration():
    """Test trigger mode integration with RadarProfile"""
    print("\n=== Testing RadarProfile Integration ===")
    
    # Test adding trigger command to profile
    try:
        profile = RadarProfile("test_profile")
        trigger_cmd = TriggerModeCommand([0])
        profile.add_command(trigger_cmd)
        print("✓ Added trigger command to profile")
        
        # Test getting command
        retrieved_cmd = profile.get_command('triggerMode')
        assert retrieved_cmd is not None
        assert retrieved_cmd.mode == 0
        print("✓ Retrieved trigger command from profile")
    except Exception as e:
        print(f"✗ Failed to add/get trigger command: {e}")
        return False
    
    # Test set_trigger_mode helper
    try:
        profile = RadarProfile("test_profile")
        trigger_cmd = TriggerModeCommand([0])
        profile.add_command(trigger_cmd)
        
        assert profile.set_trigger_mode(1) is True
        assert trigger_cmd.mode == 1
        print("✓ set_trigger_mode helper works")
    except Exception as e:
        print(f"✗ Failed set_trigger_mode helper: {e}")
        return False
    
    # Test parsing from string
    try:
        profile_str = "triggerMode 2\nsensorStop"
        profile = RadarProfile.from_string(profile_str)
        trigger_cmd = profile.get_command('triggerMode')
        assert trigger_cmd is not None
        assert trigger_cmd.mode == 2
        print("✓ Parsed trigger mode from string")
    except Exception as e:
        print(f"✗ Failed to parse from string: {e}")
        return False
    
    # Test converting to string
    try:
        profile = RadarProfile("test_profile")
        trigger_cmd = TriggerModeCommand([1])
        profile.add_command(trigger_cmd)
        
        profile_str = profile.to_string()
        assert "triggerMode 1" in profile_str
        print("✓ Converted profile to string correctly")
    except Exception as e:
        print(f"✗ Failed to convert to string: {e}")
        return False
    
    return True


def main():
    """Run all tests"""
    print("Trigger Mode Functionality Test")
    print("=" * 40)
    
    success = True
    
    # Test trigger mode command
    if not test_trigger_mode_command():
        success = False
    
    # Test radar profile integration
    if not test_radar_profile_integration():
        success = False
    
    print("\n" + "=" * 40)
    if success:
        print("✓ All tests passed!")
        print("Trigger mode functionality is working correctly.")
    else:
        print("✗ Some tests failed!")
        print("Please check the implementation.")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 