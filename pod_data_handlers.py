from io import BytesIO
import struct

def unsigned_short_handler(stream: BytesIO, components):
    result = []
    for _ in range(components):
        short = struct.unpack('<H', stream.read(2))[0]
        result.append(short)
    return result[0] if components == 1 else result

def singed_32bit_float_handler(stream: BytesIO, components):
    result = []
    for _ in range(components):
        bytes_read = stream.read(4)
        value = struct.unpack('<f', bytes_read)[0]
        result.append(value)
    return result[0] if components == 1 else result

def argb32bit_float_handler(stream: BytesIO, components):
    result = []
    for _ in range(components):
        a = struct.unpack('<f', stream.read(4))[0]
        r = struct.unpack('<f', stream.read(4))[0]
        g = struct.unpack('<f', stream.read(4))[0]
        b = struct.unpack('<f', stream.read(4))[0]
        result.append((r, g, b, a))  # NOTE: reordered to RGBA
    return result[0] if components == 1 else result

def unsigned_32bit_integer_handler(stream: BytesIO, components):
    result = []
    for _ in range(components):
        uint = struct.unpack('<I', stream.read(4))[0]
        result.append(uint)
    return result[0] if components == 1 else result

DATA_HANDLERS = {
    1: singed_32bit_float_handler,
    2: unsigned_32bit_integer_handler,
    3: unsigned_short_handler,
    5: argb32bit_float_handler,
}

DATA_HANDLERS_SIZE = {
    1: 4,
    2: 4,
    3: 2,
    5: 16,
}