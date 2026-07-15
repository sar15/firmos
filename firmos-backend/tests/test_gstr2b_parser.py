"""Tests for engines.gstr2b_parser — portal JSON ingestion."""

from engines.gstr2b_parser import parse_gstr2b_json


def test_parse_gstr2b_json_full():
    sample_payload = {
        "data": {
            "docdata": {
                "b2b": [
                    {
                        "ctin": "27AABCU9603R1ZM",
                        "trdnm": "ACME INDUSTRIES LTD",
                        "inv": [
                            {
                                "inum": "INV-2026-001",
                                "idt": "15/06/2026",
                                "val": 118000.0,
                                "itms": [{"iamt": 18000.0, "camt": 0.0, "samt": 0.0}]
                            }
                        ]
                    }
                ],
                "cdnr": [
                    {
                        "ctin": "27AABCU9603R1ZM",
                        "trdnm": "ACME INDUSTRIES LTD",
                        "nt": [
                            {
                                "ntnum": "CN-2026-009",
                                "ntdt": "20/06/2026",
                                "val": 5900.0
                            }
                        ]
                    }
                ],
                "b2ba": [],
                "cdnra": [],
                "impg": [{"boe": "BOE991"}]
            }
        }
    }

    lines = parse_gstr2b_json(sample_payload)
    assert len(lines) == 2
    assert lines[0].id == "2b-b2b-27aabcu9603r1zm-inv-2026-001"
    assert lines[0].amount == 11800000  # ₹118,000.00 in paise
    assert lines[0].ref == "INV-2026-001"
    assert lines[0].gstin == "27AABCU9603R1ZM"

    assert lines[1].id == "2b-cdnr-27aabcu9603r1zm-cn-2026-009"
    assert lines[1].amount == 590000  # ₹5,900.00 in paise
