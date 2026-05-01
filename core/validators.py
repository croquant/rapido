from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from stdnum import exceptions as stdnum_exceptions
from stdnum.eu import vat as eu_vat


def validate_vat(value: str, country: str) -> None:
    if not value:
        return
    if not value[:2].isalpha() or value[:2].upper() != country.upper():
        raise ValidationError(
            _(
                message="VAT number must start with the country code "
                "%(country)s."
            )
            % {"country": country.upper()},
            code="invalid_vat",
        )
    try:
        eu_vat.validate(value)
    except stdnum_exceptions.ValidationError as e:
        raise ValidationError(
            _(message="Invalid %(country)s VAT number.")
            % {"country": country.upper()},
            code="invalid_vat",
        ) from e


def validate_currency(value: str) -> None:
    if value not in settings.CURRENCIES:
        raise ValidationError(
            _(
                message="Invalid currency code. Supported currencies are: "
                "%(currencies)s."
            )
            % {"currencies": ", ".join(settings.CURRENCIES)},
            code="invalid_currency",
        )


validate_slug = RegexValidator(
    regex=r"^[a-z0-9-]+$",
    message=_(
        message="URL must contain only lowercase letters, digits, and hyphens."
    ),
)
