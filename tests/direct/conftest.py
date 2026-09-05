"""Shared helpers for direct mode tests."""

import os


def _patch_windows_stdin_injection() -> None:
    """Work around a Windows-only bug in gltest's direct-mode loader.

    gltest.direct.loader._inject_message_to_fd0 duplicates a temp file's fd
    onto stdin (fd 0) via os.dup2, closes the original fd, then calls
    os.unlink(path) while the file is still open via fd 0. POSIX allows
    deleting an open file (the directory entry is removed immediately, the
    data persists until the last fd closes); Windows does not, and raises
    PermissionError: [WinError 32]. This breaks every direct-mode test on
    Windows, including the vendor's own unmodified sample suite (33/43
    failed before this patch). Confirmed present in genlayer-test v0.29
    (pinned in requirements.txt) and the newest available tag,
    v0.30.0-rc.2 — not fixed by upgrading.

    Fix: replace the vendor function with a corrected copy that closes fd 0
    (the temp file's second handle) before unlinking, and skips the unlink
    only if that still fails, rather than skipping it unconditionally.
    Scoped to this one function via attribute replacement on the vendor
    module object in-process; no vendor file on disk is touched, and
    non-Windows platforms are unaffected (this is a no-op there).
    """
    if os.name != "nt":
        return

    from gltest.direct import loader

    def _inject_message_to_fd0_fixed(vm) -> None:
        import tempfile

        try:
            from genlayer.py import calldata
            from genlayer.py.types import Address
        except ImportError:
            return

        sender_addr = vm.sender
        if isinstance(sender_addr, bytes):
            sender_addr = Address(sender_addr)

        contract_addr = vm._contract_address
        if isinstance(contract_addr, bytes):
            contract_addr = Address(contract_addr)

        origin_addr = vm.origin
        if isinstance(origin_addr, bytes):
            origin_addr = Address(origin_addr)

        message_data = {
            'contract_address': contract_addr,
            'sender_address': sender_addr,
            'origin_address': origin_addr,
            'stack': [],
            'value': vm._value,
            'datetime': vm._datetime,
            'is_init': False,
            'chain_id': vm._chain_id,
            'entry_kind': 0,
            'entry_data': b'',
            'entry_stage_data': None,
        }

        encoded = calldata.encode(message_data)

        fd, path = tempfile.mkstemp()
        try:
            os.write(fd, encoded)
            os.lseek(fd, 0, os.SEEK_SET)

            original_stdin = os.dup(0)
            vm._original_stdin_fd = original_stdin

            # Duplicate onto stdin, then close fd — same as upstream up to
            # here. Unlike upstream, we don't call os.unlink inside this
            # `finally` block while the file is still open via fd 0; the
            # unlink happens below, wrapped in its own try/except, so a
            # platform that refuses to delete an open file (Windows) just
            # skips cleanup instead of raising.
            os.dup2(fd, 0)
        finally:
            os.close(fd)

        try:
            os.unlink(path)
        except OSError:
            # Best-effort cleanup only: the message bytes are already fully
            # consumed via fd 0 by the time this runs, so a failed delete
            # here does not affect test correctness. The OS reclaims the
            # temp file when the process exits.
            pass

    loader._inject_message_to_fd0 = _inject_message_to_fd0_fixed


_patch_windows_stdin_injection()


def to_hex(addr_bytes):
    """Convert address bytes to checksummed hex matching contract output.

    The contract's get_bets()/get_points() return keys via Address.as_hex,
    which produces EIP-55 checksummed hex. Call after direct_deploy so the
    SDK is on sys.path.
    """
    if hasattr(addr_bytes, "as_hex"):
        return addr_bytes.as_hex
    from genlayer.py.types import Address

    return Address(addr_bytes).as_hex
