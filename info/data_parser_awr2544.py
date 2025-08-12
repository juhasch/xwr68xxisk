# ****************************************************************************
# * (C) Copyright 2023, Texas Instruments Incorporated. - www.ti.com
# ****************************************************************************
# *
# *  Redistribution and use in source and binary forms, with or without
# *  modification, are permitted provided that the following conditions are
# *  met:
# *
# *    Redistributions of source code must retain the above copyright notice,
# *    this list of conditions and the following disclaimer.
# *
# *    Redistributions in binary form must reproduce the above copyright
# *    notice, this list of conditions and the following disclaimer in the
# *     documentation and/or other materials provided with the distribution.
# *
# *    Neither the name of Texas Instruments Incorporated nor the names of its
# *    contributors may be used to endorse or promote products derived from
# *    this software without specific prior written permission.
# *
# *  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# *  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# *  PARTICULAR TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# *  A PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT  OWNER OR
# *  CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# *  EXEMPLARY, ORCONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# *  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# *  PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# *  LIABILITY, WHETHER IN CONTRACT,  STRICT LIABILITY, OR TORT (INCLUDING
# *  NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# *  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# *
# ****************************************************************************
# Sample mmW demo Enet output parser script - should be invoked using python3
# Ex: python3 data_parser_awr2544.py <recorded_pcap_file>.pcap <config_file>.cfg
# Following optional arguments are supported:
#  --dcmpFrame: To decompress the entire frame instead of only first chirp
#  --checkCRC: Compute and check the CRC of each packet
#  --verifyCheckSum: Compute and check the UDP checksum of each packet
#  --deleteCapFile: Remove the Captured File, helpful for infinite frame testing
#
# By default, data_parser_awr2544 does the following tasks:
#   1. Checks if the packets are sequential. That is, no packet is dropped while
#      receiving the Enet data.
#   2. Decompresses the first chirp of each frame and plots the range profile of each
#      receiver for chirp 0.
#
# Note:
#   Following python packages needs to be installed to run this script:
#       math, binascii, dpkt, numpy, matplotlib, ctypes
#
# ****************************************************************************

import os
import math
import binascii
import dpkt
import numpy as np
import time
import matplotlib
#matplotlib.use('Agg')  # Use Agg backend instead of Qt
import matplotlib.pyplot as plt
from ctypes import *
from ctypes import CDLL
import ctypes
import argparse
import warnings
warnings.filterwarnings('ignore')

if (os.name=='nt'):
    lib=CDLL("./hwam_lib.dll")
elif(os.name=='posix'):
    lib=CDLL("./hwam_lib.so")

PASS = 0
FAIL = -1
seqNum = -1
badFrameNum = -1
compChirpList = []
fileNum=0
file=''
checkFileTimes = 0
checkFileSizeTimes = 0
MMW_DEMO_MAX_PAYLOAD_SIZE = 1536


class dcmpCfg(Structure):
    _fields_ = [("compMethod", ctypes.c_uint8),
                ("numRx", ctypes.c_uint8),
                ("rangeBinsPerBlock", ctypes.c_uint16),
                ("numRangeBinsPerChirp", ctypes.c_uint16),
                ("numChirpsPerFrame", ctypes.c_uint16),
                ("compRatio", ctypes.c_float)]


def nextPowerOf2(N):
    # if N is a power of two simply return it
    if not (N & (N - 1)):
        return N
    # else set only the left bit of most significant bit
    return  int("1" + (len(bin(N)) - 2) * "0", 2)


def parseConfigs(cfgFile):
    cfgFileId = open(cfgFile,'r')
    configs = cfgFileId.read()
    cfgFileId.close()
    configParams = {}
    for line in configs.split('\n'):
        cfg = line.split(" ")
        cmd = cfg[0]
        args = cfg[1::]
        if cmd == 'channelCfg':
            configParams['rxAnt'] = bin(int(args[0])).count("1")
            configParams['txAnt'] = bin(int(args[1])).count("1")

        elif cmd == 'profileCfg':
            configParams['samples'] = int(args[-5])
            configParams['sampleRate'] = int(args[-4])
            configParams['slope'] = float(args[7])

        elif cmd == 'frameCfg':
            configParams['chirpsPerFrame'] = (int(args[1]) - int(args[0]) + 1) * int(args[2])

        elif cmd =='compressionCfg':
            configParams['compMethod'] = int(args[2])
            configParams['compRatio'] = float(args[3])
            configParams['rangeBinsPerBlock'] = int(args[4])

        elif cmd == 'procChainCfg':
            configParams['procChain'] = int(args[0])
            configParams['crcType'] = int(args[4])

        else:
            continue

    rangeBins2x = nextPowerOf2(configParams['samples'])
    if configParams['procChain'] == 0:
        configParams['rangeBins'] = int(rangeBins2x/2)
    else:
        rangeBins3x = 3*nextPowerOf2(int(configParams['samples']/3))
        configParams['rangeBins'] = int(rangeBins3x/2) if(rangeBins2x > rangeBins3x) else int(rangeBins2x/2)

    # range resolution
    configParams['rangeStep'] = (3e8 *configParams['sampleRate'] *1e3 )/ (2 *configParams['slope'] *1e12 *configParams['rangeBins'] *2)
    configParams['maxRange'] = configParams['rangeStep'] * configParams['rangeBins']

    if configParams['compMethod'] == 1:
        samplesPerBlock = configParams['rangeBinsPerBlock']
    else:
        samplesPerBlock = configParams['rxAnt'] * configParams['rangeBinsPerBlock']
    inputBytesPerBlock = 4 * samplesPerBlock
    # 32-bit boundary aligned
    outputBytesPerBlock = math.ceil((inputBytesPerBlock * configParams['compRatio']) / 4) * 4

    configParams['achievedDcmpratio'] = outputBytesPerBlock/inputBytesPerBlock

    # number of compressed blocks per chirp
    numBlocksPerChirp = configParams['rangeBins'] * configParams['rxAnt'] / samplesPerBlock
    # max data present in transmit buffer other than header and footer
    maxPayloadSize = MMW_DEMO_MAX_PAYLOAD_SIZE - (16 + 8) # max - (header+ footer)
    numBlocksPerPayload = int(maxPayloadSize / outputBytesPerBlock)

    # total number of payload in one chirp data */
    configParams['pktsPerChirp'] = math.ceil(numBlocksPerChirp / numBlocksPerPayload)

    configParams['pktsPerFrame'] = configParams['pktsPerChirp'] * configParams['chirpsPerFrame']

    configParams['pktLen'] = int((outputBytesPerBlock * numBlocksPerChirp) / configParams['pktsPerChirp'])

    print(configParams)
    return configParams


def getUint32(data):
    """!
       This function coverts 4 bytes to a 32-bit unsigned integer.

        @param data : 1-demension byte array
        @return     : 32-bit unsigned integer
    """
    return (data[0] +
            data[1]*256 +
            data[2]*65536 +
            data[3]*16777216)

def getUint16(data):
    """!
       This function coverts 2 bytes to a 16-bit unsigned integer.

        @param data : 1-demension byte array
        @return     : 16-bit unsigned integer
    """
    return (data[0] +
            data[1]*256)


def checkMagicPattern(data):
    """!
       This function check if data arrary contains the magic pattern which is the start of one mmw demo output packet.

        @param data : 1-demension byte array
        @return     : 1 if magic pattern is found
                      0 if magic pattern is not found
    """
    found = 0
    header = binascii.hexlify(data[::-1])
    if(header == b'01234567'):
        found = 1
    return (found)


def check32bitCRC(data, pktLength):
    crc32 = -1
    crc32_p = -306674912 #crc32 reverse poly

    for i in range(pktLength + 16 + 8):
        byte = int(data[i])
        crc32 = crc32 ^ byte

        for j in range(8):
            a = (crc32 >> 1) & int(0x7fffffff)
            b = crc32_p & (-1*(crc32 & 1))
            crc32 = a ^ b
    ans32 = (~(crc32))
    if (ans32<0):
        ans32 = ans32 + int(0xffffffff) + 1
    ans32 = hex(ans32)
    obt = hex(getUint32(data[pktLength+16+8:pktLength+16+8+4]))
    if(ans32 == obt):
        return PASS
    else:
        return FAIL


def check16bitCRC(data, pktLength):
    crc16 = -1
    crc16_p = 4129 #crc16 reverse poly

    for i in range(pktLength + 16 + 8):
        byte = int(data[i])
        crc16 = crc16 ^ (byte<<8)

        for j in range(8):
            if (crc16 & 0x8000 == 0x8000):
                crc16 = (crc16<<1) ^ crc16_p
            else:
                crc16 = crc16 << 1

    ans16 = hex(crc16 & 0xffff)
    obt = hex(getUint16(data[pktLength+16+8:pktLength+16+8+2]))

    if(ans16 == obt):
        return PASS
    else:
        return FAIL


def verifyUDPCheckSum(input):
    sum = 0xd386 #initial psuedo hdr chksum
    for i in range(1, 6, 2):
        data = int(input[i-1]) + 256*(input[i])
        sum = sum + int(data)
        if (sum > int(0xffff)):
            sum = (sum & int(0xffff)) + (sum >> 16)

    chkSumObt = int(input[6]) + 256*(input[7])

    for i in range(9, len(input), 2):
        data = int(input[i-1]) + 256*(input[i])
        sum = sum + int(data)
        if (sum > int(0xffff)):
            sum = (sum & int(0xffff)) + (sum >> 16)
    sum = (~sum & int(0xffff))

    if(chkSumObt == sum):
        return PASS
    else:
        return FAIL


def decompression(dcmpFrame, configParams):
    global compChirpList

    compChirp = (ctypes.c_uint32 * len(compChirpList))(*compChirpList)
    lenDcmpChirpList = configParams['rangeBins'] * configParams['rxAnt'] * 2
    if dcmpFrame:
        lenDcmpChirpList = lenDcmpChirpList * configParams['chirpsPerFrame']
    dcmpChirp = (ctypes.c_int16 * lenDcmpChirpList)()

    if dcmpFrame:
        cfg = dcmpCfg(configParams['compMethod'], configParams['rxAnt'], configParams['rangeBinsPerBlock'], \
                      configParams['rangeBins'], configParams['chirpsPerFrame'], configParams['compRatio'])
    else:
        cfg = dcmpCfg(configParams['compMethod'], configParams['rxAnt'], configParams['rangeBinsPerBlock'], configParams['rangeBins'], 1, configParams['compRatio'])

    lib.hwam_example1.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_int16), ctypes.POINTER(dcmpCfg)]
    lib.hwam_example1.restype = ctypes.c_int

    retVal = lib.hwam_example1(compChirp, dcmpChirp, cfg)

    dcmpChirp = np.array(list(dcmpChirp))
    dcmpChirpCmplx = []
    dcmpChirpCmplx = dcmpChirp[1::2] + dcmpChirp[0::2]*1j
    dcmpChirpCmplx = np.array(dcmpChirpCmplx)

    if dcmpFrame:
        if(configParams['compMethod']):
            dcmpChirpCmplx = np.reshape(dcmpChirpCmplx, (configParams['numChirpsPerFrame'], configParams['rxAnt'], -1))
            dcmpChirpCmplx = np.transpose(dcmpChirpCmplx, (0, 2, 1))
        else:
            dcmpChirpCmplx = np.reshape(dcmpChirpCmplx, (-1, configParams['rangeBins'], configParams['rxAnt']))

        dcmpChirpCmplx = dcmpChirpCmplx[0,:,:]

    else:
        if(configParams['compMethod']):
            dcmpChirpCmplx = np.reshape(dcmpChirpCmplx, (configParams['rxAnt'], -1))
            dcmpChirpCmplx = np.transpose(dcmpChirpCmplx)
        else:
            dcmpChirpCmplx = np.reshape(dcmpChirpCmplx, (-1, configParams['rxAnt']))

    line1.set_ydata(20*np.log10(np.abs(dcmpChirpCmplx[:,0])))
    line2.set_ydata(20*np.log10(np.abs(dcmpChirpCmplx[:,1])))
    line3.set_ydata(20*np.log10(np.abs(dcmpChirpCmplx[:,2])))
    line4.set_ydata(20*np.log10(np.abs(dcmpChirpCmplx[:,3])))

    # drawing updated values
    figure.canvas.draw()
    figure.canvas.flush_events()


def parse_one_packet(data, args, pktLength, badFrameNum):
    global compChirpList

    #check magic number
    headerStartIndex = -1
    result = PASS
    crcResult = PASS
    checkSumResult = PASS


    # find the location of magic number in the packet
    for idx in range(len(data)):
        if checkMagicPattern(data[idx:idx+4:1]) == 1:
            headerStartIndex = idx
            print(data[headerStartIndex:headerStartIndex+4:1])
            print(headerStartIndex)
            exit()
            break

    # magic number found?
    if headerStartIndex == -1:  # does not find the magic number i.e output packet header
        frameNumber = -1
        chirpNumber = -1
        sequenceNumber = -1
        crcResult = FAIL
        result = FAIL

    else:
        sequenceNumber = getUint32(data[headerStartIndex+4:headerStartIndex+8:1])
        print(data[headerStartIndex+4:headerStartIndex+8:1])
        frameNumber = getUint32(data[headerStartIndex+8:headerStartIndex+12:1])
        chirpNumber = getUint32(data[headerStartIndex+12:headerStartIndex+16:1])

        if args.checkCRC:
            if configParams['crcType']:
                crcResult = check32bitCRC(data[headerStartIndex::], pktLength)
            else:
                crcResult = check16bitCRC(data[headerStartIndex::], pktLength)

        if args.verifyCheckSum:
            checkSumResult = verifyUDPCheckSum(data[headerStartIndex-10::])

        if frameNumber != badFrameNum:
            if args.dcmpFrame == 0:
                if chirpNumber == 0:
                    for i in range(int(pktLength/4)):
                        compChirpList.append(getUint32(data[(i*4 + headerStartIndex+16):((i+1 + headerStartIndex+16)*4):1]))

            else:
                for i in range(int(pktLength/4)):
                        compChirpList.append(getUint32(data[(i*4 + headerStartIndex+16):((i+1 + headerStartIndex+16)*4):1]))
    return(result, frameNumber, chirpNumber, sequenceNumber, crcResult, checkSumResult)


def processData(capturedFileName, args, configParams):
    global seqNum
    global badFrameNum
    global compChirpList

    print('Parsing File: ',capturedFileName)
    with open((capturedFileName), 'rb') as f:
        pcap = dpkt.pcap.Reader(f)
        packetsBuf = pcap.readpkts()

        for pkt in range(len(packetsBuf)):
            oldseqnum = seqNum
            (result, frameNum, chirpNum, seqNum, crcResult, checkSumResult) \
                    = parse_one_packet(packetsBuf[pkt][1], args, configParams['pktLen'], badFrameNum)
            print(result, frameNum, chirpNum, seqNum, crcResult, checkSumResult)

            if(result == PASS):
                if(seqNum != oldseqnum+1):
                    print("Pkt drop: FrameNum ", frameNum, " SeqNum ", seqNum, " Old SeqNum ", oldseqnum)
                    # bad frame, drop this entire frame and don't plot it
                    badFrameNum = frameNum
                    # re-initialize the compressed radar cube
                    compChirpList = []

                if(crcResult ==  FAIL):
                    print("CRCFAIL: Chirp ", chirpNum)
                if(checkSumResult ==  FAIL):
                    print("UDP CheckSum Fail: Chirp ", chirpNum)

                # decompress the frame if all the chirps of a frame are available
                if ((frameNum!=badFrameNum) and  (((seqNum+1) % configParams['pktsPerFrame']) == 0)):
                    decompression(args.dcmpFrame, configParams)
                    # re-initialize the compressed radar cube
                    compChirpList = []

    if args.deleteCapFile:
        # delete the last parsed file
        os.remove(capturedFileName)



if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Parse the Enet Captured Data")
    parser.add_argument("capturedFileName", help="path of data file to be parsed", type=str)
    parser.add_argument("configFileName", help='Path of config (.cfg) file', type=str)
    parser.add_argument("--dcmpFrame", help="decompress entire frame", action="store_true")
    parser.add_argument("--checkCRC", help="check CRC of each packet", action="store_true")
    parser.add_argument("--verifyCheckSum", help="verify UDP checksum of each packet", action="store_true")
    parser.add_argument("--deleteCapFile", help="delete captured data", action="store_true")
    args = parser.parse_args()

    # parse the cfg file
    configParams = parseConfigs(args.configFileName)
    rangeAxis = np.linspace(0,configParams['maxRange'], configParams['rangeBins'])
    plt.ion()
    figure = plt.figure(figsize=(15, 10))
    figure.suptitle('Range Plot for Chirp 0 (dB)')

    ax1 = figure.add_subplot(221)
    ax1.set_xlim(0, configParams['maxRange'])
    ax1.set_ylim((0, 100))
    ax1.set_xlabel('Range (m)')
    ax1.set_title('RX 1')
    line1, = ax1.plot([],[])
    line1.set_xdata(rangeAxis)

    ax2 = figure.add_subplot(222)
    ax2.set_xlim(0, configParams['maxRange'])
    ax2.set_ylim((0, 100))
    ax2.set_xlabel('Range (m)')
    ax2.set_title('RX 2')
    line2, = ax2.plot([],[])
    line2.set_xdata(rangeAxis)

    ax3 = figure.add_subplot(223)
    ax3.set_xlim(0, configParams['maxRange'])
    ax3.set_ylim((0, 100))
    ax3.set_xlabel('Range (m)')
    ax3.set_title('RX 3')
    line3, = ax3.plot([],[])
    line3.set_xdata(rangeAxis)

    ax4 = figure.add_subplot(224)
    ax4.set_xlim(0, configParams['maxRange'])
    ax4.set_ylim((0, 100))
    ax4.set_xlabel('Range (m)')
    ax4.set_title('RX 4')
    line4, = ax4.plot([],[])
    line4.set_xdata(rangeAxis)

    while(1):
        # open the file if it exists
        if(os.path.exists(args.capturedFileName+file)):
            checkFileTimes = 0
            # check if the entire file size is available
            if(os.path.getsize(args.capturedFileName+file)>=1300000304):
                checkFileSizeTimes = 0
                processData(args.capturedFileName+file, args, configParams)
                fileNum = fileNum + 1
                file = str(fileNum)

            # wait for the entire file to be available
            else:
                checkFileSizeTimes = checkFileSizeTimes + 1
                # check for 3 times if the entire data is available
                if(checkFileSizeTimes < 3):
                    time.sleep(2)
                # else consider this to be last file and exit
                else:
                    processData(args.capturedFileName+file, args, configParams)
                    print("Last File Processed, Exiting..")
                    #exit()

        # if the file does not exist, sleep for sometime
        else:
            checkFileTimes = checkFileTimes + 1
            if(checkFileTimes < 5):
                time.sleep(10)
            else:
                print("Error: '",args.capturedFileName+file,"' File Not Found")
                exit()

    print("Parsing Done.")