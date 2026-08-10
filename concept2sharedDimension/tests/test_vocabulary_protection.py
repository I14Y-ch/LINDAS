from __future__ import annotations

import unittest
from unittest.mock import patch

from concept2sharedDimension.src.versioning.utils import I14YAPIHelper, LindasAPIHelper


class VocabularyProtectionTests(unittest.TestCase):
    def test_protected_vocabulary_is_not_deleted(self) -> None:
        protected = {("DV_DCAT_DATASET_THEME", "1.1.0")}
        with patch.object(I14YAPIHelper, "get_protected_vocabulary_versions", return_value=protected), patch.object(
            LindasAPIHelper,
            "get_lindas_concept_versions",
            return_value={"DV_DCAT_DATASET_THEME": ["1.1.0"]},
        ), patch.object(LindasAPIHelper, "graphdb_update") as update:
            result = LindasAPIHelper.delete_concept("DV_DCAT_DATASET_THEME")

        self.assertFalse(result)
        update.assert_not_called()

    def test_unprotected_vocabulary_keeps_existing_delete_behavior(self) -> None:
        with patch.object(I14YAPIHelper, "get_protected_vocabulary_versions", return_value=set()), patch.object(
            LindasAPIHelper,
            "get_lindas_concept_versions",
            return_value={"OTHER": ["1.0.0"]},
        ), patch.object(LindasAPIHelper, "graphdb_update") as update:
            LindasAPIHelper.delete_concept("OTHER")

        self.assertEqual(2, update.call_count)


if __name__ == "__main__":
    unittest.main()