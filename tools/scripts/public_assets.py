"""Exact reviewed binary branding assets; other binaries remain prohibited."""

import hashlib

APPROVED_BINARY_ASSETS = {
    "assets/microsoft/color.png": "d207a733912b1dcc6f9020ea9173540f716f0c3821f329291f70e08a98db510b",
    "assets/microsoft/outline.png": "539e36b43ee52e2b407f6783852661d9909532d015e1c764290aee0aa851f2ce",
}


def reviewed_binary(name, content):
    """Allow only the reviewed bytes at their exact repository paths."""
    if name not in APPROVED_BINARY_ASSETS:
        return False
    if hashlib.sha256(content).hexdigest() != APPROVED_BINARY_ASSETS[name]:
        raise ValueError("Binary branding asset differs from its reviewed checksum")
    return True
