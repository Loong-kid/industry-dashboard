# -*- coding: utf-8 -*-
"""접속 비밀번호: 파이썬·브라우저 해시 일치, 설정 파일 형식, 페이지 연결 시험."""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import set_site_password as gate  # noqa: E402

NODE_CHECK = r"""
const fs = require('fs'), vm = require('vm');
const sandbox = {window: {SITE_GATE: null}, crypto: globalThis.crypto, TextEncoder, Uint8Array, Promise, console};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('assets/site-gate.js', 'utf8'), sandbox);
const [password, salt, iterations] = JSON.parse(process.argv[1]);
sandbox.window.SiteGate.derive(password, salt, iterations).then(v => console.log(v));
"""


class SiteGateTest(unittest.TestCase):
    def test_browser_and_python_hashes_match(self):
        salt = "00112233445566778899aabbccddeeff"
        for password in ("correct horse", "한글비밀번호123", "é 조합형"):
            with self.subTest(password=password):
                result = subprocess.run(["node", "-e", NODE_CHECK, json.dumps([password, salt, 1000])], cwd=ROOT,
                                        capture_output=True, text=True, encoding="utf-8", check=True)
                self.assertEqual(result.stdout.strip(), gate.derive(password, salt, 1000))

    def test_config_never_contains_password(self):
        text = gate.config_text("my-secret-pass")
        self.assertNotIn("my-secret-pass", text)
        values = json.loads(re.search(r"window\.SITE_GATE = (\{.*\});", text)[1])
        self.assertEqual(values["hash"], gate.derive("my-secret-pass", values["salt"]))
        self.assertIsNone(json.loads(re.search(r"window\.SITE_GATE = (\{.*\});", gate.config_text())[1])["hash"])

    def test_committed_config_is_valid(self):
        text = (ROOT / "assets/site-gate-config.js").read_text(encoding="utf-8")
        values = json.loads(re.search(r"window\.SITE_GATE = (\{.*\});", text)[1])
        if values["hash"] is None:
            self.assertIsNone(values["salt"])
        else:
            self.assertRegex(values["hash"], r"^[0-9a-f]{64}$")
            self.assertRegex(values["salt"], r"^[0-9a-f]{32}$")
            self.assertGreaterEqual(values["iterations"], gate.ITERATIONS)

    def test_local_preview_skips_gate(self):
        script = (ROOT / "assets/site-gate.js").read_text(encoding="utf-8")
        self.assertIn(r"^(localhost|127\.0\.0\.1|\[::1\])$", script, "로컬 화면 시험이 입력창에서 멈추지 않게 한다")
        self.assertIn("!config.test_local", script)

    def test_gate_runs_before_app_and_holds_boot(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        order = [html.index(f"assets/{name}") for name in ("site-gate-config.js", "site-gate.js", "app.js")]
        self.assertEqual(order, sorted(order))
        self.assertLess(html.index("assets/site-gate.js"), html.index("</head>"), "내용이 보이기 전에 잠근다")
        self.assertIn("assets/site-gate.css", html)
        app = (ROOT / "assets/app.js").read_text(encoding="utf-8")
        self.assertIn("(window.siteGateReady || Promise.resolve()).then(boot);", app)
        self.assertNotRegex(app, r"(?m)^boot\(\);")


if __name__ == "__main__":
    unittest.main()
