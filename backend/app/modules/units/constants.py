"""Constants for IDTA-01003-b DataSpecificationUoM handling."""

from __future__ import annotations

DATA_SPECIFICATION_UOM_TEMPLATE_ID = (
    "https://admin-shell.io/DataSpecificationTemplates/DataSpecificationUoM/3"
)

DATA_SPECIFICATION_UOM_MODEL_TYPE = "DataSpecificationUoM"
DATA_SPECIFICATION_IEC61360_MODEL_TYPE = "DataSpecificationIEC61360"

UOM_FIELDS = (
    "preferredName",
    "symbol",
    "specificUnitID",
    "definition",
    "preferredNameQuantity",
    "quantityID",
    "classificationSystem",
    "classificationSystemVersion",
)

# Supported aliases observed in upstream catalogs.
UOM_SYMBOL_ALIASES = ("symbol", "unitSymbol")
