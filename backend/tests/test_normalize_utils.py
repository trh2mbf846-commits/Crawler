from app.normalize_utils import make_kurzbeschreibung, parse_currency_de, parse_date_de


def test_parse_date_de_deutsches_format():
    d = parse_date_de("30.09.2026")
    assert d is not None
    assert (d.year, d.month, d.day) == (2026, 9, 30)


def test_parse_date_de_iso_format():
    d = parse_date_de("2026-09-30")
    assert (d.year, d.month, d.day) == (2026, 9, 30)


def test_parse_date_de_leer():
    assert parse_date_de(None) is None
    assert parse_date_de("") is None


def test_parse_currency_de_tausendertrennzeichen():
    assert parse_currency_de("1.234.567,89 EUR") == 1234567.89


def test_parse_currency_de_englisch():
    assert parse_currency_de("1234.56") == 1234.56


def test_make_kurzbeschreibung_kuerzt():
    text = "Wort " * 200
    kurz = make_kurzbeschreibung(text, max_len=50)
    assert len(kurz) <= 51
    assert kurz.endswith("…")


def test_make_kurzbeschreibung_none():
    assert make_kurzbeschreibung(None) is None
