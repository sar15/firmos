from engines.gst_components import extract_components


def test_extracts_verified_intrastate_components_without_float_rounding():
    result = extract_components({
        "sub_total": "100.01", "tax_total": "18.00", "taxes": [
            {"tax_name": "CGST 9%", "tax_amount": "9.00"},
            {"tax_name": "SGST 9%", "tax_amount": "9.00"},
        ],
    })
    assert result == {"igst_paise": 0, "cgst_paise": 900, "sgst_paise": 900, "cess_paise": 0, "taxable_paise": 10001, "components_verified": True}


def test_unknown_tax_label_stays_unverified_instead_of_guessing():
    result = extract_components({"total": "118", "tax_total": "18", "taxes": [{"tax_name": "GST", "tax_amount": "18"}]})
    assert result["taxable_paise"] == 10000
    assert result["components_verified"] is False
