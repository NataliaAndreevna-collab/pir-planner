"""Денежные суммы: форматирование и сумма прописью (русский язык)."""
from decimal import ROUND_HALF_UP, Decimal

_ONES_M = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_ONES_F = ["", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_TEENS = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
          "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят",
         "восемьдесят", "девяносто"]
_HUNDREDS = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот",
             "восемьсот", "девятьсот"]
# (форма для 1, для 2-4, для 5+), женский род?
_SCALES = [
    None,
    (("тысяча", "тысячи", "тысяч"), True),
    (("миллион", "миллиона", "миллионов"), False),
    (("миллиард", "миллиарда", "миллиардов"), False),
    (("триллион", "триллиона", "триллионов"), False),
]


def plural_form(n: int, forms) -> str:
    """Выбор формы слова по числу: forms = (для 1, для 2-4, для 5+)."""
    n = abs(int(n)) % 100
    if 11 <= n <= 19:
        return forms[2]
    last = n % 10
    if last == 1:
        return forms[0]
    if 2 <= last <= 4:
        return forms[1]
    return forms[2]


def _triplet_words(n: int, feminine: bool) -> list:
    words = []
    words.append(_HUNDREDS[n // 100])
    rest = n % 100
    if 10 <= rest <= 19:
        words.append(_TEENS[rest - 10])
    else:
        words.append(_TENS[rest // 10])
        words.append((_ONES_F if feminine else _ONES_M)[rest % 10])
    return [w for w in words if w]


def int_to_words(n: int, feminine: bool = False) -> str:
    """Целое число прописью, например 421000 -> «четыреста двадцать одна тысяча»."""
    n = int(n)
    if n == 0:
        return "ноль"
    if n < 0:
        return "минус " + int_to_words(-n, feminine)
    parts = []
    scale = 0
    while n > 0:
        triplet = n % 1000
        n //= 1000
        if triplet:
            if scale == 0:
                parts.append(" ".join(_triplet_words(triplet, feminine)))
            else:
                forms, fem = _SCALES[scale]
                words = _triplet_words(triplet, fem)
                parts.append(" ".join(words + [plural_form(triplet, forms)]))
        scale += 1
    return " ".join(reversed(parts))


def format_number_ru(value: float) -> str:
    """15447100 -> «15 447 100» (неразрывные пробелы между разрядами)."""
    return f"{int(value):,}".replace(",", "\u00a0")


def format_rub(value: float) -> str:
    """15447100.5 -> «15 447 100,50» (с копейками)."""
    d = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rub = int(d)
    kop = int((d - rub) * 100)
    return f"{format_number_ru(rub)},{kop:02d}"


def rubles_in_words(value: float) -> str:
    """
    Сумма прописью в форме коммерческого предложения:
    «421 000 (Четыреста двадцать одна тысяча) рублей, 00 копеек».
    """
    d = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rub = int(d)
    kop = int((d - rub) * 100)
    words = int_to_words(rub)
    words = words[:1].upper() + words[1:]
    rub_word = plural_form(rub, ("рубль", "рубля", "рублей"))
    kop_word = plural_form(kop, ("копейка", "копейки", "копеек"))
    return f"{format_number_ru(rub)} ({words}) {rub_word}, {kop:02d} {kop_word}"
