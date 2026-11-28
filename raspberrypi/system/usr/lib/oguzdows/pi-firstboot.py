#!/usr/bin/env python3
"""Kalıcı Pi imajında ortak parola bırakmadan Türkçe yerel hesap oluşturur."""
from __future__ import annotations

import fcntl
import getpass
import grp
import json
import os
import pwd
import re
import stat
import subprocess
from pathlib import Path

STATE = Path("/var/lib/oguzdows")
PROVISION = Path("/boot/firmware/oguzdows-userconf.txt")
# Resmî pi-gen stage2 üyelikleri; yalnızca zaten var olan gruplar eklenir.
GROUPS = ("sudo", "adm", "dialout", "cdrom", "audio", "users", "video", "games", "plugdev", "input", "gpio", "spi", "i2c", "netdev", "render")
USERNAME = re.compile(r"[a-z][a-z0-9_-]{0,30}")
SHA512 = re.compile(r"\$6\$(?:rounds=[0-9]{4,9}\$)?[./0-9A-Za-z]{1,16}\$[./0-9A-Za-z]{86}")
YESCRYPT = re.compile(r"\$y\$[./0-9A-Za-z]{1,16}\$[./0-9A-Za-z]{1,86}\$[./0-9A-Za-z]{20,128}")


def valid_username(name: str) -> bool:
    return bool(USERNAME.fullmatch(name)) and name not in ("root", "oguz-build", "nobody")


def valid_password(password: str) -> bool:
    return len(password) >= 10 and len(password) <= 1024 and not any(char in password for char in "\x00\r\n:")


def read_provision(path: Path = PROVISION) -> tuple[str, str] | None:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
            raise ValueError("Hazır hesap dosyası normal, en fazla 4 KiB bir dosya olmalı.")
        line = stream.read(4097).decode("utf-8").strip()
    if "\n" in line or "\r" in line or line.count(":") != 1:
        raise ValueError("Hazır hesap dosyasında tek kullanıcı:parola-özeti satırı olmalı.")
    name, hashed = line.split(":")
    if not valid_username(name) or not (SHA512.fullmatch(hashed) or YESCRYPT.fullmatch(hashed)):
        raise ValueError("Kullanıcı adı veya SHA-512 / yescrypt parola özeti geçersiz.")
    return name, hashed


def write_state(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    temporary = path.with_name(path.name + ".new")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def run(command: list[str], secret: str | None = None) -> None:
    try:
        subprocess.run(command, input=secret, text=True, capture_output=True, check=True,
                       env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "tr_TR.UTF-8"}, timeout=120)
    except (subprocess.SubprocessError, OSError) as error:
        # Parola/özet veya komut stderr'i journal'a taşınmaz.
        raise RuntimeError("Hesap işlemi tamamlanamadı; yeniden deneyin. Ayrıntılar gizlilik için yazdırılmadı.") from error


def lookup(name: str):
    try:
        return pwd.getpwnam(name)
    except KeyError:
        return None


def complete(name: str, password: str, hashed: bool, state: Path = STATE) -> None:
    if not valid_username(name):
        raise ValueError("Geçersiz kullanıcı adı.")
    if hashed:
        if not (SHA512.fullmatch(password) or YESCRYPT.fullmatch(password)):
            raise ValueError("Geçersiz parola özeti.")
    elif not valid_password(password):
        raise ValueError("Parola en az 10 karakter olmalı; satır sonu ve iki nokta içeremez.")
    pending_file = state / "firstboot.pending.json"
    pending = json.loads(pending_file.read_text()) if pending_file.exists() else {}
    account = lookup(name)
    if pending and pending.get("username") != name:
        raise ValueError("Yarım kalan hesabı aynı adla tamamlayın: " + str(pending.get("username", "")))
    if account and (pending.get("username") != name or account.pw_uid != 1000 or account.pw_dir != "/home/" + name):
        raise ValueError("Bu kullanıcı adı zaten kullanılıyor.")
    groups = []
    for group in GROUPS:
        try:
            grp.getgrnam(group)
            groups.append(group)
        except KeyError:
            continue
    if "sudo" not in groups:
        raise RuntimeError("Yönetici grubu bulunamadı; imajı doğrulayın.")
    if not account:
        try:
            pwd.getpwuid(1000)
        except KeyError:
            pass
        else:
            raise ValueError("1000 numaralı kullanıcı zaten var; otomatik olarak değiştirilmedi.")
    # Kesintide isim korunur, parola asla diske yazılmaz. Hesap parola verilene kadar kilitlidir.
    write_state(pending_file, {"username": name, "uid": 1000})
    if not account:
        run(["/usr/sbin/useradd", "--create-home", "--user-group", "--uid", "1000",
             "--shell", "/bin/bash", "--comment", "OğuzDows Kullanıcısı", name])
    run(["/usr/sbin/usermod", "--append", "--groups", ",".join(groups), name])
    run(["/usr/sbin/usermod", "--lock", "root"])
    run(["/usr/sbin/chpasswd", *(["--encrypted"] if hashed else [])], secret=name + ":" + password + "\n")
    # Parola ve üyelikler kalıcı olmadan 'tamamlandı' işareti yazma.
    os.sync()
    write_state(state / "firstboot.done", {"username": name, "version": 1})
    pending_file.unlink(missing_ok=True)


def cleanup_provision(path: Path = PROVISION) -> None:
    # FAT üzerinde güvenli fiziksel silme garantisi yok; yalnızca dosya kaldırılır.
    path.unlink(missing_ok=True)
    os.sync()


def main() -> int:
    if os.geteuid() != 0 or not Path("/etc/oguzdows/pi-image.json").is_file():
        print("Bu işlem yalnızca OğuzDows Pi ilk açılış servisi içindir.")
        return 1
    fd = os.open("/run/lock/oguzdows-firstboot.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (STATE / "firstboot.done").is_file():
            cleanup_provision()
            return 0
        subprocess.run(["/usr/bin/plymouth", "quit"], check=False, capture_output=True)
        print("\nOğuzDows · Akıncı\nRaspberry Pi ilk açılış kurulumu\n")
        print("Ortak kullanıcı veya parola yok. Bir yönetici hesabı oluşturacağız.\nParolanız yazılırken görünmez; root hesabı kilitli ve SSH kapalıdır.\n")
        try:
            provision = read_provision()
            if provision:
                complete(*provision, hashed=True)
                cleanup_provision()
                print("Hesap oluşturuldu. OğuzDows giriş ekranı açılıyor.")
                return 0
        except (OSError, ValueError, RuntimeError) as error:
            print("Hazır hesap uygulanamadı: " + str(error))
        pending_file = STATE / "firstboot.pending.json"
        while True:
            try:
                if pending_file.exists():
                    name = json.loads(pending_file.read_text())["username"]
                    print("Yarım kalan hesap tamamlanacak: " + name)
                else:
                    name = input("Kullanıcı adı (küçük Latin harfleri, rakam, - veya _): ").strip()
                if not valid_username(name):
                    print("Ad bir harfle başlamalı ve en fazla 31 karakter olmalı.")
                    continue
                if lookup(name) and not pending_file.exists():
                    print("Bu ad kullanılıyor; başka bir ad seçin.")
                    continue
                password = getpass.getpass("En az 10 karakterli parola: ")
                if not valid_password(password):
                    print("Parola en az 10 karakter olmalı; satır sonu ve iki nokta içeremez.")
                    continue
                if password != getpass.getpass("Parola tekrar: "):
                    print("Parolalar eşleşmedi.")
                    continue
                complete(name, password, hashed=False)
                cleanup_provision()
                print("\nKurulum tamamlandı. Parolanızla giriş yapabilirsiniz.")
                return 0
            except (ValueError, RuntimeError) as error:
                print(str(error))
            except (EOFError, KeyboardInterrupt):
                print("\nKurulum tamamlanmadı. Hesap ekranı yeniden açılacak.")
                return 1


if __name__ == "__main__":
    raise SystemExit(main())
