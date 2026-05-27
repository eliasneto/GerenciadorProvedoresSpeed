import re


VARIABLE_PATTERN = re.compile(r"{([^}]+)}")


def variables(template):
    return VARIABLE_PATTERN.findall(template)
