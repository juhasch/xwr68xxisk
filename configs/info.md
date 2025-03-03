# Configuration information

## Commands

### Overview

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
    lvdsStreamCfg: <subFrameIdx> <enableHeader> <dataFmt> <enableSW>
    calibData: <save enable> <restore enable> <Flash offset>
    idlePowerCycle: <enDSPpowerdown> <enDSSclkgate> <enMSSvclkgate> <enBSSclkgate> <enRFpowerdown> <enAPLLpowerdown> <enAPLLGPADCpowerdown> <componentMicroDelay> <idleModeMicroDelay>
    idlePowerDown: <enDSPpowerdown> <enDSSclkgate> <enMSSvclkgate> <enBSSclkgate> <enRFpowerdown> <enAPLLpowerdown> <enAPLLGPADCpowerdown> <componentMicroDelay> <idleModeMicroDelay>
    dfeDataOutputMode: 
    channelCfg: 
    adcCfg: 
    advFrameCfg: 
    subFrameCfg: 
    lowPower:
    contModeCfg: 
    bpmCfgAdvanced: 


### flushCfg


### clutterRemoval

clutterRemoval: <subFrameIdx> <enabled>

    clutterRemoval: -1 0

### profileCfg

profileCfg <> <frequency band> <> <> <> <> <> <> <> <>

    profileCfg 0 77 267 7 57.14 0 0 70 1 256 5209 0 0 30
    profileCfg 0 60 558 7 66.67 0 0 60 1 256 4363 0 0 158


### frameCfg

frameCfg <> <> <> <> <period> <> <>

     frameCfg 0 1 16 0 71.429 1 0


### chirpCfg

### guiMonitor

| Parameter               | Description |
|-------------------------|-------------|
| `detectedObjects`       | Send list of detected objects. <br>• **0**: Don't send anything.<br>• **1**: Send list of detected objects (see `DPIF_PointCloudCartesian`) and side info (`DPIF_PointCloudSideInfo`).<br>• **2**: Send list of detected objects only (no side info). |
| `logMagRange`          | Send log magnitude range array. |
| `noiseProfile`         | Send noise floor profile. |
| `rangeAzimuthHeatMap`  | Send complex range bins at zero Doppler, all antenna symbols for range-azimuth heat map. |
| `rangeDopplerHeatMap`  | Send complex range bins at zero Doppler (all antenna symbols), for range-Doppler heat map. |
| `statsInfo`            | Send statistics. |


    guiMonitor -1 1 1 0 0 0 1


### analogMonitor

analogMonitor: <rxSaturation> <sigImgBand>

    analogMonitor 0 0

### cfarCfg

cfarCfg: <subFrameIdx> <procDirection> <averageMode> <winLen> <guardLen> <noiseDiv> <cyclicMode> <thresholdScale> <peakGroupingEn>

| Parameter | Description |
|-----------|-------------|
| procDirection | 0: range, 1: doppler |
| averageMode   | int |
| winLen         | int|
| guardLen       | int|
| noiseDivShift  | int|
| cyclicMode     | int|
| threshold      | float|
| peakGroupingEn | int|


    cfarCfg -1 0 2 8 4 3 0 15 1
    cfarCfg -1 1 0 4 2 3 1 15 1

### multiObjBeamForming

multiObjBeamForming: <subFrameIdx> <enabled> <threshold>


| Parameter | Description |
|-----------|-------------|
| enabled   | |
| threshold | |

    multiObjBeamForming -1 1 0.5


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

