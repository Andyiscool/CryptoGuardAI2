import hmac
import hashlib
import os

key_hex = os.getenv("HMAC_KEY")
print(f"HMAC_KEY (hex): {key_hex}")
if not key_hex:
    raise RuntimeError("HMAC_KEY environment variable is not set.")
HMAC_KEY = bytes.fromhex(os.getenv("HMAC_KEY"))
def generate_hmac(message_bytes):
    """Generate HMAC for the given message bytes using the predefined key."""
    return hmac.new(HMAC_KEY, message_bytes, hashlib.sha256).hexdigest()
def verify_hmac(message_bytes, received_hmac):
    """Verify the HMAC for the given message bytes against the received HMAC."""
    expected_hmac = generate_hmac(message_bytes)
    return hmac.compare_digest(expected_hmac, received_hmac)