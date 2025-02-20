# Configuration information

## Commands

### Overview

    guiMonitor: <subFrameIdx> <detectedObjects> <logMagRange> <noiseProfile> <rangeAzimuthHeatMap> <rangeDopplerHeatMap> <statsInfo>
    cfarCfg: <subFrameIdx> <procDirection> <averageMode> <winLen> <guardLen> <noiseDiv> <cyclicMode> <thresholdScale> <peakGroupingEn>
    multiObjBeamForming: <subFrameIdx> <enabled> <threshold>
    calibDcRangeSig: <subFrameIdx> <enabled> <negativeBinIdx> <positiveBinIdx> <numAvgFrames>
    clutterRemoval: <subFrameIdx> <enabled>
    adcbufCfg: <subFrameIdx> <adcOutputFmt> <SampleSwap> <ChanInterleave> <ChirpThreshold>
    compRangeBiasAndRxChanPhase: <rangeBias> <Re00> <Im00> <Re01> <Im01> <Re02> <Im02> <Re03> <Im03> <Re10> <Im10> <Re11> <Im11> <Re12> <Im12> <Re13> <Im13>
    measureRangeBiasAndRxChanPhase: <enabled> <targetDistance> <searchWin>
    aoaFovCfg: <subFrameIdx> <minAzimuthDeg> <maxAzimuthDeg> <minElevationDeg> <maxElevationDeg>
    cfarFovCfg: <subFrameIdx> <procDirection> <min (meters or m/s)> <max (meters or m/s)>
    extendedMaxVelocity: <subFrameIdx> <enabled>
    bpmCfg: <subFrameIdx> <enabled> <chirp0Idx> <chirp1Idx>
    CQRxSatMonitor: <profile> <satMonSel> <priSliceDuration> <numSlices> <rxChanMask>
    CQSigImgMonitor: <profile> <numSlices> <numSamplePerSlice>
    analogMonitor: <rxSaturation> <sigImgBand>
    lvdsStreamCfg: <subFrameIdx> <enableHeader> <dataFmt> <enableSW>
    configDataPort: <baudrate> <ackPing>
    calibData: <save enable> <restore enable> <Flash offset>
    idlePowerCycle: <enDSPpowerdown> <enDSSclkgate> <enMSSvclkgate> <enBSSclkgate> <enRFpowerdown> <enAPLLpowerdown> <enAPLLGPADCpowerdown> <componentMicroDelay> <idleModeMicroDelay>
    idlePowerDown: <enDSPpowerdown> <enDSSclkgate> <enMSSvclkgate> <enBSSclkgate> <enRFpowerdown> <enAPLLpowerdown> <enAPLLGPADCpowerdown> <componentMicroDelay> <idleModeMicroDelay>
    version: 
    flushCfg: 
    dfeDataOutputMode: 
    channelCfg: 
    adcCfg: 
    profileCfg: 
    chirpCfg: 
    frameCfg: 
    advFrameCfg: 
    subFrameCfg: 
    lowPower:
    contModeCfg: 
    bpmCfgAdvanced: 


### Version

```
version
```

Gives the following information:
    Platform                : xWR68xx
    mmWave SDK Version      : 03.06.02.00
    Device Info             : AWR68XX ASIL-B non-secure ES 02.00
    RF F/W Version          : 06.03.02.06.20.08.11
    RF F/W Patch            : 00.00.00.00.00.00.00
    mmWaveLink Version      : 01.02.06.06
    Lot number              : 4134287
    Wafer number            : 11
    Die coordinates in wafer: X = 18, Y = 28

### Query Demo Status

```
queryDemoStatus
```

Gives the following information:

    Sensor State: 3
    Data port baud rate: 1036800

### Sensor stop

Stop the sensor and clear the configuration.

```
sensorStop: No arguments
```


### Sensor start

Start the sensor and configure the sensor with the previously set configuration.

```
sensorStart: [doReconfig(optional, default:enabled)]
```

### Config Data Port

Set the data port baudrate and ackPing. The ackPing is used to check if the data port is set correctly and sends 16 bytes of 0xff to the data port.

```
configDataPort: <baudrate> <ackPing>
```

