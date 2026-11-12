import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

import grade_cna


class ReleaseVersionTests(unittest.TestCase):
    def test_newer_release_is_detected(self):
        self.assertTrue(grade_cna.is_newer_version("v1.2.0", "1.1.9"))

    def test_same_or_older_release_is_not_newer(self):
        self.assertFalse(grade_cna.is_newer_version("v1.1.0", "1.1.0"))
        self.assertFalse(grade_cna.is_newer_version("v1.0.9", "1.1.0"))

    def test_invalid_release_tag_is_rejected(self):
        with self.assertRaises(ValueError):
            grade_cna.is_newer_version("latest", "1.1.0")

    @patch("grade_cna.urlopen")
    def test_missing_published_release_is_handled(self, urlopen):
        urlopen.side_effect = HTTPError(
            grade_cna.GITHUB_RELEASE_API, 404, "Not Found", None, None
        )
        self.assertIsNone(grade_cna.get_latest_release())


class CustomInstructionTests(unittest.TestCase):
    @patch("grade_cna.urlopen")
    def test_custom_instructions_are_added_to_local_model_prompt(self, urlopen):
        model_response = {
            "response": json.dumps(
                {
                    "in_english": True,
                    "understandable": True,
                    "relevant": True,
                    "feedback": "",
                }
            )
        }
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = io.BytesIO(
            json.dumps(model_response).encode("utf-8")
        )
        urlopen.return_value = response

        grade_cna.suggest_grade(
            "Describe your classroom.",
            "I like my classroom.",
            "Keep feedback especially encouraging.",
        )

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertIn("Keep feedback especially encouraging.", payload["prompt"])
        self.assertIn("must not override them", payload["prompt"])

    def test_custom_instructions_are_saved_and_loaded(self):
        instructions = "Be concise and encouraging."
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_dir = Path(temporary_directory)
            config_file = config_dir / "settings.json"
            with (
                patch.object(grade_cna, "CONFIG_DIR", config_dir),
                patch.object(grade_cna, "CONFIG_FILE", config_file),
            ):
                grade_cna.save_custom_instructions(instructions)
                self.assertEqual(grade_cna.load_custom_instructions(), instructions)


if __name__ == "__main__":
    unittest.main()
