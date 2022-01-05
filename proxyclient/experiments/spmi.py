import datetime

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from m1n1.utils import Register32,RegMap
from m1n1.setup import *
from m1n1.shell import run_shell

spmi0 = u.adt["/arm-io/nub-spmi"]

spmi0_base_addr = spmi0.get_reg(0)[0]

class R_STATUS(Register32):
    RX_FIFO_EMPTY   = 24
    RX_FIFO_CNT     = 21,16

class R_CMD(Register32):
    REG_ADDR    = 31,16
    LAST        = 15    
    SLAVE_ID    = 7,4
    CMD         = 5,3
    LEN         = 2,0


class SPMIRegs(RegMap):
    STATUS   = 0x00, R_STATUS
    CMD      = 0x04, R_CMD
    RSP      = 0x08, Register32

# RTC is available from SERA PMU slave id/address 0xF
# There is an RTC_TIME(32.16 fixed point) value to be added to an RTC_OFFSET(33.15 fixed point) value.

# SPMI Base address: 0x23d0d8000 + 0x1300 = 0x23d0d9300

# SPMI_STATUS_REG : 0x00
# SPMI_RX_FIFO_EMPTY: 1<<24
# SPMI_CMD_REG : 0x04
# SPMI_RSP_REG: 0x08

def spmi_cmd(cmd):
    r.CMD.val = cmd

def spmi_read_rsp():
    rsp=[]
    while r.STATUS.reg.RX_FIFO_CNT !=0:
        print('SPMI Status:',r.STATUS)
        rsp.append(r.RSP.val)
        print('SPMI Rsp({}):'.format(len(rsp)-1),hex(rsp[len(rsp)-1]))

    print('SPMI Status:',r.STATUS)
    return(rsp)


r=SPMIRegs(u,spmi0_base_addr)

print('SPMI STATUS:',r.STATUS)

def gettime():
    ''' SPMI READ EXT CMD to read RTC TIME Reg:
        SPMI_CMD_EXT_READL	0x38
        SPMI_CMD_LAST       (1<<15)
        PMU_SERA_SLAVE_ID   0x0f
        RTC_TIME_ADDR		0xd002
        RTC_TIME_LEN		6

        Resulting command:
            SPMI_CMD_EXT_READL | PMU_SERA_SLAVE_ID<<8 | RTC_TIME_ADDR<<16 | RTC_TIME_LEN-1 | SMPI_CMD_LAST
            => 0xd0028f3d
            0x3d = 0b0011 1 101
    '''
    spmi_cmd(0xd0028f3d)
    rsp=spmi_read_rsp()
    rtc_time = rsp[1] + (rsp[2]<<32)

    '''
        Reading RTC_OFFSET value
        Same as RTC TIME Reg, only the address is different:
        RTC_OFFSET_ADDR     0xd100
        RTC_OFFSET_LEN    6
        => 0xd1008f3d
    '''
    spmi_cmd(0xd1008f3d)
    rsp=spmi_read_rsp()
    rtc_offset = rsp[1] + (rsp[2]<<32)

    print('time:',rtc_time)
    print('offset:',rtc_offset)

    current_time=(rtc_time+(rtc_offset<<1))>>16
    print('Epoch time:',current_time)
    print('Actual time:',datetime.datetime.fromtimestamp(current_time))

    return current_time

def settime(t):
    spmi_cmd(0xd0028f3d)
    rsp=spmi_read_rsp()
    rtc_time = rsp[1] + (rsp[2]<<32)

    new_offset = (t<<16)-rtc_time

    '''
        SPMI_CMD_EXT_WRITEL	0x30
        Replace EXT_READL(0x38) by EXT_WRITEL (0x30) in 0xd1008f3d
        => 0xd1008f35
    '''

    spmi_cmd(0xd1008f35)
    spmi_cmd(0xFFFFFFFF & (new_offset>>1))
    spmi_cmd((0xFFFF00000000 & (new_offset>>1))>>32)
    spmi_read_rsp()

print('\nChanging time 1h back in time')
settime(gettime()-3600)
print('\n\nChanged time to:',gettime())

settime(gettime()+3601)
print('\n\nPut time back:',gettime())
print('\n')


#run_shell(globals(), msg="Have fun!")
