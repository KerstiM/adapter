from pathlib import Path
from typing import Any, Dict
import json


def write_statement_json(data: Dict[str, Any], path: str | Path) -> None:
    """
    Kirjutab konto väljavõtte JSON-struktuuri faili.

    Eeldab, et `data` on juba õiges vormis:
    {
      "account": {...},
      "statement_period": {...},
      "source": {...},
      "transactions": [...]
    }
    """
    # Tagame, et path on Path-objekt (võib tulla stringina)
    path = Path(path)

    # Loome vajadusel kataloogid, kuhu faili kirjutame (nt data/)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Serialiseerime dict'i loetavaks JSON-stringiks
    text = json.dumps(data, indent=2, ensure_ascii=False)

    # Kirjutame JSON-faili UTF-8 kodeeringus
    path.write_text(text, encoding="utf-8")
