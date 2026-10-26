"""Provenance and date semantics for the explicit, manual content importer."""

import importlib.util
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('curated_import', Path(__file__).parents[1] / 'scripts/import_curated_content.py')
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


class CuratedImportTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(importer.DEFAULT_MANIFEST.read_text())
        self.now = datetime(2026, 10, 14, 19, 50)

    def test_sources_and_counts(self):
        importer.validate_manifest(self.manifest)
        self.assertEqual({kind: sum(r['kind'] == kind for r in self.manifest['records'])
                          for kind in ('paper', 'news', 'wechat')}, {'paper': 3, 'news': 3, 'wechat': 3})

    def test_unknown_wechat_date_is_not_repost_date(self):
        for item in self.manifest['records']:
            if item['kind'] == 'wechat':
                _, _, row = importer.build_row(item, self.manifest['batch'], self.now)
                self.assertIsNone(row['published_time'])
                self.assertEqual(row['metadata_json'].adapted['repost_date'], item['repost_date'])
                self.assertIn(item['verification_url'], row['body'])

    def test_no_fabricated_model_receipt_or_original_publication_date(self):
        for item in self.manifest['records']:
            _, pk, row = importer.build_row(item, self.manifest['batch'], self.now)
            self.assertEqual(row['published_at'], self.now)
            self.assertEqual(row['handoff_status'], 'pending')
            self.assertEqual(row['handoff_result_json'].adapted, {})
            self.assertFalse(row['metadata_json'].adapted['llm_used'])
            self.assertNotIn('collection_run_id', row)
            self.assertIsNone(row['reviewed_by'])
            self.assertTrue(row.get('summary', row.get('abstract_text')).startswith('导读摘要'))
            _, _, rerun = importer.build_row(item, self.manifest['batch'], datetime(2026, 10, 15))
            self.assertEqual(row[pk], rerun[pk])

    def test_duplicate_and_missing_provenance_fail_before_writes(self):
        invalid = deepcopy(self.manifest)
        invalid['records'].append(invalid['records'][0])
        with self.assertRaises(ValueError):
            importer.validate_manifest(invalid)
        invalid = deepcopy(self.manifest)
        invalid['records'][-1].pop('verification_url')
        with self.assertRaises(ValueError):
            importer.validate_manifest(invalid)


if __name__ == '__main__':
    unittest.main()
