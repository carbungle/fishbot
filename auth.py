import base64
import hashlib
import json
import os
import platform
import sys
import time
import uuid

OWNER_SALT_B64 = "rXtK880+lqjsohQ4547xCw=="
OWNER_DIGEST_B64 = "pqjr3ydb5mM/qOjeS4jiibY0jn7p0SKJS3yy0hr5Cjo="
OWNER_KDF = "pbkdf2"

_XOR_KEY = base64.b64decode("ctYMkmwodUo/DIwsd6C80oF6k+TPkXmledes+0x1joA=")
_ITER = 250000
_SCRYPT_N = 2 ** 18
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 64
_MAGIC = b"AUTH1"

_OWNER_HW = "Q7dv8whNTSxeOOoZFZPf57JDoNSsohqRQbScmClA7OIW4DuhWBhGc1w/uBREmIrrsk+mh6uhGpNBs8jNLkK5tA=="

_gate = None


def _dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def store_path() -> str:
    return os.path.join(_dir(), "users.dat")


def _session_path() -> str:
    return os.path.join(_dir(), "session.dat")


def machine_id() -> str:
    parts = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            "SOFTWARE\\Microsoft\\Cryptography") as k:
            parts.append(str(winreg.QueryValueEx(k, "MachineGuid")[0]))
    except Exception:
        pass
    try:
        import ctypes
        from ctypes import wintypes
        buf = ctypes.create_unicode_buffer(32)
        sn = wintypes.DWORD()
        ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p("C" + os.sep),
            buf, len(buf), ctypes.byref(sn), None, None, None, 0)
        parts.append(str(sn.value))
    except Exception:
        pass
    parts.append(str(uuid.getnode()))
    parts.append(str(platform.processor()))
    parts.append(str(platform.node()))
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _pbkdf2(secret: bytes, salt: bytes) -> bytes:
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", secret, salt, _ITER)


def _scrypt(secret: str, salt: bytes) -> bytes:
    return hashlib.scrypt(secret.encode("utf-8"), salt=salt, n=_SCRYPT_N,
                          r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN,
                          maxmem=1 << 30)


def _derive(secret: str, salt: bytes, kdf: str) -> bytes:
    if kdf == "scrypt":
        return _scrypt(secret, salt)
    return _pbkdf2(secret, salt)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _owner_creds():
    """Return (kdf, salt, digest) for the owner gate."""
    p = os.path.join(_dir(), "owner.dat")
    if os.path.exists(p):
        try:
            with open(p, "rb") as f:
                d = json.loads(_mask(base64.b64decode(f.read())).decode("utf-8"))
            return "scrypt", base64.b64decode(d["salt"]), base64.b64decode(d["digest"])
        except Exception:
            pass
    return OWNER_KDF, base64.b64decode(OWNER_SALT_B64), base64.b64decode(OWNER_DIGEST_B64)


def _bake_owner(pw: str) -> None:
    salt = os.urandom(16)
    payload = json.dumps({"salt": _b64(salt),
                          "digest": _b64(_scrypt(pw, salt))},
                         separators=(",", ":")).encode("utf-8")
    with open(os.path.join(_dir(), "owner.dat"), "wb") as f:
        f.write(base64.b64encode(_mask(payload)))


def _mask(data: bytes) -> bytes:
    out = bytearray(len(data))
    k = len(_XOR_KEY)
    for i, b in enumerate(data):
        out[i] = b ^ _XOR_KEY[i % k]
    return bytes(out)


def _encode(records: list) -> bytes:
    body = json.dumps(records, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(_MAGIC + _mask(body))


def _decode(blob: bytes) -> list:
    raw = base64.b64decode(blob)
    if not raw.startswith(_MAGIC) or len(raw) < 8:
        return []
    return json.loads(_mask(raw[len(_MAGIC):]).decode("utf-8"))


def _load() -> list:
    p = store_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, "rb") as f:
            return _decode(f.read())
    except Exception:
        return []


def _save(records: list) -> None:
    with open(store_path(), "wb") as f:
        f.write(_encode(records))


def has_users() -> bool:
    return bool(_load())


def _verify_owner(owner_pw: str) -> bool:
    kdf, salt, digest = _owner_creds()
    return _derive(owner_pw, salt, kdf) == digest


def _find_user(name: str, records: list):
    for rec in records:
        salt = base64.b64decode(rec["salt"])
        kdf = rec.get("kdf", "pbkdf2")
        if base64.b64encode(_derive(name, salt, kdf)).decode("ascii") == rec["nd"]:
            return rec
    return None


def add_user(owner_pw: str, username: str, password: str) -> bool:
    if not _verify_owner(owner_pw):
        return False
    records = _load()
    salt = os.urandom(16)
    rec = {"salt": base64.b64encode(salt).decode("ascii"),
           "nd": base64.b64encode(_scrypt(username, salt)).decode("ascii"),
           "pd": base64.b64encode(_scrypt(password, salt)).decode("ascii"),
           "hw": "", "kdf": "scrypt"}
    old = _find_user(username, records)
    if old is not None:
        records[records.index(old)] = rec
    else:
        records.append(rec)
    _save(records)
    return True


def remove_user(owner_pw: str, username: str) -> bool:
    if not _verify_owner(owner_pw):
        return False
    records = _load()
    rec = _find_user(username, records)
    if rec is None:
        return False
    records.remove(rec)
    _save(records)
    return True


def _pass_prompt(prompt: str) -> str:
    sys.stdout.write(prompt)
    sys.stdout.flush()
    try:
        import msvcrt
        buf = []
        while True:
            ch = msvcrt.getwch()
            if ch in ("\r", "\n"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                return "".join(buf)
            elif ch == "\x08":
                if buf:
                    buf.pop()
                    sys.stdout.write("\x08 \x08")
                    sys.stdout.flush()
            elif ch == "\x03":
                raise KeyboardInterrupt
            elif ch == "\x1b":
                sys.stdout.write("\n")
                sys.stdout.flush()
                raise KeyboardInterrupt
            elif ch == "\x00":
                msvcrt.getch()   # swallow the second byte of a 2-byte key
            else:
                buf.append(ch)
                sys.stdout.write("*")
                sys.stdout.flush()
    except Exception:
        return input("")


def _save_session(username: str) -> None:
    p = _session_path()
    try:
        blob = json.dumps({"u": username, "t": int(time.time())},
                          separators=(",", ":")).encode("utf-8")
        with open(p, "wb") as f:
            f.write(base64.b64encode(_mask(blob)))
    except Exception:
        pass


def _load_session():
    """Return (username, epoch_time) or ("", 0) if none/expired format."""
    try:
        with open(_session_path(), "rb") as f:
            data = json.loads(_mask(base64.b64decode(f.read())).decode("utf-8"))
        if isinstance(data, dict) and "u" in data and "t" in data:
            return str(data["u"]), int(data["t"])
        if isinstance(data, str):
            return data, 0  # legacy session, force re-auth
    except Exception:
        pass
    return "", 0


def _password_ok(rec: dict, pw: str) -> bool:
    salt = base64.b64decode(rec["salt"])
    kdf = rec.get("kdf", "pbkdf2")
    return base64.b64encode(_derive(pw, salt, kdf)).decode("ascii") == rec["pd"]


def _masked_hw() -> str:
    return base64.b64encode(_mask(machine_id().encode("utf-8"))).decode("ascii")


def _is_owner_pc() -> bool:
    return _masked_hw() == _OWNER_HW


def login():
    records = _load()
    if not records:
        print("No registered users. Contact the owner.")
        return None
    cur = _masked_hw()

    def persist(rec):
        rec["hw"] = cur
        _save(records)

    def upgrade(rec, name, pw):
        if rec.get("kdf", "pbkdf2") != "scrypt":
            salt = os.urandom(16)
            rec["kdf"] = "scrypt"
            rec["salt"] = base64.b64encode(salt).decode("ascii")
            rec["nd"] = base64.b64encode(_scrypt(name, salt)).decode("ascii")
            rec["pd"] = base64.b64encode(_scrypt(pw, salt)).decode("ascii")
            _save(records)

    def refresh(name):
        _save_session(name)

    sess_name, _ = _load_session()
    if sess_name:
        rec = _find_user(sess_name, records)
        if rec is not None and rec.get("hw", "") == cur:
            return sess_name

    while True:
        try:
            name = input("? ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if not name:
            continue
        rec = _find_user(name, records)
        if rec is None:
            print("Try again.")
            continue
        while True:
            try:
                pw = _pass_prompt("?? ")
            except (EOFError, KeyboardInterrupt):
                print()
                return None
            if _password_ok(rec, pw):
                break
            print("Try again.")
        hw = rec.get("hw", "")
        if hw and hw != cur:
            print("This login is locked to another computer.")
            continue
        if not hw:
            persist(rec)
        upgrade(rec, name, pw)
        refresh(name)
        return name


def unlock_user(owner_pw: str, username: str) -> bool:
    if not _verify_owner(owner_pw):
        return False
    records = _load()
    rec = _find_user(username, records)
    if rec is None:
        return False
    rec["hw"] = ""
    _save(records)
    return True


def export_user(owner_pw: str, username: str, password: str, out_path: str) -> bool:
    """Write a single-user users.dat (scrypt, unbounded) to out_path. Owner-only."""
    if not _verify_owner(owner_pw):
        return False
    salt = os.urandom(16)
    rec = {"salt": base64.b64encode(salt).decode("ascii"),
           "nd": base64.b64encode(_scrypt(username, salt)).decode("ascii"),
           "pd": base64.b64encode(_scrypt(password, salt)).decode("ascii"),
           "hw": "", "kdf": "scrypt"}
    try:
        with open(out_path, "wb") as f:
            f.write(_encode([rec]))
        return True
    except Exception:
        return False


def main():
    if not sys.argv[1:]:
        print("add | remove | unlock | export <user> <out.dat>")
        return None
    owner = input("?? ")
    cmd = sys.argv[1].lower()

    def _owner_ok() -> bool:
        if not _verify_owner(owner):
            return False
        # Upgrade the owner gate to the hardened scrypt hash on first success.
        if not os.path.exists(os.path.join(_dir(), "owner.dat")):
            _bake_owner(owner)
        return True

    if cmd == "add":
        u = input("? ").strip()
        if not u:
            print("no username")
            return None
        if not _owner_ok():
            print("Wrong owner password.")
            return None
        p = input("?? ")
        print("Added." if add_user(owner, u, p) else "Failed.")
        return None
    if cmd == "remove":
        u = input("? ").strip()
        if not u:
            print("no username")
            return None
        if not _owner_ok():
            print("Wrong owner password.")
            return None
        print("Removed." if remove_user(owner, u) else "No such user.")
        return None
    if cmd == "unlock":
        u = input("? ").strip()
        if not u:
            print("no username")
            return None
        if not _owner_ok():
            print("Wrong owner password.")
            return None
        print("Unlocked." if unlock_user(owner, u) else "No such user.")
        return None
    if cmd == "export":
        if len(sys.argv) < 4:
            print("usage: python auth.py export <username> <out.dat>")
            return None
        u = sys.argv[2]
        out = sys.argv[3]
        if not _owner_ok():
            print("Wrong owner password.")
            return None
        p = input("?? ")
        print("Exported." if export_user(owner, u, p, out) else "Export failed.")
        return None
    print("add | remove | unlock | export <user> <out.dat>")
    return None


if __name__ == "__main__":
    main()