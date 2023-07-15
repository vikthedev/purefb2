#!/usr/bin/python

__all__ = "to_latin"

import re

CYR_TO_LAT_MAP = {
    # cyr symbols
    u"А": u"A", u"а": u"a",
    u"Б": u"B", u"б": u"b",
    u"В": u"V", u"в": u"v",
    u"Г": u"G", u"г": u"g",
    u"Д": u"D", u"д": u"d",
    u"Е": u"E", u"е": u"e",
    u"Ж": u"ZH", u"ж": u"zh",
    u"З": u"Z", u"з": u"z",
    u"И": u"I", u"и": u"i",
    u"Й": u"J", u"й": u"j",
    u"К": u"K", u"к": u"k",
    u"Л": u"L", u"л": u"l",
    u"М": u"M", u"м": u"m",
    u"Н": u"N", u"н": u"n",
    u"О": u"O", u"о": u"o",
    u"П": u"P", u"п": u"p",
    u"Р": u"R", u"р": u"r",
    u"С": u"S", u"с": u"s",
    u"Т": u"T", u"т": u"t",
    u"У": u"U", u"у": u"u",
    u"Ф": u"F", u"ф": u"f",
    u"Х": u"X", u"х": u"x",
    u"Ц": u"C", u"ц": u"c",
    u"Ч": u"CH", u"ч": u"ch",
    u"Ш": u"SH", u"ш": u"sh",
    u"Щ": u"SCH", u"щ": u"sch",
    u"Ь": u"'", u"ь": u"'",
    u"Ю": u"YU", u"ю": u"yu",
    u"Я": u"YA", u"я": u"ya",
    # UA symbols
    u"Ґ": u"G", u"ґ": u"g",
    u"Є": u"JE", u"є": u"je",
    u"І": u"I", u"і": u"i",
    u"Ї": u"JI", u"ї": u"ji",
    # RU symbols
    u"Ё": u"E", u"ё": u"e",
    u"Ъ": u"'", u"ъ": u"'",
    u"Ы": u"Y'", u"ы": u"y'",
    u"Э": u"E'", u"э": u"e'",

}


def to_latin(data: str = '', case: str | None = None, file_friendly_name: bool = False):
    """ Transliterate cyrillic string of characters to latin string of characters.
    :param file_safe:
    :param case:
    :param data: The cyrillic string to transliterate into latin characters.
    :return: A string of latin characters transliterated from the given cyrillic string.
    """

    # Changing the symbols case
    if case == 'lower':
        data = data.lower()
    elif case == 'upper':
        data = data.upper()

    # Get the character per character transliteration dictionary
    transliteration_dict = CYR_TO_LAT_MAP

    # Initialize the output latin string variable
    latinized_data = ''

    # Transliterate by traversing the input string character by character.
    for c in data:
        # If character is in dictionary, it means it's a cyrillic so let's transliterate that character.
        if c in transliteration_dict:
            # Transliterate current character.
            latinized_data += transliteration_dict[c]
        # If character is not in character transliteration dictionary,
        # it is most likely a number or a special character so just keep it.
        else:
            latinized_data += c

    # Return the transliterated string.
    if file_friendly_name:
        latinized_data = __file_friendly_name(latinized_data, None)
    return latinized_data


def __file_friendly_name(data: str = '', case: str | None = None) -> str:
    data = re.sub(r'["\\?!@#$%^&*+|/:;\[\]{}<>\']', '', data)
    data = re.sub(r'["—]', '-', data)
    data = re.sub(r'[\s\\(\\)\\\.]+', '_', data)
    return data.strip('. _')
