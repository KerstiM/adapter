"""Integration tests: pipeline with target_models configured.

Verifies that model-specific projections are produced alongside base
projections when target_models is set in the profile.
"""
from __future__ import annotations

import pytest

from application.pipeline import run_pipeline
from tests.fakes import (
    FakeDatasetPort,
    FakeOutputPort,
    FakeSpecPort,
    FakeValidationPort,
    FixedClock,
    load_spec_rulesets,
)
from tests.fakes.builders import make_accounts as _minimal_accounts, make_tx as _make_transaction, make_report as _transactions_report


def _profile_with_target_models() -> dict:
    """Profile with all 5 target models enabled."""
    return {
        "id": "test-multi-model",
        "version": "1.0.0",
        "schemas": {
            "S-00A": {},
            "S-00B": {},
            "S-00C": {},
            "S-01": {},
            "S-02": {},
            "S-03": {},
            "S-05": {},
        },
        "contracts": {
            "C-01": {"version": "1.0.0"},
            "C-02": {"version": "1.0.0"},
            "C-03": {
                "version": "1.0.0",
                "window": {"last_n": 200},
                "truncate": {
                    "counterparty_name_max_len": 80,
                    "remittance_max_len": 160,
                },
            },
            "C-04": {
                "llm_models": {
                    "llama3.1-8b-instruct": {
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
                    },
                    "mistral-7b-instruct-v0.3": {
                        "family": "mistral",
                        "template_tokens": {
                            "bos": "<s>",
                            "inst_start": "[INST] ",
                            "inst_end": " [/INST]",
                        },
                        "output_suffix": "mistral",
                    },
                    "qwen2.5-7b-instruct": {
                        "family": "chatml",
                        "template_tokens": {
                            "im_start": "<|im_start|>",
                            "im_end": "<|im_end|>",
                        },
                        "output_suffix": "qwen",
                    },
                },
                "ml_models": {
                    "xgboost": {
                        "encoding": "label",
                        "drop_string_columns": True,
                        "output_suffix": "xgboost",
                        "categorical_fields": ["status", "direction", "currency"],
                    },
                    "catboost": {
                        "encoding": "native",
                        "drop_string_columns": False,
                        "output_suffix": "catboost",
                        "categorical_fields": ["status", "direction", "currency", "counterparty_name"],
                    },
                },
            },
        },
        "rulesets": load_spec_rulesets(),
        "run_policy": {
            "partial_success_policy": {
                "fail_on": {
                    "any_severity": "ERROR",
                    "ratio_over_records": 0.05,
                },
            },
        },
        "target_models": {
            "llm_preamble": "You are a financial analysis assistant.",
            "llm": [
                "llama3.1-8b-instruct",
                "mistral-7b-instruct-v0.3",
                "qwen2.5-7b-instruct",
            ],
            "ml": [
                "xgboost",
                "catboost",
            ],
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPipelineWithModelTargets:
    """Pipeline produces model-specific outputs when target_models is set."""

    def _run(self) -> tuple[dict, FakeOutputPort]:
        ds = FakeDatasetPort(
            accounts=_minimal_accounts(),
            transaction_reports={"transactions.json": _transactions_report(
                booked=[_make_transaction()],
            )},
        )
        out = FakeOutputPort()
        spec = FakeSpecPort(profile_override=_profile_with_target_models())
        clock = FixedClock()

        summary = run_pipeline(
            dataset=ds, out=out, spec=spec, clock=clock, validator=FakeValidationPort(),
            dataset_id="test", input_dir="/test",
        )
        return summary, out

    def test_base_projections_still_produced(self):
        summary, out = self._run()
        assert out.sv is not None
        assert out.ml is not None
        assert out.llm is not None
        assert summary["outcome"] == "SUCCESS"

    def test_ml_model_outputs_produced(self):
        _, out = self._run()
        assert "xgboost" in out.ml_models
        assert "catboost" in out.ml_models

    def test_llm_model_outputs_produced(self):
        _, out = self._run()
        assert "llama3" in out.llm_models
        assert "mistral" in out.llm_models
        assert "qwen" in out.llm_models

    def test_xgboost_output_is_numeric(self):
        _, out = self._run()
        xgb = out.ml_models["xgboost"]
        assert xgb["model_id"] == "xgboost"
        assert len(xgb["feature_matrix"]) > 0
        for row in xgb["feature_matrix"]:
            for val in row:
                assert isinstance(val, (int, float))

    def test_catboost_output_has_cat_indices(self):
        _, out = self._run()
        cb = out.ml_models["catboost"]
        assert cb["model_id"] == "catboost"
        assert len(cb["cat_feature_indices"]) > 0
        assert len(cb["data"]) > 0

    def test_llama3_prompt_has_template_tokens(self):
        _, out = self._run()
        llama_results = out.llm_models["llama3"]
        assert len(llama_results) > 0
        prompt = llama_results[0]["prompt"]
        assert "<|begin_of_text|>" in prompt
        assert "<|eot_id|>" in prompt

    def test_mistral_prompt_has_inst_tokens(self):
        _, out = self._run()
        mistral_results = out.llm_models["mistral"]
        prompt = mistral_results[0]["prompt"]
        assert "[INST]" in prompt
        assert "[/INST]" in prompt

    def test_qwen_prompt_has_chatml_tokens(self):
        _, out = self._run()
        qwen_results = out.llm_models["qwen"]
        prompt = qwen_results[0]["prompt"]
        assert "<|im_start|>" in prompt
        assert "<|im_end|>" in prompt

    def test_preamble_in_all_llm_prompts(self):
        _, out = self._run()
        for suffix in ("llama3", "mistral", "qwen"):
            results = out.llm_models[suffix]
            prompt = results[0]["prompt"]
            assert "You are a financial analysis assistant." in prompt

    def test_counts_unchanged(self):
        summary, _ = self._run()
        assert summary["counts"]["ml_rows"] >= 1
        assert summary["counts"]["llm_contexts"] >= 1


class TestPipelineWithoutModelTargets:
    """Pipeline works unchanged when target_models is not set."""

    def test_no_model_outputs_by_default(self):
        ds = FakeDatasetPort(
            accounts=_minimal_accounts(),
            transaction_reports={"transactions.json": _transactions_report(
                booked=[_make_transaction()],
            )},
        )
        out = FakeOutputPort()
        spec = FakeSpecPort()  # default profile, no target_models
        clock = FixedClock()

        summary = run_pipeline(
            dataset=ds, out=out, spec=spec, clock=clock, validator=FakeValidationPort(),
            dataset_id="test", input_dir="/test",
        )
        assert summary["outcome"] == "SUCCESS"
        assert out.sv is not None
        assert out.ml is not None
        assert out.llm is not None
        assert len(out.ml_models) == 0
        assert len(out.llm_models) == 0
