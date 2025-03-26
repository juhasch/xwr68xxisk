"""Default radar configuration for XWR68XX hardware."""
from .radar_config import RadarConfig


DEFAULT_FRAME_PERIOD = 100

xwr68xx_str = f"""
sensorStop
flushCfg
dfeDataOutputMode 1
channelCfg 15 5 0
adcCfg 2 1
adcbufCfg -1 0 1 1 1
profileCfg 0 60 567 7 57.14 0 0 70 1 256 5209 0 0 158
chirpCfg 0 0 0 0 0 0 0 1
chirpCfg 1 1 0 0 0 0 0 4
frameCfg 0 1 16 0 {DEFAULT_FRAME_PERIOD} 1 0
lowPower 0 0
guiMonitor -1 1 0 0 0 0 1
cfarCfg -1 0 2 8 4 3 0 10 1
cfarCfg -1 1 0 4 2 3 1 10 1
multiObjBeamForming -1 1 0.9
clutterRemoval -1 0
calibDcRangeSig -1 0 -5 8 256
extendedMaxVelocity -1 0
bpmCfg -1 0 0 1
lvdsStreamCfg -1 0 0 0
compRangeBiasAndRxChanPhase 0.0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0 1 0
measureRangeBiasAndRxChanPhase 0 1.5 0.2
CQRxSatMonitor 0 3 5 121 0
CQSigImgMonitor 0 127 4
analogMonitor 0 0
aoaFovCfg -1 -90 90 -90 90
cfarFovCfg -1 0 0 8.92
cfarFovCfg -1 1 -1 1.00
calibData 0 0 0
"""

    
def get_xwr68xx_config() -> 'RadarConfig':
    return RadarConfig.from_string(xwr68xx_str, "xwr68xx")
