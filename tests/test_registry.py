# -*- coding: utf-8 -*-
"""registry 固定測資:ETF 清單偵測/海外分類/unsupported 判定。
執行:python3 -m unittest discover -s tests -q
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import registry

FIXTURE = Path(__file__).parent / "fixtures" / "twse_stock_day_all.json"


def load_rows():
    return json.loads(FIXTURE.read_text())


class DetectTests(unittest.TestCase):
    def test_detect_etfs_filters_00xxxA(self):
        etfs = registry.detect_etfs(load_rows())
        codes = {e["code"] for e in etfs}
        self.assertIn("00981A", codes)
        self.assertNotIn("0050", codes)
        self.assertTrue(all(len(c) == 6 and c.endswith("A") for c in codes))
        self.assertEqual(len(codes), 29)

    def test_foreign_classified(self):
        etfs = {e["code"]: e for e in registry.detect_etfs(load_rows())}
        self.assertEqual(etfs["00988A"]["market"], "foreign")  # 主動統一全球創新
        self.assertEqual(etfs["00402A"]["market"], "foreign")  # 主動安聯美國科技
        self.assertEqual(etfs["00983A"]["market"], "foreign")  # 中信ARK創新實持美股
        self.assertEqual(etfs["00981A"]["market"], "tw")

    def test_issuer_and_adapter_mapping(self):
        etfs = {e["code"]: e for e in registry.detect_etfs(load_rows())}
        self.assertEqual(etfs["00981A"]["issuer"], "統一")
        self.assertEqual(etfs["00991A"]["adapter"], "fuhhwa")
        self.assertEqual(etfs["00405A"]["adapter"], "fubon")


class RegistryFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "etf_registry.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_code_unsupported(self):
        fetched = registry.detect_etfs(load_rows())
        fetched.append({"code": "00998A", "name": "主動未知投信基金", "market": "tw"})
        reg = registry.load_and_update(self.path, fetched)
        self.assertEqual(reg["00998A"]["status"], "unsupported")
        self.assertEqual(reg["00981A"]["status"], "active")
        reg2 = registry.load_and_update(self.path, fetched)
        self.assertEqual(reg2["00998A"]["status"], "unsupported")
        self.assertEqual(len(reg2), len(reg))

    def test_manual_override_preserved(self):
        fetched = registry.detect_etfs(load_rows())
        reg = registry.load_and_update(self.path, fetched)
        reg["00981A"]["market"] = "foreign"  # 模擬手動覆寫
        self.path.write_text(json.dumps(reg, ensure_ascii=False))
        reg2 = registry.load_and_update(self.path, fetched)
        self.assertEqual(reg2["00981A"]["market"], "foreign")


if __name__ == "__main__":
    unittest.main()
