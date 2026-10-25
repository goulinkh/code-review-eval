"""Author checks, not reviewer execution, semantic grading, or independent review."""

import json
import unittest
from itertools import product
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

from reference_checks.query_overrides import (
    CASE_IDS,
    PROBES,
    PROJECT_PATH,
    URL_PREFIX,
    check_contract,
    load_builder,
)
from validate_fixtures import validate_dataset, validate_fixture

ROOT = Path(__file__).resolve().parents[1]


class QueryOverridePairTests(unittest.TestCase):
    def test_pair_validates_with_private_relationships(self):
        self.assertEqual(
            validate_dataset([ROOT / "fixtures" / case_id for case_id in CASE_IDS]), 2,
        )
        documents = [
            validate_fixture(ROOT / "fixtures" / case_id) for case_id in CASE_IDS
        ]
        for index, (public, private) in enumerate(documents):
            self.assertEqual(public["protocol"]["name"], "fixed-context")
            self.assertEqual(private["expectations"]["context"]["condition"], "self-contained")
            self.assertEqual(private["provenance"]["verification"]["status"], "pending")
            self.assertEqual(private["dataset"]["partition"], "development")
            self.assertEqual(private["dataset"]["related_cases"], [{
                "case_id": CASE_IDS[1 - index], "relationship": "defect-fix",
            }])
            self.assertEqual(
                len(private["expectations"]["required_findings"]), 1 if index == 0 else 0,
            )
            self.assertEqual(
                private["labels"]["change_outcome"], "defective" if index == 0 else "clean",
            )
        first, second = (doc[0] for doc in documents)
        self.assertEqual(first["snapshots"]["base"], second["snapshots"]["base"])
        self.assertEqual(first["change"]["description"], second["change"]["description"])

    def test_intentional_defect_fails_exactly_the_collision_probes(self):
        failures = check_contract(load_builder("case-0004"))
        self.assertEqual(set(failures), {
            "existing-single", "existing-repeated", "empty-override",
            "encoded-key", "several-overrides", "case-sensitive-keys",
        })
        # The failures must be wrong query values, not crashes, mutations, or URL damage.
        for detail in failures.values():
            self.assertTrue(detail.startswith("expected query "), detail)
            self.assertNotIn(";", detail)

    def test_correction_passes_the_identical_contract(self):
        self.assertEqual(check_contract(load_builder("case-0005")), {})

    def test_checker_accepts_different_cross_key_order(self):
        builder = load_builder("case-0005")

        def grouped_by_key(link, overrides):
            built = urlsplit(builder(link, overrides))
            fields = parse_qsl(built.query, keep_blank_values=True)
            # Stable sorting changes cross-key order without reordering a key's values.
            fields.sort(key=lambda field: field[0])
            return urlunsplit(built._replace(query=urlencode(fields)))

        self.assertEqual(check_contract(grouped_by_key), {})

    def test_correction_matches_an_independent_multimap_oracle(self):
        builder = load_builder("case-0005")
        pairs = (("sort", "old"), ("sort", "older"), ("tag", "a"), ("tag", ""), ("", "v"))
        absent = object()
        states = (absent, None, "", "new & 雪")
        checked = 0
        for length in range(4):
            for fields in product(pairs, repeat=length):
                original = {}
                for key, value in fields:
                    original.setdefault(key, []).append(value)
                link = f"{URL_PREFIX}?{urlencode(fields)}#page-2"
                for values in product(states, repeat=3):
                    overrides = {
                        key: value for key, value in zip(("sort", "tag", ""), values)
                        if value is not absent
                    }
                    expected = {key: list(values) for key, values in original.items()}
                    # Group-and-assign oracle, independent of head's pair filtering.
                    for key, value in overrides.items():
                        if value is not None:
                            expected[key] = [value]
                    before = dict(overrides)
                    result = urlsplit(builder(link, overrides))
                    with self.subTest(fields=fields, overrides=before):
                        self.assertEqual(parse_qs(result.query, keep_blank_values=True), expected)
                        self.assertEqual(overrides, before)
                        self.assertEqual(
                            result._replace(query=""), urlsplit(link)._replace(query=""),
                        )
                    checked += 1
        self.assertEqual(checked, 9984)

    def test_first_value_consumer_observes_the_requested_sort_only_after_correction(self):
        link = f"{URL_PREFIX}?sort=old&sort=older&tag=a#page-2"
        for case_id, effective_sort in (("case-0004", "old"), ("case-0005", "new")):
            with self.subTest(case_id=case_id):
                result = load_builder(case_id)(link, {"sort": "new"})
                self.assertEqual(parse_qs(urlsplit(result).query)["sort"][0], effective_sort)

    def test_both_heads_preserve_the_base_without_overrides(self):
        for case_id in CASE_IDS:
            base, head = load_builder(case_id, "base"), load_builder(case_id)
            for probe in PROBES:
                link = f"{URL_PREFIX}?{probe.query}#page-2"
                with self.subTest(case_id=case_id, query=probe.query):
                    self.assertEqual(head(link), base(link))
                    self.assertEqual(head(link, None), base(link))
                    self.assertEqual(head(link, {}), base(link))

    def test_complete_head_is_supplied_without_private_material(self):
        for case_id in CASE_IDS:
            directory = ROOT / "fixtures" / case_id
            public = json.loads((directory / "reviewer/input.json").read_text())
            head = public["snapshots"]["head"]
            self.assertEqual(len(public["context_manifest"]), 1)
            context = public["context_manifest"][0]
            self.assertEqual(context, {
                "snapshot_id": head["id"], "path": PROJECT_PATH,
                "delivery": "initial", "availability": "available",
                "content": (
                    directory / "environment/blobs" / head["files"][0]["sha256"]
                ).read_text(),
            })
            self.assertEqual(
                {path.name for path in (directory / "reviewer").iterdir()}, {"input.json"},
            )


if __name__ == "__main__":
    unittest.main()
