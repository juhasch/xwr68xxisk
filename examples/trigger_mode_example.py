#!/usr/bin/env python3
"""
Example demonstrating the new trigger mode functionality.

This example shows how to:
1. Create trigger mode commands
2. Set different trigger modes
3. Use trigger mode in radar profiles
"""

from xwr68xxisk.radar_config import TriggerModeCommand, RadarProfile


def demonstrate_trigger_mode_commands():
    """Demonstrate basic trigger mode command usage"""
    print("=== Trigger Mode Command Examples ===")
    
    # Create timer-based trigger (default)
    timer_cmd = TriggerModeCommand([0])
    print(f"Timer-based trigger: {timer_cmd.to_string()}")
    print(f"  Is timer-based: {timer_cmd.is_timer_based}")
    print(f"  Is software: {timer_cmd.is_software_trigger}")
    print(f"  Is hardware: {timer_cmd.is_hardware_trigger}")
    
    # Create software trigger
    software_cmd = TriggerModeCommand([1])
    print(f"Software trigger: {software_cmd.to_string()}")
    print(f"  Is timer-based: {software_cmd.is_timer_based}")
    print(f"  Is software: {software_cmd.is_software_trigger}")
    print(f"  Is hardware: {software_cmd.is_hardware_trigger}")
    
    # Create hardware trigger
    hardware_cmd = TriggerModeCommand([2])
    print(f"Hardware trigger: {hardware_cmd.to_string()}")
    print(f"  Is timer-based: {hardware_cmd.is_timer_based}")
    print(f"  Is software: {hardware_cmd.is_software_trigger}")
    print(f"  Is hardware: {hardware_cmd.is_hardware_trigger}")
    
    # Demonstrate mode changing
    print("\n=== Changing Trigger Modes ===")
    cmd = TriggerModeCommand([0])
    print(f"Initial mode: {cmd.mode}")
    
    cmd.mode = 1
    print(f"Changed to software: {cmd.mode}")
    
    cmd.mode = 2
    print(f"Changed to hardware: {cmd.mode}")
    
    # Demonstrate validation
    print("\n=== Validation Example ===")
    try:
        cmd.mode = 3
        print("This should not print")
    except ValueError as e:
        print(f"Caught expected error: {e}")


def demonstrate_profile_integration():
    """Demonstrate trigger mode in radar profiles"""
    print("\n=== Radar Profile Integration ===")
    
    # Create a profile with trigger mode
    profile = RadarProfile("example_profile")
    
    # Add trigger mode command
    trigger_cmd = TriggerModeCommand([0])  # Start with timer-based
    profile.add_command(trigger_cmd)
    
    print(f"Initial trigger mode: {trigger_cmd.mode}")
    
    # Use the helper method to change trigger mode
    profile.set_trigger_mode(1)
    print(f"Changed to software trigger: {trigger_cmd.mode}")
    
    profile.set_trigger_mode(2)
    print(f"Changed to hardware trigger: {trigger_cmd.mode}")
    
    # Parse from string
    print("\n=== Parsing from String ===")
    profile_str = """
    triggerMode 1
    sensorStop
    flushCfg
    """
    
    parsed_profile = RadarProfile.from_string(profile_str)
    trigger_cmd = parsed_profile.get_command('triggerMode')
    if trigger_cmd:
        print(f"Parsed trigger mode: {trigger_cmd.mode}")
        print(f"Command string: {trigger_cmd.to_string()}")
    
    # Convert back to string
    print("\n=== Converting to String ===")
    output_str = parsed_profile.to_string()
    print("Profile as string:")
    print(output_str)


def demonstrate_usage_scenarios():
    """Demonstrate real-world usage scenarios"""
    print("\n=== Usage Scenarios ===")
    
    # Scenario 1: Timer-based operation (default)
    print("Scenario 1: Timer-based operation")
    profile = RadarProfile("timer_profile")
    profile.add_command(TriggerModeCommand([0]))
    print("  - Radar operates on internal timer")
    print("  - Automatic frame generation")
    print("  - Good for continuous monitoring")
    
    # Scenario 2: Software-triggered operation
    print("\nScenario 2: Software-triggered operation")
    profile = RadarProfile("software_profile")
    profile.add_command(TriggerModeCommand([1]))
    print("  - Radar waits for software command")
    print("  - Manual control over frame timing")
    print("  - Good for synchronized applications")
    
    # Scenario 3: Hardware-triggered operation
    print("\nScenario 3: Hardware-triggered operation")
    profile = RadarProfile("hardware_profile")
    profile.add_command(TriggerModeCommand([2]))
    print("  - Radar responds to GPIO 1 signal")
    print("  - External hardware synchronization")
    print("  - Good for multi-sensor systems")


if __name__ == "__main__":
    print("Trigger Mode Functionality Demo")
    print("=" * 40)
    
    demonstrate_trigger_mode_commands()
    demonstrate_profile_integration()
    demonstrate_usage_scenarios()
    
    print("\n" + "=" * 40)
    print("Demo completed successfully!") 