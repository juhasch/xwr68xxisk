#!/usr/bin/env python3
"""
Unit tests for radar_config.py
"""

import unittest
import os
import tempfile
from radar_config import (
    RadarCommand, RadarConfig, 
    DfeDataOutputModeCommand, ChannelConfigCommand, ProfileConfigCommand
)


class TestRadarCommand(unittest.TestCase):
    """Tests for the RadarCommand class and its subclasses"""
    
    def test_basic_command(self):
        """Test basic RadarCommand creation and string conversion"""
        cmd = RadarCommand("testCmd", [1, 2, 3])
        self.assertEqual(cmd.name, "testCmd")
        self.assertEqual(cmd.params, [1, 2, 3])
        self.assertEqual(cmd.to_string(), "testCmd 1 2 3")
    
    def test_from_string(self):
        """Test creating a command from a string"""
        cmd = RadarCommand.from_string("sensorStop")
        self.assertEqual(cmd.name, "sensorStop")
        self.assertEqual(cmd.params, [])
        
        cmd = RadarCommand.from_string("profileCfg 0 77 100 6 60 0 0 80 1 512 6000 0 0 160")
        self.assertEqual(cmd.name, "profileCfg")
        self.assertEqual(len(cmd.params), 14)
        self.assertEqual(cmd.params[1], 77)  # As integer
        self.assertEqual(cmd.params[7], 80)  # As integer
    
    def test_dfe_data_output_mode_command(self):
        """Test DfeDataOutputModeCommand methods"""
        cmd = DfeDataOutputModeCommand([1])
        self.assertEqual(cmd.mode_type, 1)
        cmd.mode_type = 3
        self.assertEqual(cmd.mode_type, 3)
        with self.assertRaises(ValueError):
            cmd.mode_type = 4  # Invalid value
    
    def test_channel_config_command(self):
        """Test ChannelConfigCommand methods"""
        cmd = ChannelConfigCommand([15, 5, 0])
        self.assertEqual(cmd.rx_channel_en, 15)
        self.assertEqual(cmd.tx_channel_en, 5)
        self.assertEqual(cmd.cascading, 0)
        
        cmd.rx_channel_en = 7
        cmd.tx_channel_en = 3
        self.assertEqual(cmd.rx_channel_en, 7)
        self.assertEqual(cmd.tx_channel_en, 3)
    
    def test_profile_config_command(self):
        """Test ProfileConfigCommand methods"""
        params = [0, 77, 100, 6, 60, 0, 0, 80, 1, 512, 6000, 0, 0, 160]
        cmd = ProfileConfigCommand(params)
        
        self.assertEqual(cmd.profile_id, 0)
        self.assertEqual(cmd.start_freq, 77)
        self.assertEqual(cmd.idle_time, 100)
        self.assertEqual(cmd.freq_slope_const, 80)
        self.assertEqual(cmd.num_adc_samples, 512)
        
        # Test setter methods
        cmd.start_freq = 78.5
        cmd.idle_time = 120
        cmd.freq_slope_const = 85
        
        self.assertEqual(cmd.start_freq, 78.5)
        self.assertEqual(cmd.idle_time, 120)
        self.assertEqual(cmd.freq_slope_const, 85)
        
        # Test validation
        with self.assertRaises(ValueError):
            cmd.freq_slope_const = 0  # Should be > 0


class TestRadarConfig(unittest.TestCase):
    """Tests for the RadarConfig class"""
    
    def test_from_string(self):
        """Test creating a config from a multiline string"""
        config_str = """
        sensorStop
        flushCfg
        dfeDataOutputMode 1
        channelCfg 15 5 0
        profileCfg 0 77 100 6 60 0 0 80 1 512 6000 0 0 160
        """
        
        config = RadarConfig.from_string(config_str, "test_config")
        self.assertEqual(config.name, "test_config")
        self.assertEqual(len(config.commands), 5)
        self.assertEqual(config.commands[0].name, "sensorStop")
        self.assertEqual(config.commands[2].name, "dfeDataOutputMode")
    
    def test_to_string(self):
        """Test converting a config to a string"""
        config = RadarConfig("test")
        config.add_command(RadarCommand("cmd1", [1, 2]))
        config.add_command(RadarCommand("cmd2", [3, 4.5]))
        
        expected = "cmd1 1 2\ncmd2 3 4.5"
        self.assertEqual(config.to_string(), expected)
    
    def test_file_io(self):
        """Test saving and loading from file"""
        config = RadarConfig("test_file_io")
        config.add_command(RadarCommand("sensorStop", []))
        config.add_command(RadarCommand("dfeDataOutputMode", [1]))
        config.add_command(RadarCommand("channelCfg", [15, 5, 0]))
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.cfg', delete=False) as tmp:
            temp_path = tmp.name
        
        try:
            # Test saving
            config.to_file(temp_path)
            self.assertTrue(os.path.exists(temp_path))
            
            # Test loading
            loaded_config = RadarConfig.from_file(temp_path, "test_file_io")
            self.assertEqual(loaded_config.name, "test_file_io")
            self.assertEqual(len(loaded_config.commands), 3)
            self.assertEqual(loaded_config.commands[0].name, "sensorStop")
            self.assertEqual(loaded_config.commands[1].name, "dfeDataOutputMode")
            self.assertEqual(loaded_config.commands[2].name, "channelCfg")
            self.assertEqual(loaded_config.commands[2].params, [15, 5, 0])
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    def test_get_command(self):
        """Test retrieving commands by name"""
        config = RadarConfig()
        config.add_command(RadarCommand("cmd1", [1]))
        config.add_command(RadarCommand("cmd2", [2]))
        config.add_command(RadarCommand("cmd1", [3]))  # Second cmd1
        
        cmd = config.get_command("cmd1")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.params[0], 1)
        
        cmd = config.get_command("cmd1", 1)  # Get the second one
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.params[0], 3)
        
        cmd = config.get_command("nonexistent")
        self.assertIsNone(cmd)
    
    def test_get_commands(self):
        """Test getting multiple commands with the same name"""
        config = RadarConfig()
        config.add_command(RadarCommand("chirpCfg", [0, 0, 0, 0, 0, 0, 0, 1]))
        config.add_command(RadarCommand("chirpCfg", [1, 1, 0, 0, 0, 0, 0, 2]))
        
        cmds = config.get_commands("chirpCfg")
        self.assertEqual(len(cmds), 2)
        self.assertEqual(cmds[0].params[0], 0)
        self.assertEqual(cmds[1].params[0], 1)
    
    def test_remove_command(self):
        """Test removing a command"""
        config = RadarConfig()
        config.add_command(RadarCommand("cmd1", [1]))
        config.add_command(RadarCommand("cmd2", [2]))
        config.add_command(RadarCommand("cmd1", [3]))
        
        # Remove first cmd1
        result = config.remove_command("cmd1")
        self.assertTrue(result)
        self.assertEqual(len(config.commands), 2)
        
        # Check remaining cmd1
        cmd1 = config.get_command("cmd1")
        self.assertEqual(cmd1.params[0], 3)
        
        # Try to remove nonexistent command
        result = config.remove_command("nonexistent")
        self.assertFalse(result)
    
    def test_clone(self):
        """Test cloning a configuration"""
        config = RadarConfig("original")
        config.add_command(RadarCommand("cmd1", [1, 2]))
        config.add_command(RadarCommand("cmd2", [3, 4]))
        
        clone = config.clone()
        self.assertEqual(clone.name, "original")
        self.assertEqual(len(clone.commands), 2)
        
        # Modify clone, shouldn't affect original
        clone.name = "clone"
        clone.commands[0].params[0] = 99
        
        self.assertEqual(config.name, "original")
        self.assertEqual(config.commands[0].params[0], 1)
        self.assertEqual(clone.commands[0].params[0], 99)
    
    def test_helper_methods(self):
        """Test the helper methods for common configuration changes"""
        config = RadarConfig()
        
        # Add frameCfg
        config.add_command(RadarCommand("frameCfg", [0, 1, 16, 0, 100, 1, 0]))
        
        # Test update_frame_period
        result = config.update_frame_period(200)
        self.assertTrue(result)
        self.assertEqual(config.get_command("frameCfg").params[4], 200)
        
        # Add channelCfg
        config.add_command(RadarCommand("channelCfg", [15, 5, 0]))
        
        # Test set_tx_antennas
        result = config.set_tx_antennas(3)
        self.assertTrue(result)
        self.assertEqual(config.get_command("channelCfg").params[1], 3)
        
        # Test set_rx_antennas
        result = config.set_rx_antennas(7)
        self.assertTrue(result)
        self.assertEqual(config.get_command("channelCfg").params[0], 7)
        
        # Add profileCfg
        config.add_command(RadarCommand("profileCfg", [0, 77, 100, 6, 60, 0, 0, 80, 1, 512, 6000, 0, 0, 160]))
        
        # Test set_profile_parameters
        result = config.set_profile_parameters(
            start_freq=79,
            idle_time=120,
            freq_slope=85,
            adc_samples=256,
            rx_gain=150
        )
        self.assertTrue(result)
        profile = config.get_command("profileCfg")
        self.assertEqual(profile.params[1], 79)
        self.assertEqual(profile.params[2], 120)
        self.assertEqual(profile.params[7], 85)
        self.assertEqual(profile.params[9], 256)
        self.assertEqual(profile.params[13], 150)
        
        # Add clutterRemoval
        config.add_command(RadarCommand("clutterRemoval", [-1, 0]))
        
        # Test set_clutter_removal
        result = config.set_clutter_removal(True)
        self.assertTrue(result)
        self.assertEqual(config.get_command("clutterRemoval").params[1], 1)
        
        # Test with nonexistent commands
        config_empty = RadarConfig()
        self.assertFalse(config_empty.update_frame_period(100))
        self.assertFalse(config_empty.set_tx_antennas(1))
        self.assertFalse(config_empty.set_rx_antennas(1))
        self.assertFalse(config_empty.set_profile_parameters(start_freq=77))
        self.assertFalse(config_empty.set_clutter_removal(True))


if __name__ == "__main__":
    unittest.main() 