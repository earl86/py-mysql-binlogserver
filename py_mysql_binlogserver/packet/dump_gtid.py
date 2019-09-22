#!/usr/bin/env python
# coding=utf-8

import struct
from io import BytesIO

from py_mysql_binlogserver.constants.COMMAND import COM_BINLOG_DUMP_GTID
from py_mysql_binlogserver.protocol.gtid import GtidSet, Gtid
from py_mysql_binlogserver.protocol.packet import Packet, dump_my_packet
from py_mysql_binlogserver.protocol.proto import int2byte


class DumpGtid(Packet):
    __slots__ = ('server_id', 'auto_position') + Packet.__slots__

    def __init__(self, server_id, auto_position):
        super(DumpGtid, self).__init__()
        self.server_id = server_id
        self.auto_position = auto_position

    def getPayload(self):
        # Format for mysql packet master_auto_position
        #
        # All fields are little endian
        # All fields are unsigned

        # Packet length   uint   4bytes
        # Packet type     byte   1byte   == 0x1e
        # Binlog flags    ushort 2bytes  == 0 (for retrocompatibilty)
        # Server id       uint   4bytes
        # binlognamesize  uint   4bytes
        # binlogname      str    Nbytes  N = binlognamesize
        #                                Zeroified
        # binlog position uint   4bytes  == 4
        # payload_size    uint   4bytes

        # What come next, is the payload, where the slave gtid_executed
        # is sent to the master
        # n_sid           ulong  8bytes  == which size is the gtid_set
        # | sid           uuid   16bytes UUID as a binary
        # | n_intervals   ulong  8bytes  == how many intervals are sent
        # |                                 for this gtid
        # | | start       ulong  8bytes  Start position of this interval
        # | | stop        ulong  8bytes  Stop position of this interval

        # A gtid set looks like:
        #   19d69c1e-ae97-4b8c-a1ef-9e12ba966457:1-3:8-10,
        #   1c2aad49-ae92-409a-b4df-d05a03e4702e:42-47:80-100:130-140
        #
        # In this particular gtid set,
        # 19d69c1e-ae97-4b8c-a1ef-9e12ba966457:1-3:8-10
        # is the first member of the set, it is called a gtid.
        # In this gtid, 19d69c1e-ae97-4b8c-a1ef-9e12ba966457 is the sid
        # and have two intervals, 1-3 and 8-10, 1 is the start position of
        # the first interval 3 is the stop position of the first interval.

        gtid_set = GtidSet(self.auto_position)
        encoded_data_size = gtid_set.encoded_length

        header_size = (2 +  # binlog_flags
                       4 +  # server_id
                       4 +  # binlog_name_info_size
                       4 +  # empty binlog name
                       8 +  # binlog_pos_info_size
                       4)  # encoded_data_size

        prelude = b'' + struct.pack('<i', header_size + encoded_data_size) \
                  + int2byte(COM_BINLOG_DUMP_GTID)

        flags = 0
        # if not self.__blocking:
        #     flags |= 0x01  # BINLOG_DUMP_NON_BLOCK
        flags |= 0x04  # BINLOG_THROUGH_GTID

        # binlog_flags (2 bytes)
        # see:
        #  https://dev.mysql.com/doc/internals/en/com-binlog-dump-gtid.html
        prelude += struct.pack('<H', flags)

        # server_id (4 bytes)
        prelude += struct.pack('<I', self.server_id)
        # binlog_name_info_size (4 bytes)
        prelude += struct.pack('<I', 3)
        # empty_binlog_name (4 bytes)
        prelude += b'\0\0\0'
        # binlog_pos_info (8 bytes)
        prelude += struct.pack('<Q', 4)

        # encoded_data_size (4 bytes)
        prelude += struct.pack('<I', gtid_set.encoded_length)
        # encoded_data
        prelude += gtid_set.encoded()

        return prelude

    @staticmethod
    def loadFromPacket(packet):
        return None


if __name__ == "__main__":
    packet = bytes.fromhex(
        "6f0000001e000075723200000000000400000000000000580000000200000000000000ba66414cd10d11e9b4b00800275ae9e7010000000000000001000000000000001700000000000000f0ea18e03cff11e994880800275ae9e7010000000000000001000000000000002000000000000000")

    print("length 1:", len(packet))
    dump_my_packet(packet)

    header_size = (2 +  # binlog_flags
                   4 +  # server_id
                   4 +  # binlog_name_info_size
                   4 +  # empty binlog name
                   8    # binlog_pos_info_size
                   )

    off = 4 + 1
    # header = struct.unpack('<iHIIQI', packet[off:header_size+off])
    # print(header)

    # payload = packet[27:]
    payload = packet[off + header_size:]
    dump_my_packet(payload)
    gtid_set = GtidSet.decode(BytesIO(payload))
    print(gtid_set)

    set_repr = 'ba66414c-d10d-11e9-b4b0-0800275ae9e7:1-22,' \
               'f0ea18e0-3cff-11e9-9488-0800275ae9e7:1-31'

    myset = GtidSet(set_repr)
    payload = myset.encode()
    print("length 2:", len(payload))
    dump_my_packet(payload)
