def strip_header(data: bytes) -> bytes:
    if data[0:1] != b"#":
        raise ValueError("Unexpected data format")
    num_digits = int(data[1:2])  # slice the first byte       eg #32500
    header_length = 2 + num_digits
    num_bytes = int(data[2 : 2 + num_digits])
    return data[header_length : header_length + num_bytes]
