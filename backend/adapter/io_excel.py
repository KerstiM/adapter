from pathlib import Path

import pandas as pd


def read_bank_excel(path: str | Path) -> pd.DataFrame:
    """
    Loeb bank.xlsx stiilis konto väljavõtte Exceli faili ja tagastab DataFrame'i.
    """
    # Tagame, et tee on Path-objekt (mitte string)
    path = Path(path)

    # Loeme esimese töölehe Exceli failist DataFrame'iks
    df = pd.read_excel(path)

    # Eemaldame read, kus KÕIK veerud on tühjad/NaN (täiesti tühi rida Excelis)
    df = df.dropna(how="all")

    # Tagastame puhastatud tabeli edasiseks töötlemiseks
    return df
