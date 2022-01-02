import datetime

# RTC is available from SERA PMU slave id/address 0xF
# There is an RTC_TIME(32.16 fixed point) value to be added to an RTC_OFFSET(33.15 fixed point) value.

# SPMI Base address: 0x23d0d8000 + 0x1300 = 0x23d0d9300

# SPMI_STATUS_REG : 0x00
# SPMI_RX_FIFO_EMPTY: 1<<24
# SPMI_CMD_REG : 0x04
# SPMI_RSP_REG: 0x08

# Check Status: Expecting SPMI_RX_FIFO_EMPTY set, something like 0x1000100
p.read32(0x23d0d8000 + 0x1300)

''' SPMI READ EXT CMD to read RTC TIME Reg:
    SPMI_CMD_EXT_READL	0x38
    SPMI_CMD_LAST       (1<<15)
    PMU_SERA_SLAVE_ID   0x0f
    RTC_TIME_ADDR		0xd002
    RTC_TIME_LEN		6

    Resulting command:
        SPMI_CMD_EXT_READL | PMU_SERA_SLAVE_ID<<8 | RTC_TIME_ADDR<<16 | RTC_TIME_LEN-1 | SMPI_CMD_LAST
        => 0xd0028f3d
'''
p.write32(0x23d0d8000 + 0x1304, 0xd0028f3d)


# Check if there is data in Rx FIFO (bit 24); Expecting SPMI_RX_FIFO_EMPTY not set, something like 0x30100
p.read32(0x23d0d8000 + 0x1300)

# Reading RSP: Expecting something like 0x3f0f3d SPMI RSP
p.read32(0x23d0d8000 + 0x1308)

# Checking SPMI_STATUS_REG: we can see the count of RSP to read reducing from 3 to 2: bit 16-17 of something like 0x20100
p.read32(0x23d0d8000 + 0x1300)

# Reading data rsp first part Expecting 4 bytes
rtc_time = p.read32(0x23d0d8000 + 0x1308)

# Checking SPMI_STATUS_REG: we can see the count of RSP to read reducing from 2 to 3: bit 16-17 of something like 0x10100
p.read32(0x23d0d8000 + 0x1300)

# Reading data rsp 2nd part Expecting 2 bytes
rtc_time = rtc_time + (p.read32(0x23d0d8000 + 0x1308)<<32)

# Check Status: Expecting SPMI_RX_FIFO_EMPTY set, something like 0x1000100
p.read32(0x23d0d8000 + 0x1300)


'''
    Reading RTC_OFFSET value
    Same as RTC TIME Reg, only the address is different:
    RTC_OFFSET_ADDR     0xd100
    RTC_OFFSET_LEN    6
    => 0xd1008f3d
'''
p.write32(0x23d0d8000 + 0x1304, 0xd1008f3d)

# Check if there is data in Rx FIFO (bit 24); Expecting SPMI_RX_FIFO_EMPTY not set, something like 0x30100
p.read32(0x23d0d8000 + 0x1300)

# Reading RSP: Expecting something like 0x3f0f3d SPMI RSP
p.read32(0x23d0d8000 + 0x1308)

# Checking SPMI_STATUS_REG: we can see the count of RSP to read reducing from 3 to 2: bit 16-17 of something like 0x20100
p.read32(0x23d0d8000 + 0x1300)

# Reading data rsp first part Expecting 4 bytes
rtc_offset = p.read32(0x23d0d8000 + 0x1308)

# Checking SPMI_STATUS_REG: we can see the count of RSP to read reducing from 2 to 3: bit 16-17 of something like 0x10100
p.read32(0x23d0d8000 + 0x1300)

# Reading data rsp 2nd part Expecting 2 bytes
rtc_offset = rtc_offset + (p.read32(0x23d0d8000 + 0x1308)<<32)

# Check Status: Expecting SPMI_RX_FIFO_EMPTY set, something like 0x1000100
p.read32(0x23d0d8000 + 0x1300)

print('time:',rtc_time)
print('offset:',rtc_offset)

print('Epoch time:',(rtc_time+(rtc_offset<<1))>>16)
print('Actual time:',datetime.datetime.fromtimestamp((rtc_time+(rtc_offset<<1))>>16))

