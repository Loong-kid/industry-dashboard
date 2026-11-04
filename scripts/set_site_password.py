# -*- coding: utf-8 -*-
"""사이트 접속 비밀번호를 정한다. 원문은 어디에도 저장하지 않고 해시만 site-gate-config.js에 쓴다.

    python scripts/set_site_password.py         # 입력창에서 비밀번호를 두 번 입력
    python scripts/set_site_password.py --off   # 비밀번호 끄기

해시는 공개 저장소에 올라가므로, 다른 곳에서 쓰지 않는 비밀번호를 정한다.
"""
import argparse
import getpass
import hashlib
import json
import secrets
import sys
import unicodedata
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "assets" / "site-gate-config.js"
ITERATIONS = 310_000
MIN_LENGTH = 8
HEADER = "// scripts/set_site_password.py가 만드는 파일. hash가 null이면 비밀번호 없이 열린다.\n"


def derive(password, salt_hex, iterations=ITERATIONS):
    text = unicodedata.normalize("NFC", password).encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", text, bytes.fromhex(salt_hex), iterations, 32).hex()


def config_text(password=None, salt_hex=None):
    if password is None:
        values = {"salt": None, "iterations": None, "hash": None}
    else:
        salt_hex = salt_hex or secrets.token_hex(16)
        values = {"salt": salt_hex, "iterations": ITERATIONS, "hash": derive(password, salt_hex)}
    return HEADER + f"window.SITE_GATE = {json.dumps(values)};\n"


def main():
    parser = argparse.ArgumentParser(description="사이트 접속 비밀번호 설정")
    parser.add_argument("--off", action="store_true", help="비밀번호 끄기")
    if parser.parse_args().off:
        CONFIG.write_text(config_text(), encoding="utf-8", newline="\n")
        print("비밀번호를 껐습니다.")
    else:
        password = getpass.getpass("새 비밀번호: ")
        if len(password) < MIN_LENGTH:
            sys.exit(f"{MIN_LENGTH}자 이상으로 정해 주세요. 바뀐 것은 없습니다.")
        if password != getpass.getpass("한 번 더: "):
            sys.exit("두 입력이 다릅니다. 바뀐 것은 없습니다.")
        CONFIG.write_text(config_text(password), encoding="utf-8", newline="\n")
        print("비밀번호를 저장했습니다. 원문은 저장되지 않았습니다.")
    print("아직 사이트에 반영되지 않았습니다. Claude에게 '설정했어'라고 말하면 배포합니다.")


if __name__ == "__main__":
    main()
