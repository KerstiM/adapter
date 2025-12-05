Berlin Group (NextGenPSD2): Berlin Group on Euroopa pankade ja makseasutuste konsortsium, mis töötas välja ühtse avatud panganduse NextGenPSD2 API raamistiku. See raamistik määratleb kontoandmete ja tehinguinfo (AIS – Account Information Service) vahetamiseks kasutatava andmemudeli ja sõnumite struktuuri. Berlin Group ei ole ametlik ELi institutsioon, kuid selle standard on laialdaselt kasutusele võetud üle Euroopa – üle 75% Euroopa pankadest ja sajad kolmandad osapooled (TPP-d) on NextGenPSD2 raamistiku juurutanud
berlin-group.org
. Berlin Groupi NextGenPSD2 hõlmab üksikasjalikku kontseptuaalset, loogilist ja füüsilist andmemudelit ning tehnilisi sõnumeid, sh JSON formaadis andmevälju konto saldo, tehingute ajaloo jms jaoks
berlin-group.org
.

Berlin Group NextGenPSD2 spetsifikatsioonid: Berlin Group on avaldanud terve komplekti dokumente, mis kirjeldavad PSD2 XS2A (Access to Account) liidest. Põhidokumentide hulgas on NextGenPSD2 Implementation Guidelines – tehniline juhis, mis spetsifitseerib üksikasjalikult konto infosüsteemi API struktuuri, sh ametlikud XML/JSON skeemid päringute ja vastuste jaoks
berlin-group.org
. Nendes juhistes on täpselt määratletud, millised väljad (nt konto ID, IBAN, valuuta, saldo tüüp, tehingu kuupäev, kirjeldus jms) peab API kaudu edastama konto väljavõtte või tehinguaruande päringu korral. Berlin Groupi andmemudel baseerub ISO 20022 standardil, mis tähendab, et andmeväljad ja nende tähendused on kooskõlas pangaülekannete ja kontoinfo rahvusvahelise standardiga. NextGenPSD2 dokumentatsioon (sh Implementation Guidelines, Operational Rules, jmt) on avalikult kättesaadav Creative Commons litsentsiga – need on tasuta allalaaditavad Berlin Groupi veebilehelt
berlin-group.org
berlin-group.org
. Seega on Berlin Groupi JSON-skeemid ametlikult dokumenteeritud tööstusstandard, mitte konfidentsiaalne spetsifikatsioon.


Berlin Group openFinance Data Dictionary

PSD2-stiilis transactions JSON-näide:

Sektsioonid: 2.205 ja 2.206
```
{
  "transactionId": "TX123456789",
  "bookingDate": "2025-11-01",
  "valueDate": "2025-11-02",
  "transactionAmount": {
    "amount": "150.00",
    "currency": "EUR"
  },
  "creditorName": "Acme OÜ",
  "remittanceInformationUnstructured": "Rent payment November",
  "bankTransactionCode": "PMNT-IRCT-ESCT",
  "entryReference": "ABC123456",
  "transactionType": "Credit",
  "balanceAfterTransaction": {
    "amount": "1200.00",
    "currency": "EUR"
  }
}
```

```
statementPeriod
{
  "from": "2025-10-01",
  "to": "2025-10-31"
}

account:
{
  "accountId": "EE123456789012345678",
  "currency": "EUR",
  "institution": "DemoBank"
}
```

output praegu:

```
  "transactions": [
    {
      "transaction_id": "409000611074-2017-06-29-000000",
      "account_id": "409000611074",
      "booking_date": "2017-06-29",
      "value_date": "2017-06-29",
      "amount": 1000000.0,
      "currency": "INR",
      "direction": "CREDIT",
      "balance_after": 1000000.0,
      "description": "TRF FROM  Indiaforensic SERVICES",
      "cheque_number": NaN,
      "row_index": 0
    },
```