import hashlib
import struct
import zlib
from pathlib import Path


def png_chunk(kind, data):
    payload = kind + data
    return struct.pack('>I', len(data)) + payload + struct.pack('>I', zlib.crc32(payload))


def icc_profile():
    tag_text = b'Antelope test profile '
    tag_text += b''.join(
        hashlib.sha256(index.to_bytes(4, 'big')).hexdigest().encode('ascii')
        for index in range(4)
    ) + b'\0'
    tag_data = b'text' + bytes(4) + tag_text
    padding = (-(144 + len(tag_data))) % 4
    profile_length = 144 + len(tag_data) + padding

    profile = bytearray(128)
    struct.pack_into('>I', profile, 0, profile_length)
    profile[4:8] = b'ANTL'
    struct.pack_into('>I', profile, 8, 0x04300000)
    profile[12:16] = b'mntr'
    profile[16:20] = b'RGB '
    profile[20:24] = b'XYZ '
    struct.pack_into('>6H', profile, 24, 2026, 1, 1, 0, 0, 0)
    profile[36:40] = b'acsp'
    profile[40:44] = b'APPL'
    profile[68:80] = bytes.fromhex('0000f6d6000100000000d32d')
    profile[80:84] = b'ANTL'
    profile += struct.pack('>I', 1)
    profile += b'cprt' + struct.pack('>II', 144, len(tag_data))
    profile += tag_data + bytes(padding)
    return bytes(profile)


def main():
    output = Path(__file__).parent / 'assets' / 'icc-profile.png'
    output.parent.mkdir(parents=True, exist_ok=True)

    header = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    iccp = b'Antelope test profile\0\0' + zlib.compress(icc_profile())
    image = (
        b'\x89PNG\r\n\x1a\n'
        + png_chunk(b'IHDR', header)
        + png_chunk(b'iCCP', iccp)
        + png_chunk(b'IDAT', zlib.compress(b'\0\x80\x40\x20'))
        + png_chunk(b'IEND', b'')
    )
    output.write_bytes(image)
    print(f'Wrote {output}')


if __name__ == '__main__':
    main()