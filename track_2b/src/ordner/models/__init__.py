import gc

import torch

DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"

# Target fields of the eCH-0196 summary page (data contract, docs/08) with a description used in prompts.
FIELDS = {
    "totalTaxValue": "total tax value of all A, B, DA-1 and USA values at year end "
    "(Total Steuerwert / valeur fiscale totale / valore fiscale totale)",
    "totalGrossRevenueA": "total gross revenue of A values, i.e. WITH Swiss withholding tax "
    "(Total Bruttoertrag A-Werte mit VSt.-Abzug / rendement brut A avec impôt anticipé)",
    "totalGrossRevenueB": "total gross revenue of B, DA-1 and USA values, i.e. WITHOUT Swiss withholding tax "
    "(Total Bruttoertrag B-, DA-1- und USA-Werte ohne VSt.-Abzug / rendement brut B sans impôt anticipé)",
    "totalWithHoldingTaxClaim": "Swiss withholding tax claim "
    "(Verrechnungssteueranspruch / impôt anticipé à récupérer / imposta preventiva)",
    "institution": "name of the financial institution that issued the statement",
    "canton": "two-letter code of the Swiss canton of the taxpayer (e.g. ZH, VD)",
    "taxPeriod": "tax year covered by the statement (e.g. 2025)",
    "client_last_name": "last name of the client (taxpayer)",
}
NUMERIC_FIELDS = ("totalTaxValue", "totalGrossRevenueA", "totalGrossRevenueB", "totalWithHoldingTaxClaim")


def free_memory():
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
