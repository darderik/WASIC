def strip_header(data: bytes) -> bytes:
    if data[0:1] != b"#":
        raise ValueError("Formato non riconosciuto")
    num_digits = int(data[1:2])
    header_length = 2 + num_digits
    num_bytes = int(data[2 : 2 + num_digits])
    return data[header_length : header_length + num_bytes]
