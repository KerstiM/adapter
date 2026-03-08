"""
C-04 ML encoders — transform base ML rows for specific ML frameworks.

Pure functions, no I/O.  Each encoder receives:
  - ml_rows: list[dict]  (output from C-02 project_ml)
  - sv_bundle: dict       (full SV bundle for additional data if needed)
  - config: dict          (model config from C-04 contract)

Returns a dict with model-specific data structure + metadata.
"""
from __future__ import annotations


def _build_label_encodings(
    rows: list[dict],
    categorical_fields: list[str],
) -> dict[str, dict[str, int]]:
    """Build label-encoding maps for categorical fields.

    For each field, assigns integers 0..N-1 to sorted unique values.
    """
    encodings: dict[str, dict[str, int]] = {}
    for field in categorical_fields:
        unique_vals = sorted({str(row.get(field, "")) for row in rows})
        encodings[field] = {val: idx for idx, val in enumerate(unique_vals)}
    return encodings


def format_xgboost(
    ml_rows: list[dict],
    sv_bundle: dict,
    config: dict,
) -> dict:
    """Format ML rows for XGBoost.

    - Label-encodes categorical fields to integers.
    - Drops pure string columns (counterparty_name, remittance).
    - Produces a numeric feature matrix.

    Returns
    -------
    dict
        ``{feature_matrix, feature_names, label_encodings, row_count}``
    """
    cat_fields = config.get("categorical_fields", ["status", "direction", "currency"])
    drop_strings = config.get("drop_string_columns", True)

    encodings = _build_label_encodings(ml_rows, cat_fields)

    # Determine which fields to keep (numeric + encoded categoricals)
    string_fields = {"counterparty_name", "remittance"}
    keep_fields = [
        "row_id", "account_id", "record_id",
        "status", "booking_date", "value_date", "direction",
        "currency", "signed_amount", "abs_amount",
        "counterparty_name", "remittance",
    ]

    if drop_strings:
        keep_fields = [f for f in keep_fields if f not in string_fields]

    # Also drop booking_date / value_date as they are date strings
    # XGBoost needs purely numeric data
    date_fields = {"booking_date", "value_date"}
    keep_fields = [f for f in keep_fields if f not in date_fields]

    # Also drop account_id and record_id (string identifiers, not features)
    id_fields = {"account_id", "record_id"}
    feature_fields = [f for f in keep_fields if f not in id_fields]

    matrix: list[list[float | int]] = []
    for row in ml_rows:
        encoded_row: list[float | int] = []
        for field in feature_fields:
            val = row.get(field, 0)
            if field in cat_fields:
                encoded_row.append(encodings[field].get(str(val), 0))
            elif field == "row_id":
                encoded_row.append(int(val))
            else:
                try:
                    encoded_row.append(float(val))
                except (ValueError, TypeError):
                    encoded_row.append(0.0)
        matrix.append(encoded_row)

    return {
        "model_id": "xgboost",
        "feature_names": feature_fields,
        "feature_matrix": matrix,
        "label_encodings": encodings,
        "row_count": len(matrix),
    }


def format_catboost(
    ml_rows: list[dict],
    sv_bundle: dict,
    config: dict,
) -> dict:
    """Format ML rows for CatBoost.

    - Keeps categorical fields as strings (CatBoost handles them natively).
    - Provides cat_feature_indices for CatBoost Pool construction.

    Returns
    -------
    dict
        ``{data, feature_names, cat_feature_indices, row_count}``
    """
    cat_fields_set = set(config.get("categorical_fields", [
        "status", "direction", "currency", "counterparty_name",
    ]))

    # Drop date strings and IDs — keep features only
    skip_fields = {"booking_date", "value_date", "account_id", "record_id"}
    feature_fields = [
        f for f in [
            "row_id", "status", "direction", "currency",
            "signed_amount", "abs_amount",
            "counterparty_name", "remittance",
        ]
        if f not in skip_fields
    ]

    cat_indices = [i for i, f in enumerate(feature_fields) if f in cat_fields_set]

    data: list[list] = []
    for row in ml_rows:
        data_row: list = []
        for field in feature_fields:
            val = row.get(field, "")
            if field in cat_fields_set:
                data_row.append(str(val))
            elif field == "row_id":
                data_row.append(int(val))
            else:
                try:
                    data_row.append(float(val))
                except (ValueError, TypeError):
                    data_row.append(0.0)
        data.append(data_row)

    return {
        "model_id": "catboost",
        "feature_names": feature_fields,
        "data": data,
        "cat_feature_indices": cat_indices,
        "row_count": len(data),
    }
