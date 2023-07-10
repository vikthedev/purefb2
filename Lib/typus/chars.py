__all__ = (
    'ANYDASH',
    'ANYSP',
    'DLQUO',
    'DPRIME',
    'FDASH',
    'HMINUS',
    'LAQUO',
    'LDQUO',
    'LSQUO',
    'MDASH',
    'MDASH_PAIR',
    'MINUS',
    'NBSP',
    'NDASH',
    'NNBSP',
    'RAQUO',
    'RDQUO',
    'RSQUO',
    'SPRIME',
    'THNSP',
    'TIMES',
    'WHSP',
)

NBSP = '\u00A0'
NNBSP = '\u202F'
THNSP = '\u2009'
WHSP = '\u0020'
ANYSP = r'[{}{}{}{}]'.format(WHSP, NBSP, NNBSP, THNSP)

HMINUS = '-'  # HYPHEN-MINUS
MINUS = '−'
FDASH = '‒'  # FIGURE DASH
NDASH = '–'
MDASH = '—'
# MDASH_PAIR = NNBSP + MDASH + THNSP
MDASH_PAIR = NBSP + MDASH + WHSP
HYPHEN = ''

ANYDASH = r'[{}{}{}{}{}]'.format(HMINUS, MINUS, FDASH, NDASH, MDASH)

TIMES = '×'

LSQUO = '‘'  # left curly quote mark
RSQUO = '’'  # right curly quote mark/apostrophe
LDQUO = '“'  # left curly quote marks
RDQUO = '”'  # right curly quote marks
DLQUO = '„'  # double low curly quote mark
LAQUO = '«'  # left angle quote marks
RAQUO = '»'  # right angle quote marks

SPRIME = '′'
DPRIME = '″'
