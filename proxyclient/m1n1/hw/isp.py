import struct
from enum import IntEnum
from ..utils import *

class ISPCommandDirection(IntEnum):
    RX = 0
    TX = 1

class ISPCommand:
    """ Represents a command in any IPC channel """

    def __init__(self, channel, message, direction):
        value, u0, u1 = struct.unpack('<3q40x', message.data)
        self.message = message
        self.channel = channel
        self.direction = direction
        self.tracer = channel.tracer
        self.raw_value = value
        self.value = value & 0xFFFFFFFFFFFFFFFC
        self.arg0 = u0
        self.arg1 = u1

    def dump(self):
        self.log(f"[CMD Value: {hex(self.value)}, U0: {hex(self.arg0)}, U1: {hex(self.arg1)}]")

    def read_iova(self, address, length):
        return self.tracer.dart.ioread(0, address, length)

    def valid(self):
        return True

    def log(self, message):
        if self.direction is ISPCommandDirection.RX:
            self.tracer.log(f"<== [{self.channel.name}]({self.message.index}): {message}")
        else:
            self.tracer.log(f"==> [{self.channel.name}]({self.message.index}): {message}")

class ISPTerminalCommand(ISPCommand):
    """ Represents a command in TERMINAL channel 

    A command arguments include a pointer to a buffer that contains log line 
    and the length of the buffer. Buffers are 0x80 bytes wide.
    """
    # ISP sends buffer address at beginning
    BUFFER_ADDRESS = None
    # It seems messages are capped to 100 bytes
    MAX_BUFFER_SIZE = 0x80 

    @staticmethod
    def set_address(address):
        if address != 0:
            ISPTerminalCommand.BUFFER_ADDRESS = address

    @staticmethod
    def move_cursor():
        if ISPTerminalCommand.BUFFER_ADDRESS:
            ISPTerminalCommand.BUFFER_ADDRESS += ISPTerminalCommand.MAX_BUFFER_SIZE
        else:
            return None

    def __init__(self, channel, message, direction):
        super().__init__(channel, message, direction)

        ## Set buffer address
        ISPTerminalCommand.set_address(self.value)

        ## Read contents 
        self.buffer_message = self.read_iova(ISPTerminalCommand.BUFFER_ADDRESS, self.arg0)

        ## Move cursor
        ISPTerminalCommand.move_cursor()

    def dump(self):
        self.log(f"ISPCPU: {self.buffer_message}]")

    def log(self, message):
        self.tracer.log(f"[{self.channel.name}]({str(self.message.index).ljust(3)}): {message}") 

class ISPIOCommand(ISPCommand):
    """ Represents a command in IO channel 

    An IO command is used to request ISP to perform some operations. The command
    contains a pointer to a command struct which contains a OPCODE. The OPCODE 
    is used to differentate commands.
    """

    def __init__(self, channel, message, direction):
        super().__init__(channel, message, direction)
        self.iova = self.value
        if self.iova != 0:
            contents = self.read_iova(self.iova, 0x8)
            self.contents = int.from_bytes(contents, byteorder="little")
        else:
            self.contents = None

    def dump(self):
        if self.iova != 0:
            self.log(f"[IO Addr: {hex(self.iova)}, Size: {hex(self.arg0)}, U1: {hex(self.arg1)} -> Opcode: {hex(self.contents >> 32)}]")

class ISPT2HBufferCommand(ISPCommand):
    """ Represents a command in BUF_T2H channel """
    def __init__(self, channel, message, direction):
        super().__init__(channel, message, direction)
        self.iova = self.value
        if self.iova != 0:
            self.contents = self.read_iova(self.iova, 0x280)

    def dump(self):
        super().dump()
        if self.iova != 0:
            chexdump(self.contents)

class ISPH2TBufferCommand(ISPCommand):
    """ Represents a command in BUF_H2T channel """
    def __init__(self, channel, message, direction):
        super().__init__(channel, message, direction)
        self.iova = self.value
        if self.iova != 0:
            # Dumping first 0x20 bytes after iova translation, but no idea how internal struct
            self.contents = self.read_iova(self.iova, 0x20)

    def dump(self):
        super().dump()
        if self.iova != 0:
            chexdump(self.contents)

class ISPT2HIOCommand(ISPCommand):
    """ Represents a command in IO_T2H channel """
    def __init__(self, channel, message, direction):
        super().__init__(channel, message, direction)
        self.iova = self.value
        if self.iova != 0:
            # Dumping first 0x20 bytes after iova translation, but no idea how internal struct
            self.contents = self.read_iova(self.iova, 0x20)

    def dump(self):
        super().dump()
        if self.iova != 0:
            chexdump(self.contents)

class ISPSharedMallocCommand(ISPCommand):
    """ Represents a command in SHAREDMALLOC channel

    A command of this type can either request memory allocation or memory free 
    depending the arguments. When ISP needs to allocate memory, it puts a 
    message in the SHAREDMALLOC channel, message arguments are length of buffer
    and type of allocation. 

    CPU detects the new message, perform memory allocation and mutate the 
    original message to indicate the address of the allocated memory block.
    """

    def __init__(self, channel, message, direction):
        super().__init__(channel, message, direction)
        self.address = self.value
        self.size = self.arg0
        self.type = self.arg1 #.to_bytes(8, byteorder="little")

    def dump(self):
        if self.direction == ISPCommandDirection.RX:
            if self.address is 0:
                self.log(f"[FW Malloc, Length: {hex(self.size)}, Type: {hex(self.type)}]")
            else:
                self.log(f"[FW Free, Address: {hex(self.value)}, Length: {hex(self.size)}, Type: {hex(self.type)})]")
        else:
            if self.address is 0:
                self.log(f"[FW Free]")
            else:
                self.log(f"[FW Malloc, Address: {hex(self.value)}, Type: {hex(self.type)})]")

class ISPChannelTable:
    """ A class used to present IPC table.

    The Channel Table describes the IPC channels available to communicate with
    the ISP. 

    In the M1 processor (tonga), the list of channels exposed by ISP are:
        [CH - TERMINAL] (src = 0, type = 2, entries = 768, iova = 0x1804700)
        [CH - IO] (src = 1, type = 0, entries = 8, iova = 0x1810700)
        [CH - BUF_H2T] (src = 2, type = 0, entries = 64, iova = 0x1810b00)
        [CH - BUF_T2H] (src = 3, type = 1, entries = 64, iova = 0x1811b00)
        [CH - SHAREDMALLOC] (src = 3, type = 1, entries = 8, iova = 0x1812b00)
        [CH - IO_T2H] (src = 3, type = 1, entries = 8, iova = 0x1812d00)

    Each entry in the table is 256 bytes wide. Here is the layout of each entry:
        0x00 - 0x1F = Name (NULL terminated string)
        0x20 - 0x3F = Padding
        0x40 - 0x43 = Type (DWORD)
        0x44 - 0x47 = Source (DWORD)
        0x48 - 0x4F = Entries (QWORD)
        0x50 - 0x58 = Address (QWORD)
    """

    ENTRY_LENGTH = 256

    def __init__(self, tracer, number_of_channels, table_address):
        self.tracer = tracer
        self.address = table_address
        self.count = number_of_channels
        self.size = number_of_channels * self.ENTRY_LENGTH
        self.channels = []

        _table = self.ioread(self.address & 0xFFFFFFFF, self.size)
        for offset in range(0, self.size, self.ENTRY_LENGTH):
            _entry =  _table[offset: offset + self.ENTRY_LENGTH]
            _name, _type, _source, _entries, _address = struct.unpack('<32s32x2I2q168x', _entry)
            _channel = ISPChannel(self, _name, _type, _source, _entries, _address)
            # We want to process terminal logs as fast as possible before they are processed by CPU
            # So we use a special implementation for TERMINAL channel that fetches all logs 
            if _channel.name == "TERMINAL":
                _channel = ISPTerminalChannel(self, _name, _type, _source, _entries, _address)
            self.channels.append(_channel)

    def get_last_write_command(self, doorbell_value):
        """ Gets last written message given a Doorbell value """
        if self.channels and len(self.channels) > 0:
            names = []
            channel_cmds = []
            for channel in self.channels:
                # We want to process terminal logs as fast as possible before they are processed by CPU
                if (channel.doorbell == doorbell_value) or channel.name == "TERMINAL":
                    names.append(channel.name)
                    for cmd in channel.get_commands(ISPCommandDirection.TX):
                        channel_cmds.append(cmd)

            self.log(f"CHs: [{(','.join(names))}]")
            for cmd in channel_cmds:
                cmd.dump()
                
    def get_last_read_command(self, pending_irq):
        """ Gets last read message given a IRQ value """
        cmds = []
        scanned_channels = []
        if self.channels and len(self.channels) > 0:
            cidx = 0
            for channel in self.channels:
                if (pending_irq >> channel.source & 1) != 0:
                    scanned_channels.append(channel.name)
                    for cmd in channel.get_commands(ISPCommandDirection.RX):
                        cmds.append(cmd)
                cidx = cidx + 1 
        
        if len(scanned_channels) > 0:
            self.log(f"CHs: [{(','.join(scanned_channels))}]")
            for cmd in cmds:
                cmd.dump()

    def dump(self):
        """ Dumps the content of each channel """
        if self.channels and len(self.channels) > 0:
            for channel in self.channels:
                channel.dump()

    def ioread(self, address, size):
        return self.tracer.ioread(address, size)

    def log(self, message):
        self.tracer.log(message)
    
    def __str__(self):
        s = "======== CHANNEL TABLE ========\n"
        for channel in self.channels:
            s += f"\t{str(channel)}\n"
        return s

class ISPChannel:
    """ A class used to represent IPC channel

    ISP channels are ring buffers used by communication between CPU and ISP.
    channel length is measured in number of entries, each entry is 64 bytes,
    so channel size is '(entries * 64)' bytes. 

    Channel Source is used to filter out channels when processing interrupts
    and doorbell. Each time CPU wants to notify ISP about a new message it
    writes doorbell register. In the other hand, when ISP wants to notify CPU
    about a new message it triggers a hardware interrupt. 

    Channel Type is a mistery, but it seems to have a connection with cmd bit
    mask. 
    """

    ENTRY_LENGTH = 64

    def __init__(self, table, name, _type, source, number_of_entries, address):
        self.table = table
        self.tracer = table.tracer
        self.name = str(name, "ascii").rstrip('\x00')
        self.source = source
        self.type = _type
        self.number_of_entries = number_of_entries
        self.entry_size = self.ENTRY_LENGTH
        self.size = self.number_of_entries * self.entry_size
        self.address = address
        self.doorbell = 1 << source
        self.last_message_sent = None
        self.last_message_received = None
    
    def get_commands(self, direction):
        """ Gets a command from the channel"""
        commands = []
        message = self.get_message(direction)
        if message:
            command = self.__convert2command__(message, direction)
            if command:
                commands.append(command)
        return commands
    
    def get_message(self, direction):
        """ Gets a message from the channel and increase the associated index """
        last_message = self.last_message_sent if direction is ISPCommandDirection.TX else self.last_message_received
        index = (last_message.index + 1) if last_message else 0
        new_index, message = self.__read_message__(index)
        if message:
            if last_message and last_message == message:
                return

            last_message = message
            if direction is ISPCommandDirection.TX:
                self.last_message_sent = last_message
            else:
                self.last_message_received = last_message
            return message

    def dump(self):
        """ Dumps the content of the channel """
        s = f"[{self.name}] Channel messages: \n"
        for index in range(self.number_of_entries):
            _, message = self.__read_message__(index)
            s = s + "\t" + str(message) + "\n"
        self.table.log(s)
        
    def __convert2command__(self, message, direction):
        """ Converts a channel message into a command """
        if self.name == "TERMINAL":
            return ISPTerminalCommand(self, message, direction)
        elif self.name == "IO" or self.name == "DEBUG":
            return ISPIOCommand(self, message, direction)
        elif self.name == "SHAREDMALLOC":
            return ISPSharedMallocCommand(self, message, direction)
        elif self.name == "BUF_T2H":
            return ISPT2HBufferCommand(self, message, direction)
        elif self.name == "BUF_H2T":
            return ISPH2TBufferCommand(self, message, direction)
        elif self.name == "IO_T2H":
            return ISPT2HIOCommand(self, message, direction)
        else:
            return ISPCommand(self, message, direction)

    def __read_message__(self, index):
        message_data = self.__read_by_index__(index)
        message = ISPChannelMessage(index, message_data)
        if message.valid():
            index += 1
            if index >= self.number_of_entries:
                index = 0
            return index, message
        return 0, None

    def __read_by_index__(self, index):
        return self.table.ioread(self.address + (self.entry_size * index), self.entry_size)
    
    def __str__(self):
        return f"[CH - {str(self.name)}] (src = {self.source!s}, type = {self.type!s}, size = {self.number_of_entries!s}, iova = {hex(self.address)!s})"

class ISPTerminalChannel(ISPChannel):
    """ Special channel implementation for TERMINAL channel 
    Addresses of log buffers are removed from memory after MacOS processes them,
    hence we want to be a little bit ahead of MacOS and fetch all entries if
    possible.  
    """

    def __init__(self, table, name, _type, source, number_of_entries, address):
        super().__init__(table, name, _type, source, number_of_entries, address)
        self.last_index = 0

    def get_commands(self, direction):
        """ Gets a command from the channel"""
        commands = []
        for i in range(self.number_of_entries):
            index = (self.last_index + i) % self.number_of_entries
            _, message = self.__read_message__(index)
            if message and message.valid():
                command = self.__convert2command__(message, ISPCommandDirection.RX)
                if command:
                    commands.append(command)
            else:
                self.last_index = index
                break
        return commands

class ISPChannelMessage:
    """ A class used to represent IPC channel message or entry

    Each entry is 64 bytes, however only 24 bytes seems to be used. These 24
    bytes are divided in three qwords (8-bytes).
    """

    def __init__(self, index, data):
        self.index = index
        self.data = data
        idx = 0
        for arg in struct.unpack('<8q', self.data):
            setattr(self, f"arg{idx}", arg) 
            idx += 1
    
    def valid(self):
        """ Checks if a message seems to be valid

        So far I have observed that invalid messages or empty slots
        are usually marked as 0x1 (or 0x3 in case of TERMINAL msgs)
        """
        return (self.arg0 is not 0x1) and (self.arg0 is not 0x3)

    def __str__(self):
        s = "ISP Message: {"
        idx = 0
        for arg in struct.unpack('<8q', self.data):
            s = s + f"Arg{idx}: {hex(arg)}, " 
            idx = idx + 1
        s = s + "}"
        return s  
    
    def __eq__(self, other):
        return self.data == other.data  

class ISP_REVISION(Register32):
    REVISION = 15, 0

class ISP_PMU(Register32):
    STATUS = 7, 0
    OTHER = 63, 8

class ISP_PMU_SPECIAL_STATUS(Register32):
    STATUS = 7, 0
    OTHER = 63, 8

class ISPRegs(RegMap):
    ISP_CPU_CONTROL         = 0x0000, Register32
    ISP_CPU_STATUS          = 0x0004, Register32
    ISP_REVISION            = 0x1800000, ISP_REVISION
    ISP_POWER_UNKNOWN       = 0x20e0080, Register32
    ISP_IRQ_INTERRUPT       = 0x2104000, Register32
    ISP_IRQ_INTERRUPT_2     = 0x2104004, Register32
    ISP_SENSOR_REF_CLOCK    = irange(0x2104190, 3, 4), Register32
    ISP_GPR0                = 0x2104170, Register32
    ISP_GPR1                = 0x2104174, Register32
    ISP_GPR2                = 0x2104178, Register32
    ISP_GPR3                = 0x210417c, Register32
    ISP_GPR4                = 0x2104180, Register32
    ISP_GPR5                = 0x2104184, Register32
    ISP_GPR6                = 0x2104188, Register32
    ISP_GPR7                = 0x210418c, Register32

    ISP_DOORBELL_RING0      = 0x21043f0, Register32
    ISP_IRQ_INTERRUPT_ACK   = 0x21043fc, Register32

    ISP_SMBUS_REG_MTXFIFO   = irange(0x2110000, 4, 0x1000), Register32
    ISP_SMBUS_REG_MRXFIFO   = irange(0x2110004, 4, 0x1000), Register32
    ISP_SMBUS_REG_UNK_1     = irange(0x2110008, 4, 0x1000), Register32
    ISP_SMBUS_REG_UNK_2     = irange(0x211000c, 4, 0x1000), Register32
    ISP_SMBUS_REG_UNK_3     = irange(0x2110010, 4, 0x1000), Register32
    ISP_SMBUS_REG_SMSTA     = irange(0x2110014, 4, 0x1000), Register32
    ISP_SMBUS_REG_UNK_4     = irange(0x2110018, 4, 0x1000), Register32
    ISP_SMBUS_REG_CTL       = irange(0x211001c, 4, 0x1000), Register32
    ISP_SMBUS_REG_UNK_5     = irange(0x2110020, 4, 0x1000), Register32
    ISP_SMBUS_REG_UNK_6     = irange(0x2110024, 4, 0x1000), Register32
    ISP_SMBUS_REG_REV       = irange(0x2110028, 4, 0x1000), Register32
    ISP_SMBUS_REG_UNK_7     = irange(0x211002c, 4, 0x1000), Register32
    ISP_SMBUS_REG_UNK_8     = irange(0x2110030, 4, 0x1000), Register32
    ISP_SMBUS_REG_UNK_9     = irange(0x2110034, 4, 0x1000), Register32
    ISP_SMBUS_REG_UNK_A     = irange(0x2110038, 4, 0x1000), Register32
    ISP_SMBUS_REG_UNK_B     = irange(0x211003c, 4, 0x1000), Register32

    ISP_DPE_REG_UNK1        = 0x2504000, Register32
    ISP_DPE_REG_UNK2        = 0x2508000, Register32

    ISP_CPU_BUFFER          = 0x1050000, Register32

    ISP_SPMI0_REGISTER_BASE = 0x2900000, Register32
    ISP_SPMI1_REGISTER_BASE = 0x2920000, Register32
    ISP_SPMI2_REGISTER_BASE = 0x2940000, Register32

class PSReg(RegMap):
    PMU_UNKNOWN0           = 0x4000, ISP_PMU
    PMU_UNKNOWN1           = 0x4008, ISP_PMU
    PMU_UNKNOWN2           = 0x4010, ISP_PMU
    PMU_UNKNOWN3           = 0x4018, ISP_PMU
    PMU_UNKNOWN4           = 0x4020, ISP_PMU
    PMU_UNKNOWN5           = 0x4028, ISP_PMU
    PMU_UNKNOWN6           = 0x4030, ISP_PMU
    PMU_UNKNOWN7           = 0x4038, ISP_PMU
    PMU_UNKNOWN8           = 0x4040, ISP_PMU
    PMU_UNKNOWN9           = 0x4048, ISP_PMU
    PMU_UNKNOWNA           = 0x4050, ISP_PMU
    PMU_UNKNOWNB           = 0x4058, ISP_PMU
    PMU_SPECIAL_STATUS     = 0x4060, ISP_PMU_SPECIAL_STATUS
    CLOCK_TICK_LOW         = 0x34004, Register32
    CLOCK_TICK_HIGH        = 0x34008, Register32
    RT_BANDWIDTH_SCRATCH1  = 0x38014, Register32
    RT_BANDWIDTH_SCRATCH2  = 0x38018, Register32

class SPMIReg(RegMap):
    SPMI_UNKNOWN0           = 0x28, Register32
    SPMI_UNKNOWN1           = 0x40, Register32
    SPMI_UNKNOWN2           = 0x90, Register32
    SPMI_UNKNOWN3           = 0x80a0, Register32
    SPMI_UNKNOWN4           = 0x80a4, Register32