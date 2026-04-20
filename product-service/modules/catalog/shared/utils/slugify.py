from django.utils.text import slugify


def build_slug(value: str) -> str:
    return slugify(value or '')
