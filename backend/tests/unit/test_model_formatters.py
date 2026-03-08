"""Unit tests for C-04 model-specific formatters."""
from __future__ import annotations

import json

import pytest

from domain.projections.model_formatters import format_for_model
from domain.projections.model_formatters.llm_templates import (
    format_chatml,
    format_llama3,
    format_mistral,
)
from domain.projections.model_formatters.ml_encoders import (
    format_catboost,
    format_xgboost,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_llm_contexts() -> list[dict]:
    return [
        {
            "meta": {
                "run_id": "abc123",
                "created_at_utc": "2024-01-01T00:00:00Z",
                "account_id": "ACCT-1",
                "iban": "DE89370400440532013000",
                "currency": "EUR",
            },
            "tx": [
                {"id": "TX-1", "d": "2024-01-01", "s": "BOOKED", "dir": "DEBIT",
                 "a": "-50.00", "c": "EUR", "cp": "Shop A", "r": "Groceries"},
            ],
        }
    ]


@pytest.fixture()
def sample_sv_bundle() -> dict:
    return {
        "meta": {"run_id": "abc123", "created_at_utc": "2024-01-01T00:00:00Z"},
        "accounts": [{"account_id": "ACCT-1", "iban": "DE89370400440532013000", "currency": "EUR"}],
        "transactions": [
            {
                "account_id": "ACCT-1",
                "record_id": "TX-1",
                "status": "BOOKED",
                "booking_date": "2024-01-01",
                "value_date": "2024-01-01",
                "direction": "DEBIT",
                "amount": {"signed": "-50.00", "abs": "50.00", "currency": "EUR"},
                "counterparty": {"name": "Shop A"},
                "remittance": "Groceries",
            },
        ],
    }


@pytest.fixture()
def sample_ml_rows() -> list[dict]:
    return [
        {
            "row_id": 1,
            "account_id": "ACCT-1",
            "record_id": "TX-1",
            "status": "BOOKED",
            "booking_date": "2024-01-01",
            "value_date": "2024-01-01",
            "direction": "DEBIT",
            "currency": "EUR",
            "signed_amount": "-50.00",
            "abs_amount": "50.00",
            "counterparty_name": "Shop A",
            "remittance": "Groceries",
        },
        {
            "row_id": 2,
            "account_id": "ACCT-1",
            "record_id": "TX-2",
            "status": "PENDING",
            "booking_date": "",
            "value_date": "2024-01-02",
            "direction": "CREDIT",
            "currency": "EUR",
            "signed_amount": "100.00",
            "abs_amount": "100.00",
            "counterparty_name": "Employer",
            "remittance": "Salary",
        },
    ]


@pytest.fixture()
def llama3_config() -> dict:
    return {
        "family": "llama3",
        "template_tokens": {
            "bos": "<|begin_of_text|>",
            "system_start": "<|start_header_id|>system<|end_header_id|>\n\n",
            "system_end": "<|eot_id|>",
            "user_start": "<|start_header_id|>user<|end_header_id|>\n\n",
            "user_end": "<|eot_id|>",
            "assistant_start": "<|start_header_id|>assistant<|end_header_id|>\n\n",
        },
        "output_suffix": "llama3",
    }


@pytest.fixture()
def mistral_config() -> dict:
    return {
        "family": "mistral",
        "template_tokens": {
            "bos": "<s>",
            "inst_start": "[INST] ",
            "inst_end": " [/INST]",
        },
        "output_suffix": "mistral",
    }


@pytest.fixture()
def chatml_config() -> dict:
    return {
        "family": "chatml",
        "template_tokens": {
            "im_start": "<|im_start|>",
            "im_end": "<|im_end|>",
        },
        "output_suffix": "qwen",
    }


@pytest.fixture()
def xgboost_config() -> dict:
    return {
        "encoding": "label",
        "drop_string_columns": True,
        "output_suffix": "xgboost",
        "categorical_fields": ["status", "direction", "currency"],
    }


@pytest.fixture()
def catboost_config() -> dict:
    return {
        "encoding": "native",
        "drop_string_columns": False,
        "output_suffix": "catboost",
        "categorical_fields": ["status", "direction", "currency", "counterparty_name"],
    }


PREAMBLE = "You are a financial analysis assistant."


# ---------------------------------------------------------------------------
# LLM template tests
# ---------------------------------------------------------------------------

class TestFormatLlama3:
    def test_wraps_with_template_tokens(self, sample_llm_contexts, sample_sv_bundle, llama3_config):
        results = format_llama3(sample_llm_contexts, sample_sv_bundle, llama3_config, preamble=PREAMBLE)
        assert len(results) == 1
        prompt = results[0]["prompt"]
        assert prompt.startswith("<|begin_of_text|><|start_header_id|>system<|end_header_id|>")
        assert PREAMBLE in prompt
        assert "<|eot_id|>" in prompt
        assert "<|start_header_id|>user<|end_header_id|>" in prompt
        assert "<|start_header_id|>assistant<|end_header_id|>" in prompt
        assert prompt.endswith("<|start_header_id|>assistant<|end_header_id|>\n\n")

    def test_contains_context_json(self, sample_llm_contexts, sample_sv_bundle, llama3_config):
        results = format_llama3(sample_llm_contexts, sample_sv_bundle, llama3_config, preamble=PREAMBLE)
        prompt = results[0]["prompt"]
        assert '"ACCT-1"' in prompt
        assert '"TX-1"' in prompt

    def test_account_id_in_result(self, sample_llm_contexts, sample_sv_bundle, llama3_config):
        results = format_llama3(sample_llm_contexts, sample_sv_bundle, llama3_config, preamble=PREAMBLE)
        assert results[0]["account_id"] == "ACCT-1"
        assert results[0]["model_id"] == "llama3.1-8b-instruct"


class TestFormatMistral:
    def test_wraps_with_inst_tokens(self, sample_llm_contexts, sample_sv_bundle, mistral_config):
        results = format_mistral(sample_llm_contexts, sample_sv_bundle, mistral_config, preamble=PREAMBLE)
        assert len(results) == 1
        prompt = results[0]["prompt"]
        assert prompt.startswith("<s>[INST] ")
        assert PREAMBLE in prompt
        assert prompt.endswith(" [/INST]")

    def test_contains_context_json(self, sample_llm_contexts, sample_sv_bundle, mistral_config):
        results = format_mistral(sample_llm_contexts, sample_sv_bundle, mistral_config, preamble=PREAMBLE)
        prompt = results[0]["prompt"]
        assert '"ACCT-1"' in prompt


class TestFormatChatML:
    def test_wraps_with_im_tokens(self, sample_llm_contexts, sample_sv_bundle, chatml_config):
        results = format_chatml(sample_llm_contexts, sample_sv_bundle, chatml_config, preamble=PREAMBLE)
        assert len(results) == 1
        prompt = results[0]["prompt"]
        assert "<|im_start|>system\n" in prompt
        assert PREAMBLE in prompt
        assert "<|im_end|>" in prompt
        assert "<|im_start|>user\n" in prompt
        assert "<|im_start|>assistant\n" in prompt

    def test_model_id(self, sample_llm_contexts, sample_sv_bundle, chatml_config):
        results = format_chatml(sample_llm_contexts, sample_sv_bundle, chatml_config, preamble=PREAMBLE)
        assert results[0]["model_id"] == "qwen2.5-7b-instruct"


# ---------------------------------------------------------------------------
# ML encoder tests
# ---------------------------------------------------------------------------

class TestFormatXGBoost:
    def test_produces_numeric_matrix(self, sample_ml_rows, sample_sv_bundle, xgboost_config):
        result = format_xgboost(sample_ml_rows, sample_sv_bundle, xgboost_config)
        assert result["model_id"] == "xgboost"
        assert result["row_count"] == 2
        for row in result["feature_matrix"]:
            for val in row:
                assert isinstance(val, (int, float)), f"Non-numeric value: {val!r}"

    def test_label_encodings_present(self, sample_ml_rows, sample_sv_bundle, xgboost_config):
        result = format_xgboost(sample_ml_rows, sample_sv_bundle, xgboost_config)
        enc = result["label_encodings"]
        assert "status" in enc
        assert "BOOKED" in enc["status"]
        assert "PENDING" in enc["status"]
        assert "direction" in enc
        assert "DEBIT" in enc["direction"]
        assert "CREDIT" in enc["direction"]

    def test_no_string_columns(self, sample_ml_rows, sample_sv_bundle, xgboost_config):
        result = format_xgboost(sample_ml_rows, sample_sv_bundle, xgboost_config)
        assert "counterparty_name" not in result["feature_names"]
        assert "remittance" not in result["feature_names"]
        assert "booking_date" not in result["feature_names"]
        assert "value_date" not in result["feature_names"]

    def test_feature_names_match_matrix_width(self, sample_ml_rows, sample_sv_bundle, xgboost_config):
        result = format_xgboost(sample_ml_rows, sample_sv_bundle, xgboost_config)
        for row in result["feature_matrix"]:
            assert len(row) == len(result["feature_names"])


class TestFormatCatBoost:
    def test_preserves_categoricals_as_strings(self, sample_ml_rows, sample_sv_bundle, catboost_config):
        result = format_catboost(sample_ml_rows, sample_sv_bundle, catboost_config)
        assert result["model_id"] == "catboost"
        assert result["row_count"] == 2
        # Check that categorical columns have string values
        for idx in result["cat_feature_indices"]:
            for row in result["data"]:
                assert isinstance(row[idx], str), f"Expected string at index {idx}: {row[idx]!r}"

    def test_cat_feature_indices_correct(self, sample_ml_rows, sample_sv_bundle, catboost_config):
        result = format_catboost(sample_ml_rows, sample_sv_bundle, catboost_config)
        cat_names = [result["feature_names"][i] for i in result["cat_feature_indices"]]
        for name in ["status", "direction", "currency", "counterparty_name"]:
            if name in result["feature_names"]:
                assert name in cat_names, f"{name} should be categorical"

    def test_feature_names_match_data_width(self, sample_ml_rows, sample_sv_bundle, catboost_config):
        result = format_catboost(sample_ml_rows, sample_sv_bundle, catboost_config)
        for row in result["data"]:
            assert len(row) == len(result["feature_names"])


# ---------------------------------------------------------------------------
# Dispatcher tests
# ---------------------------------------------------------------------------

class TestFormatForModel:
    def test_dispatches_llm(self, sample_llm_contexts, sample_sv_bundle, llama3_config):
        result = format_for_model(
            sample_llm_contexts, sample_sv_bundle,
            "llama3.1-8b-instruct", llama3_config, "llm",
            preamble=PREAMBLE,
        )
        assert isinstance(result, list)
        assert result[0]["model_id"] == "llama3.1-8b-instruct"

    def test_dispatches_ml(self, sample_ml_rows, sample_sv_bundle, xgboost_config):
        result = format_for_model(
            sample_ml_rows, sample_sv_bundle,
            "xgboost", xgboost_config, "ml",
        )
        assert result["model_id"] == "xgboost"

    def test_unknown_family_raises(self, sample_llm_contexts, sample_sv_bundle):
        with pytest.raises(ValueError, match="Unknown LLM family"):
            format_for_model(
                sample_llm_contexts, sample_sv_bundle,
                "unknown", {"family": "nonexistent"}, "llm",
            )

    def test_unknown_type_raises(self, sample_ml_rows, sample_sv_bundle):
        with pytest.raises(ValueError, match="Unknown projection_type"):
            format_for_model(
                sample_ml_rows, sample_sv_bundle,
                "test", {}, "unknown",
            )
