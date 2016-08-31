#!/usr/bin/env python
"""
 Insteon Device Classes
 provides device classes for Insteon dimmers and thermostats, along
 with necessary functions that enable communication from the host
 through a power line modem (PLM) to the device instances.

 Classes:
    dimmer: Insteon device class for dimmers
    thermostat: Insteon device class for dimmers

 Functions:
    CalcCrcStr: calculates the Insteon extended command two byte CRC
    ExtCrc: sends an Insteon extended CRC command and gets the response
    ExtChecksum: sends an Insteon extended CS command and gets the response
    StdCmd: sends an Insteon standard command and gets the response
    betterErrorChecking:  reports errors/recovery only when things change

 History:
    December 2014 - first version
    January 2015 - added extended command functions and thermostat class
    August 2016 - general cleanup and comment additions for first release
 """

import time, datetime
#consider updating this to the form:
#from time import sleep
#from datetime.datetime import now

__author__ = "David Boertjes"
__license__ = "unlicense"
__version__ = "1.0.1"
__maintainer__ = "David Boertjes"
__email__ = "david.boertjes@gmail.com"
__status__ = "Production"

def errorReporting(address, errorText, localError, errorStatus, verbose):
    if localError:
        if (errorStatus == False) and verbose:
            print "ERROR: Readback length fail"
            print "   ", datetime.datetime.now()
            print "    set address ", \
                  hex(address[0])[2:] + "." + \
                  hex(address[1])[2:] + "." + \
                  hex(address[2])[2:] + " on " + errorText
        return True
    else:
        if (errorStatus == True) and verbose:
            print "INFO: Readback recovery"
            print "   ", datetime.datetime.now()
            print "    set address ", \
                  hex(address[0])[2:] + "." + \
                  hex(address[1])[2:] + "." + \
                  hex(address[2])[2:] + " on " + errorText
        return False

def CalcCrcStr(dataStr):
    # calculates the Insteon extended command two byte CRC
    # dataStr should contain the cmd1 through data12
    #
    # details on this calculation and when these commands are used
    # can be found in the following document: 
    # http://cache.insteon.com/developer/2441ZTHdev-112012-en.pdf
    crcVal = 0
    for iChar in range(len(dataStr)):
        byte = ord(dataStr[iChar])
        for iByte in range(8):
            fb = byte & 1
            fb = fb ^ 1 if (crcVal & 0x8000) else fb
            fb = fb ^ 1 if (crcVal & 0x4000) else fb
            fb = fb ^ 1 if (crcVal & 0x1000) else fb
            fb = fb ^ 1 if (crcVal & 0x0008) else fb
            crcVal = (crcVal << 1) | fb
            byte = byte >> 1
    crcBytes = [crcVal >> i &0xff for i in (8, 0)]
    crcStr = chr(crcBytes[0]) + chr(crcBytes[1])
    return crcStr

def ExtCrc(ser, cmdStr, verbose = False, extreadback = True):
    # sends an Insteon extended CRC command and gets the response
    # response string and error boolean returned in list
    # ser: serial port handle of the PLM
    # cmdStr: should contain full command to send from 0x02 through data12 = 20 characters
    #   this string has the following format:
    #   1st byte (all commands start with this value):  0x02 --> ASCII start of text
    #   2nd byte (code): 0x62 --> Send INSTEON Standard or Extended Message
    #   3rd byte (destination address high byte)
    #   4th byte (destination address middle byte)
    #   5th byte (destination address low byte)
    #   6th byte (flags):  0x1F --> first nibble = 0 for std 1 for ext
    #                               second nibble = 0bnnmm where nn = hops left, mm = max hops
    #   INSTEON Extended message (20 bytes, excludes From Address): 
    #       7th byte:  Command 1
    #       8th byte:  Command 2
    #       9th byte:  Data 1
    #       10th byte: Data 2
    #       11th byte: Data 3
    #       12th byte: Data 4
    #       13th byte: Data 5
    #       14th byte: Data 6
    #       15th byte: Data 7
    #       16th byte: Data 8
    #       17th byte: Data 9
    #       18th byte: Data 10
    #       19th byte: Data 11
    #       20th byte: Data 12
    #   the last two bytes which are sent to the PLM are calculated in CalcCrcStr
    #   they are not provided by the user and are added herein
    #       21nd byte: CRC High Byte
    #       22nd byte: CRC Low Byte
    # verbose: is a boolean controlling quantity of output
    # external routines: CalcCrcStr
    if len(cmdStr) <> 20:
        print "ERROR: ExtCrc input command not 20 characters"
        return ["", True]
    # this CRC is not the CRC that is used in all Insteon messaging on the wire or RF.  It
    # is additional robustness which can help cover the serial connection from host to PLM.
    crcStr = CalcCrcStr(cmdStr[-14:])
    tempStr = cmdStr + crcStr
    ser.write(tempStr)
    try:
        cmdEcho = ser.read(23)
        stdAck = ser.read(11)
        if extreadback:
            response = ser.read(25)
        else:
            response = ""
    except:
        if verbose:
            print "ERROR: ExtCrc read error"
        return ["", True]
    if extreadback:
        lr = len(response) <> 25
    else:
        lr = False
    if (len(cmdEcho) <> 23) or (len(stdAck) <> 11) or lr:
        if verbose:
            print "ERROR: ExtCrc read error - wrong number of characters"
            print ":".join("{:02x}".format(ord(c)) for c in tempStr)
            print ":".join("{:02x}".format(ord(c)) for c in cmdEcho)
            print("ACK response (0x50): ")
            print ":".join("{:02x}".format(ord(c)) for c in stdAck)
            print("EXT response (0x51): ")
            print ":".join("{:02x}".format(ord(c)) for c in response)
        return ["", True]
    # check to make sure responses line up with sent commands, i.e. no
    # out of order or unsolicited messages
    ackErr = not((cmdEcho[-1] == chr(0x06)))
    stdErr = not((stdAck[1] == chr(0x50)) and (stdAck[-2:] == tempStr[6:8]))
    if extreadback:
        extErr = not((response[1] == chr(0x51)))
    else:
        extErr = False
    if ackErr or stdErr or extErr:
        if verbose:
            print "ERROR: ExtCrc a packet received out of order"
        ser.flushInput()
        ser.flushOutput()
        return ["", True]
    if verbose:
        print ":".join("{:02x}".format(ord(c)) for c in tempStr)
        print ":".join("{:02x}".format(ord(c)) for c in cmdEcho)
        print("ACK response (0x50): ")
        print ":".join("{:02x}".format(ord(c)) for c in stdAck)
        print("EXT response (0x51): ")
        print ":".join("{:02x}".format(ord(c)) for c in response)
    return [response, False]

def ExtChecksum(ser, cmdStr, verbose = False):
    # sends an Insteon extended CS command and gets the response
    # response string and error boolean returned in list
    # ser: serial port handle of the PLM
    # cmdStr: should contain full command to send from 0x02 through data13 = 21 characters
    # this string has the following format:
    #   1st byte (all commands start with this value):  0x02 --> ASCII start of text
    #   2nd byte (code): 0x62 --> Send INSTEON Standard or Extended Message
    #   3rd byte (destination address high byte)
    #   4th byte (destination address middle byte)
    #   5th byte (destination address low byte)
    #   6th byte (flags):  0x1F --> first nibble = 0 for std 1 for ext
    #                               second nibble = 0bnnmm where nn = hops left, mm = max hops
    #   INSTEON Extended message (20 bytes, excludes From Address): 
    #       7th byte:  Command 1
    #       8th byte:  Command 2
    #       9th byte:  Data 1
    #       10th byte: Data 2
    #       11th byte: Data 3
    #       12th byte: Data 4
    #       13th byte: Data 5
    #       14th byte: Data 6
    #       15th byte: Data 7
    #       16th byte: Data 8
    #       17th byte: Data 9
    #       18th byte: Data 10
    #       19th byte: Data 11
    #       20th byte: Data 12
    #       21st byte: Data 13
    #   the last byte which is sent to the PLM is calculated in this routine
    #   it is not provided by the user and is added herein
    #       22nd byte: Data14 - calculated CS
    # verbose: is a boolean controlling quantity of output

    if len(cmdStr) <> 21:
        print "ERROR: ExtChecksum input cmdStr not 21 characters"
        return ["", True]

    # this checksum is not the CRC that is used in all Insteon messaging on the wire or RF.  It
    # is additional robustness which can help cover the serial connection from host to PLM.
    # checksum calculation:  add all bytes from Command 1 (7th byte) through Data13 (21st byte)
    # take the last byte of the sum, bitwise complement, then add 1 (and take last byte)
    # details can be found in the following document:
    # http://cache.insteon.com/developer/i2CSdev-022012-en.pdf
    checksum = chr((((sum(bytearray(cmdStr[-15:]))%256) ^ 0xff) + 0x01)%256)
    tempStr = cmdStr + checksum
    ser.write(tempStr)
    try:
        cmdEcho = ser.read(23)
        stdAck = ser.read(11)
        response = ser.read(25)
    except:
        if verbose:
            print "ERROR: ExtChecksum read error"
        return ["", True]
    if (len(cmdEcho) <> 23) or (len(stdAck) <> 11) or (len(response) <> 25):
        if verbose:
            print "ERROR: ExtChecksum read error - wrong number of characters"
        return ["", True]
    # check to make sure responses line up with sent commands, i.e. no
    # out of order or unsolicited messages
    ackErr = not((cmdEcho[-1] == chr(0x06)))
    stdErr = not((stdAck[1] == chr(0x50)) and (stdAck[-2:] == tempStr[6:8]))
    extErr = not((response[1] == chr(0x51)))
    if ackErr or stdErr or extErr:
        if verbose:
            print "ERROR: ExtChecksum a packet received out of order"
        ser.flushInput()
        ser.flushOutput()
        return ["", True]
    if verbose:
        print ":".join("{:02x}".format(ord(c)) for c in tempStr)
        print ":".join("{:02x}".format(ord(c)) for c in cmdEcho)
        print("ACK response (0x50): ")
        print ":".join("{:02x}".format(ord(c)) for c in stdAck)
        print("EXT response (0x51): ")
        print ":".join("{:02x}".format(ord(c)) for c in response)
    return [response, False]

def StdCmd(ser, cmdStr, verbose = False, nResponse = 1):
    # sends an Insteon standard command and gets the response
    # response string and error boolean returned in list
    # ser: serial port handle of the PLM
    # cmdStr: should contain full command to send from 0x02 through cmd2
    # this string has the following format:
    #   1st byte (all commands start with this value):  0x02 --> ASCII start of text
    #   2nd byte (code): 0x62 --> Send INSTEON Standard or Extended Message
    #   3rd byte (destination address high byte)
    #   4th byte (destination address middle byte)
    #   5th byte (destination address low byte)
    #   6th byte (flags):  0x0F --> first nibble = 0 for std 1 for ext
    #                               second nibble = 0bnnmm where nn = hops left, mm = max hops
    #   INSTEON Standard message (6 bytes, excludes From Address):
    #       7th byte:  Command 1
    #       8th byte:  Command 2
    # verbose: is a boolean controlling quantity of output
    # nResponse: integer number of 0x50 responses to receive

    if len(cmdStr) <> 8:
        print "ERROR: StdCmd input command not 8 characters"
        return ["", True]
    ser.write(cmdStr)
    try:
        cmdEcho = ser.read(9)
        response = ""
        for iResponse in range(nResponse):
            response = response + ser.read(11)
    except:
        if verbose:
            print "ERROR: StdCmd read error"
        return ["", True]
    if (len(cmdEcho) <> 9) or (len(response) <> 11 * nResponse):
        if verbose:
            print "ERROR: StdCmd read error - wrong number of characters"
        return ["", True]
    # check to make sure responses line up with sent commands, i.e. no
    # out of order or unsolicited messages
    ackErr = not((cmdEcho[-1] == chr(0x06)))
    stdErr = False
    for iResponse in range(nResponse):
        iChar = 1 + 11 * iResponse
        stdErr = not((response[iChar] == chr(0x50)) and (not(stdErr)))
    if ackErr or stdErr:
        if verbose:
            print "ERROR: StdCmd a packet received out of order"
        ser.flushInput()
        ser.flushOutput()
        return ["", True]
    if verbose:
        print ":".join("{:02x}".format(ord(c)) for c in cmdStr)
        print ":".join("{:02x}".format(ord(c)) for c in cmdEcho)
        print("STD response (0x50): ")
        print ":".join("{:02x}".format(ord(c)) for c in response)
    return [response, False]

class dimmer:
    """
    Insteon device class for dimmers
    Documentation available at
    http://cache.insteon.com/pdf/INSTEON_Command_Tables_20070925a.pdf
    
    VALUES:
    address:
        provide a 3 element integer array for the address at creation
        the address is arranged as follows for simple readability:
        [high_byte, mid_byte, low_byte]
        This way, it appears in the brackets exactly as you see it
        written on the actual device label.  For example, if the label
        says 00.2B.8E, then the address array is:
        [0x00, 0x2B, 0x8E]
    lastSetOn:
        True if the device was last set to ON, False for OFF, default
        False on creation
    lastSetLevel:
        last level sent to device, default 0 on creation
    lastGetOn:
        Result of the last GetState() method
    lastGetLevel:
        Result of the last GetState() method
    manualOverride:
        indicates that the set and get values are not the same
    errorStatus:
        indicates that the readback from the PLM or dimmer did not work
    verbose:
        True prints a lot of debugging text to stdout while False suppresses

    METHODS:
    SetOn(level):
        turns the dimmer on to the level specified (100% if omitted)
        level is the dimmer value in percent
    SetOff()
        turns the dimmer off
    GetState()
        gets the on and level states and compares to set states to determine
        whether there has been a manual override
    """
    
    lastSetOn = False
    lastSetLevel = 0
    lastGetOn = False
    lastGetLevel = 0
    manualOverride = False
    errorStatus = False
    verbose = False

    def __init__(self,address = [0, 0, 0]):
        self.address=address
        if len(self.address) <> 3:
            print "ERROR: Insteon address length"
            self.address = [0, 0, 0]
        elif max(self.address) > 255 or min(self.address) < 0:
            print "ERROR: Insteon address out of range"
            self.address = [0, 0, 0]
        
    def SetOn(self, plmSerial, level=100):
        if self.address == [0, 0, 0]:
            print "WARNING: No action taken on null address device"
        else:
            if self.verbose:
                print "    set address ", \
                      hex(self.address[0])[2:] + "." + \
                      hex(self.address[1])[2:] + "." + \
                      hex(self.address[2])[2:] + \
                      " ON, level ", level
            plmSerial.flushInput()
            plmSerial.flushOutput()

            # build the data string to send to the PLM in the following format
            # {0x02,0x62,da0,da1,da2,0x0F,0x11,hex_level} 
            # where da is the desination address and hex_level = [0x00..0xFF]
            # we start with a level in percentage and convert it to this range
            tempStr = (chr(0x02) + chr(0x62) + chr(self.address[0]) +
              chr(self.address[1]) + chr(self.address[2]) +
              chr(15) + chr(17) + chr(int(round(level*2.55))))
            [response, localError] = StdCmd(plmSerial, tempStr, self.verbose)

            # better error checking
            self.errorStatus = errorReporting(self.address,\
                               "Set ON, level = " + str(level), localError, \
                               self.errorStatus, True)
            if not localError:
                self.lastSetOn = True
                self.lastSetLevel = level
                self.manualOverride = False

    def SetOff(self, plmSerial):
        if self.address == [0, 0, 0]:
            print "WARNING: No action taken on null address device"
        else:
            if self.verbose:
                print "    set address ", \
                      hex(self.address[0])[2:] + "." + \
                      hex(self.address[1])[2:] + "." + \
                      hex(self.address[2])[2:] +  \
                      " OFF"
            plmSerial.flushInput()
            plmSerial.flushOutput()

            # {2,98,51,70,111,15,19,0}
            tempStr = (chr(2) + chr(98) + chr(self.address[0]) +
              chr(self.address[1]) + chr(self.address[2]) +
              chr(15) + chr(19) + chr(0))
            [response, localError] = StdCmd(plmSerial, tempStr, self.verbose)

            # better error checking
            self.errorStatus = errorReporting(self.address,\
                               "Set OFF", localError, \
                               self.errorStatus, True)
            if not localError:
                self.lastSetOn = False
                self.lastSetLevel = 0
                self.manualOverride = False

    def GetState(self, plmSerial):
        if self.address == [0, 0, 0]:
            print "WARNING: No action taken on null address device"
        else:
            if self.verbose:
                print "    get address ", \
                      hex(self.address[0])[2:] + "." + \
                      hex(self.address[1])[2:] + "." + \
                      hex(self.address[2])[2:]

            plmSerial.flushInput()
            plmSerial.flushOutput()

            # {2,98,51,70,111,15,25,0}
            tempStr = (chr(2) + chr(98) + chr(self.address[0]) +
              chr(self.address[1]) + chr(self.address[2]) +
              chr(15) + chr(25) + chr(0))
            [response, localError] = StdCmd(plmSerial, tempStr, self.verbose)

            self.errorStatus = errorReporting(self.address,\
                               "GetState", localError, \
                               self.errorStatus, True)
            if not localError:
                x = ord(response[-1:])
                if x == 0:
                    self.lastGetOn = False
                else:
                    self.lastGetOn = True

                self.lastGetLevel = int(round(x/2.55))
                # test to see if manual override has been enacted with 2% slop
                if self.lastGetOn <> self.lastSetOn or \
                   abs(self.lastGetLevel - self.lastSetLevel) > 2:
                    self.manualOverride = True

class thermostat:
    """
    Insteon device class for thermostats
    Documentation available at
    http://cache.insteon.com/developer/2441ZTHdev-112012-en.pdf

    VALUES:
    address:
        provide a 3 element integer array for the address at creation
        the address is arranged as follows for simple readability:
        [high_byte, mid_byte, low_byte]
        This way, it appears in the brackets exactly as you see it
        written on the actual device label.  For example, if the label
        says 00.2B.8E, then the address array is:
        [0x00, 0x2B, 0x8E]
    mode:
        integer indicating the mode of the thermostat, heat, cool, auto
    modeText:
        text representation of mode
    targetHeat:
        current heating setpoint (1C resolution)
    targetCool:
        current cooling setpoint (1C resolution)
    actualTemp:
        current ambient temperature (0.1C resolution)
    actualHumi:
        current ambient percent relative humidity (1% resolution)
    schedule:
        7x16 2D list of text values holding the current schedule (default [])
    errorStatus:
        indicates that the readback from the PLM or thermostat did not work
    verbose:
        True prints a lot of debugging text to stdout while False suppresses

    METHODS:
    GetState(PLM)
        gets the on and level states and compares to set states to determine
        whether there has been a manual override

    GetSchedule(PLM)
        get the current schecule from the thermostat and save in .schedule

    SetSchedule(PLM, schedule)
        set the current schecule to the thermostat and save in .schedule

    UpSetPoint(PLM)
        equivalent to pushing up button on faceplate

    DownSetPoint(PLM)
        equivalent to pushing down button on faceplate

    TO DO:

    SetMode(PLM, mode) - doesn't work as set out in the manual
        set the thermostat mode, 4 = Heat, 5 = Cool, 10 = Auto

    SetHetSetpoint(PLM, setpoint) - don't need
        set the heat setpoint to setpoint in degrees C rounded to 1C

    SetCoolSetpoint(PLM, setpoint) - don't need
        set the cooling setpoint to setpoint in degrees C rounded to 1C
    """
    ## from thermostats table:
    ##mode INTEGER,
    ##targetheat NUMERIC,
    ##targetcool NUMERIC,
    ##acutaltemp NUMERIC,
    ##actualhumi NUMERIC,
    ##error BOOLEAN,

    mode = 0x08
    modeText = "unknown"
    targetHeat = 0
    targetCool = 0
    actualTemp = 0
    actualHumi = 0
    schedule = []
    errorStatus = False
    verbose = False

    def __init__(self,address = [0, 0, 0]):
        self.address=address
        if len(self.address) <> 3:
            print "ERROR: Insteon address length"
            self.address = [0, 0, 0]
        elif max(self.address) > 255 or min(self.address) < 0:
            print "ERROR: Insteon address out of range"
            self.address = [0, 0, 0]

    def GetState(self, plmSerial):
        if self.address == [0, 0, 0]:
            print "WARNING: No action taken on null address device"
        else:
            if self.verbose:
                print "    get address ", \
                      hex(self.address[0])[2:] + "." + \
                      hex(self.address[1])[2:] + "." + \
                      hex(self.address[2])[2:] + \
                      " GetState"

            plmSerial.flushInput()
            plmSerial.flushOutput()
            cumError = False
            preStr = chr(0x02) + chr(0x62) + chr(self.address[0]) + \
                     chr(self.address[1]) + chr(self.address[2]) + chr(0x0F)

            # get thermostat mode
            cmdStr = chr(0x6B) + chr(0x02)
            tempStr = preStr + cmdStr
            [response, localError] = StdCmd(plmSerial, tempStr, self.verbose)
            cumError = localError or cumError
            try:
                responseMode = ord(response[-1])
            except:
                responseMode = 9
            if not localError and (responseMode < 8) and (responseMode >=0):
                # 0x00 = Off
                # 0x01 = Heat
                # 0x02 = Cool
                # 0x03 = Auto
                # 0x04 = Fan
                # 0x05 = Program
                # 0x06 = Program Heat
                # 0x07 = Program Cool
                # 0x08 = unknown - not returned from thermostat
                modeTextArray = ["Off", "Heat", "Cool", "Auto", "Fan", "Program", \
                            "Program Heat", "Program Cool" ,"Unknown"]
                self.mode = responseMode
                self.modeText = modeTextArray[self.mode]
                if self.verbose:
                    print "mode =", self.modeText
            else:
                # keep the error in cumError and try to move on
                cumError = True
                plmSerial.flushInput()
                plmSerial.flushOutput()
                
            # get zone information, zone 0 setpoint
            cmdStr = chr(0x6A) + chr(0b00100000)
            tempStr = preStr + cmdStr
            [response, localError] = StdCmd(plmSerial, tempStr, self.verbose, 2)
            cumError = localError or cumError
            responseHeat = response[:11]
            responseCool = response[11:]
            if not localError:
                self.targetHeat = int(float(ord(responseHeat[-1]))/2.0+0.5)
                self.targetCool = int(float(ord(responseCool[-1]))/2.0+0.5)
                if self.verbose:
                    print "heat setpoint:", self.targetHeat
                    print "cool setpoint:", self.targetCool
            else:
                # keep the error in cumError and try to move on
                plmSerial.flushInput()
                plmSerial.flushOutput()

            # get zone information, zone 0 humidity
            cmdStr = chr(0x6A) + chr(0b01100000)
            tempStr = preStr + cmdStr
            [response, localError] = StdCmd(plmSerial, tempStr, self.verbose)
            cumError = localError or cumError
            if not localError:
                self.actualHumi = float(ord(response[-1]))
                if self.verbose:
                    print "zone 0 humidity:", str(self.actualHumi) + "%"
            else:
                # keep the error in cumError and try to move on
                plmSerial.flushInput()
                plmSerial.flushOutput()

            # get dataset 1 extended CS command
            preExt = preStr[:-1] + chr(0x1F)
            extCmdData = chr(0x2E) + chr(0x00) + \
                         chr(0x00) + chr(0x00) + chr(0x00) + chr(0x00) + \
                         chr(0x00) + chr(0x00) + chr(0x00) + chr(0x00) + \
                         chr(0x00) + chr(0x00) + chr(0x00) + chr(0x00) + \
                         chr(0x00)
            tempStr = preExt + extCmdData
            [response, localError] = ExtChecksum(plmSerial, tempStr, \
                                                 self.verbose)
            cumError = localError or cumError
            if not localError:
                self.actualTemp = (ord(response[13])*256 + \
                                   ord(response[14]))/10.0
                if self.verbose:
                    print "ambient temperature:", self.actualTemp
            else:
                # keep the error in cumError and try to move on
                plmSerial.flushInput()
                plmSerial.flushOutput()

            # end of work, now set the overall error state    
            self.errorStatus = errorReporting(self.address,\
                               "GetStatus", cumError, \
                               self.errorStatus, True)

    def UpSetPoint(self, plmSerial):
        if self.address == [0, 0, 0]:
            print "WARNING: No action taken on null address device"
        else:
            if self.verbose:
                print "    set address ", \
                      hex(self.address[0])[2:] + "." + \
                      hex(self.address[1])[2:] + "." + \
                      hex(self.address[2])[2:] +  \
                      " UpSetPoint"
            plmSerial.flushInput()
            plmSerial.flushOutput()

            # {2,98,51,70,111,15,0x15,0}
            tempStr = (chr(2) + chr(98) + chr(self.address[0]) +
              chr(self.address[1]) + chr(self.address[2]) +
              chr(15) + chr(0x15) + chr(0))
            [response, localError] = StdCmd(plmSerial, tempStr, self.verbose)
            time.sleep(1.5)

            # better error checking
            self.errorStatus = errorReporting(self.address,\
                               "UpSetPoint", localError, \
                               self.errorStatus, True)

    def DownSetPoint(self, plmSerial):
        if self.address == [0, 0, 0]:
            print "WARNING: No action taken on null address device"
        else:
            if self.verbose:
                print "    set address ", \
                      hex(self.address[0])[2:] + "." + \
                      hex(self.address[1])[2:] + "." + \
                      hex(self.address[2])[2:] +  \
                      " DownSetPoint"
            plmSerial.flushInput()
            plmSerial.flushOutput()

            # {2,98,51,70,111,15,0x16,0}
            tempStr = (chr(2) + chr(98) + chr(self.address[0]) +
              chr(self.address[1]) + chr(self.address[2]) +
              chr(15) + chr(0x16) + chr(0))
            [response, localError] = StdCmd(plmSerial, tempStr, self.verbose)
            time.sleep(1.5)

            # better error checking
            self.errorStatus = errorReporting(self.address,\
                               "DownSetPoint", localError, \
                               self.errorStatus, True)

    def GetSchedule(self, plmSerial, deviceId = 8, zone = 0):
        if self.address == [0, 0, 0]:
            print "WARNING: No action taken on null address device"
        else:
            if self.verbose:
                print "    get address ", \
                      hex(self.address[0])[2:] + "." + \
                      hex(self.address[1])[2:] + "." + \
                      hex(self.address[2])[2:] + \
                      " GetSchedule"

            plmSerial.flushInput()
            plmSerial.flushOutput()
            scheduleMode = 7
            cumError = False

            prefixStr = chr(0x02) + chr(0x62) + chr(self.address[0]) + \
                     chr(self.address[1]) + chr(self.address[2]) + chr(0x1F)
            data1Thru12 = chr(0x00) + chr(0x00) + chr(0x00) + chr(0x00) + \
                          chr(0x00) + chr(0x00) + chr(0x00) + chr(0x00) + \
                          chr(0x00) + chr(0x00) + chr(0x00) + chr(0x00)
            cmd1 = chr(0x2e)
            schedTable = []
            tfmt = "{0:d}:{1:0>2d}:00"
            
            for iDay in range (7):
                cmd2 = chr(0x0a + iDay * 2)
                tempStr = prefixStr + cmd1 + cmd2 + data1Thru12
                [response, localError] = ExtCrc(plmSerial, tempStr, \
                                                self.verbose)
                cumError = localError or cumError
                if not localError:
                    cmdCheck = (ord(response[10]) == ord(cmd2) + 1)
                    timeCheck = (ord(response[11]) < 96) and \
                                (ord(response[14]) < 96) and \
                                (ord(response[17]) < 96) and \
                                (ord(response[20]) < 96)
                else:
                    cmdCheck = False
                    timeCheck = False
                if (not cumError) and cmdCheck and timeCheck:
                    ##mysql> describe thermostatschedule;
                    ##+--------------+---------+
                    ##| Field        | Type    |
                    ##+--------------+---------+
                    ##| scheduleid   | int(11) |
                    ##| deviceid     | int(11) |
                    ##| zone         | int(11) |
                    ##| schedulemode | int(11) |
                    ##| day          | int(11) |
                    ##| waketime     | time    |
                    ##| wakecool     | int(11) |
                    ##| wakeheat     | int(11) |
                    ##| leavetime    | time    |
                    ##| leavecool    | int(11) |
                    ##| leaveheat    | int(11) |
                    ##| returntime   | time    |
                    ##| returncool   | int(11) |
                    ##| returnheat   | int(11) |
                    ##| sleeptime    | time    |
                    ##| sleepcool    | int(11) |
                    ##| sleepheat    | int(11) |
                    ##+--------------+---------+
                    scheduleId = iDay + 1 + (scheduleMode - 1) * 7 + 49 * zone
                    schedLine = []
                    schedLine.append(str(scheduleId))
                    schedLine.append(str(deviceId))
                    schedLine.append(str(zone))
                    schedLine.append(str(scheduleMode))
                    schedLine.append(str(iDay))
                    for iPeriod in range(4):
                        t = ord(response[11 + iPeriod * 3])/4.0
                        h = int(t)
                        m = int((t - h) * 60)
                        schedLine.append(tfmt.format(h, m))
                        schedLine.append(str(ord(response[12 + iPeriod * 3])))
                        schedLine.append(str(ord(response[13 + iPeriod * 3])))

                    schedTable.append(schedLine)
                else:
                    cumError = True

            # end of work, now save the table and set the overall error state
            self.errorStatus = errorReporting(self.address,\
                               "GetSchedule", cumError, \
                               self.errorStatus, True)
            if not cumError:
                self.schedule = schedTable

    def SetSchedule(self, plmSerial, schedTable):
        if self.address == [0, 0, 0]:
            print "WARNING: No action taken on null address device"
        elif len(schedTable) <> 7:
            print "WARNING: schedule table not 7 days long ",len(schedTable)
        else:
            if self.verbose:
                print "    get address ", \
                      hex(self.address[0])[2:] + "." + \
                      hex(self.address[1])[2:] + "." + \
                      hex(self.address[2])[2:] + \
                      " SetSchedule"

            plmSerial.flushInput()
            plmSerial.flushOutput()
            cumError = False

            prefixStr = chr(0x02) + chr(0x62) + chr(self.address[0]) + \
                     chr(self.address[1]) + chr(self.address[2]) + chr(0x1F)
            cmd1 = chr(0x2e)
            
            # iDay = 0
            for schedRow in schedTable:
                # iDay += 1
                # print "shedule row =", iDay
                cmd2 = chr(0x03 + int(schedRow[4]))
                
                data1Thru12 = ""
                for iPeriod in range(4):
                    iCol = iPeriod * 3 + 5
                    [h, m] = [int(a) for a in schedRow[iCol].split(":")[0:2]]
                    timebyte = chr(h*4 + m/15)
                    coolbyte = chr(int(schedRow[iCol + 1]))
                    heatbyte = chr(int(schedRow[iCol + 2]))
                    data1Thru12 = data1Thru12 + timebyte + coolbyte + heatbyte
                    
                tempStr = prefixStr + cmd1 + cmd2 + data1Thru12
                [response, localError] = ExtCrc(plmSerial, tempStr, \
                                                self.verbose, False)
                cumError = localError or cumError
                time.sleep(4)

            # end of work, now save the table and set the overall error state
            self.errorStatus = errorReporting(self.address,\
                               "SetSchedule", cumError, \
                               self.errorStatus, True)
            if not cumError:
                self.schedule = schedTable

    def SetMode(self, plmSerial, mode):
        if self.address == [0, 0, 0]:
            print "WARNING: No action taken on null address device"
        elif mode < 4 or mode > 10:
            print "WARNING: mode setting for thermostat out of range:", mode
        else:
            if self.verbose:
                print "    set address ", \
                      hex(self.address[0])[2:] + "." + \
                      hex(self.address[1])[2:] + "." + \
                      hex(self.address[2])[2:] +  \
                      " SetMode"
            plmSerial.flushInput()
            plmSerial.flushOutput()
            
            # readback
            # 0x00 = Off
            # 0x01 = Heat
            # 0x02 = Cool
            # 0x03 = Auto
            # 0x04 = Fan
            # 0x05 = Program
            # 0x06 = Program Heat
            # 0x07 = Program Cool
            # 0x08 = unknown - not returned from thermostat

            # set
            # 0x04 = On Heat
            # 0x05 = On Cool
            # 0x06 = Manual Auto
            # 0x07 = On Fan
            # 0x08 = Off Fan
            # 0x09 = Off All
            # 0x0a = Auto

            # {2,98,51,70,111,15,0x6b,0}
            #tempStr = (chr(2) + chr(98) + chr(self.address[0]) +
            #  chr(self.address[1]) + chr(self.address[2]) +
            #  chr(15) + chr(0x6B) + chr(mode))
            #[response, localError] = StdCmd(plmSerial, tempStr, self.verbose)
            #time.sleep(1.5)

            prefixStr = chr(0x02) + chr(0x62) + chr(self.address[0]) + \
                     chr(self.address[1]) + chr(self.address[2]) + chr(0x1F)
            cmd1 = chr(0x6B)
            cmd2 = chr(int(mode))
            data1Thru13 = chr(0x00) + chr(0x00) + chr(0x00) + chr(0x00) + \
                          chr(0x00) + chr(0x00) + chr(0x00) + chr(0x00) + \
                          chr(0x00) + chr(0x00) + chr(0x00) + chr(0x00) + \
                          chr(0x00)
            tempStr = prefixStr + cmd1 + cmd2 + data1Thru13
            [response, localError] = ExtChecksum(plmSerial, tempStr, \
                                     self.verbose)
            time.sleep(1.5)

            # better error checking
            self.errorStatus = errorReporting(self.address,\
                               "SetMode", localError, \
                               self.errorStatus, True)

if __name__ == '__main__':
    """
    Example of how to use the device classes and their functions
    """
    import serial
    machine = "unix"
    #machine = "windows"
    # PLM serial port connection settings and open
    #
    if machine == "unix":
        SERIALPORT = "/dev/ttyUSB0"         #put your device path here
    elif machine == "windows":
        SERIALPORT = "COM3"                 #windows version
    BAUDRATE = 19200                        #standard for Insteon PLMs
    insteonPlm = serial.Serial(SERIALPORT, BAUDRATE)
    insteonPlm.bytesize = serial.EIGHTBITS  #number of bits per bytes
    insteonPlm.parity = serial.PARITY_NONE  #set parity check: no parity
    insteonPlm.stopbits = serial.STOPBITS_ONE   #number of stop bits
    #insteonPlm.timeout = None              #block read
    #insteonPlm.timeout = 0                 #non-block read
    insteonPlm.timeout = 2                  #timeout block read
    insteonPlm.xonxoff = False              #disable software flow control
    insteonPlm.rtscts = False               #disable hardware (RTS/CTS) flow control
    insteonPlm.dsrdtr = False               #disable hardware (DSR/DTR) flow control
    insteonPlm.writeTimeout = 0             #timeout for write

    if machine == "windows":
        pass
    else:
        attempts = 0
        maxattempts = 10
        attemptwait = 30
        success = False
        while (not success) and (attempts < maxattempts):
            try:
                insteonPlm.open()
                success = True
            except Exception, e:
                print "ERROR: opening serial port PLM connection: " + str(e)
                attempts += 1
                success = False
                time.sleep(attemptwait)

        if not success:
            print "FATAL: couldn't open serial port connection to PLM"
            exit()

    dimmerAddresses = []
    dimmerAddresses.append([0x00,0x00,0x00]) #append as many addresses as you have dimmers
    dimmers = []
    for address in dimmerAddresses:
        dimmers.append(dimmer(address))
    print len(dimmers),"dimmers setup"
    for iDimmer, dimmer in enumerate(dimmers):
        dimmer.GetState(insteonPlm)
        print "dimmer", iDimmer, "set to", dimmer.lastGetLevel
    
    thermostatAddresses = []
    thermostatAddresses.append([0x00,0x00,0x00]) #append as many addresses as you have thermostats
    thermostats = []
    for address in thermostatAddresses:
        thermostats.append(thermostat(address))
    print len(thermostats),"thermostats setup"
    for iThermostat, thermostat in enumerate(thermostats):
        thermostat.GetState(insteonPlm)
        print "thermostat", iThermostat, "temperature is", thermostat.actualTemp
