"""EPCIS 2.0 Core Business Vocabulary (CBV) enums.

Defines the standardised GS1 CBV 2.0 vocabularies for business steps,
dispositions, and business transaction types used in EPCIS events.

Reference: https://ref.gs1.org/cbv/
"""

from enum import Enum


class BizStep(str, Enum):
    """CBV 2.0 Business Step vocabulary (26 values).

    Each value is the short name used in EPCIS events. The JSON-LD
    ``@context`` handles expansion to the full CBV URI.
    """

    ACCEPTING = "accepting"
    ARRIVING = "arriving"
    ASSEMBLING = "assembling"
    COLLECTING = "collecting"
    COMMISSIONING = "commissioning"
    DECOMMISSIONING = "decommissioning"
    DEPARTING = "departing"
    DESTROYING = "destroying"
    DISASSEMBLING = "disassembling"
    ENCODING = "encoding"
    HOLDING = "holding"
    INSPECTING = "inspecting"
    INSTALLING = "installing"
    LOADING = "loading"
    PACKING = "packing"
    PICKING = "picking"
    RECEIVING = "receiving"
    REPAIRING = "repairing"
    REPLACING = "replacing"
    SHIPPING = "shipping"
    STORING = "storing"
    TRANSFORMING = "transforming"
    UNINSTALLING = "uninstalling"
    UNLOADING = "unloading"
    UNPACKING = "unpacking"
    VOID = "void"


class Disposition(str, Enum):
    """CBV 2.0 Disposition vocabulary (19 values)."""

    ACTIVE = "active"
    CONFORMANT = "conformant"
    CONTAINER_CLOSED = "container_closed"
    CONTAINER_OPEN = "container_open"
    DAMAGED = "damaged"
    DESTROYED = "destroyed"
    DISPOSED = "disposed"
    ENCODED = "encoded"
    IN_PROGRESS = "in_progress"
    IN_TRANSIT = "in_transit"
    INACTIVE = "inactive"
    NO_PEDIGREE_MATCH = "no_pedigree_match"
    NON_CONFORMANT = "non_conformant"
    RECALLED = "recalled"
    RESERVED = "reserved"
    RETURNED = "returned"
    SOLD = "sold"
    UNKNOWN = "unknown"


class BizTransactionType(str, Enum):
    """CBV 2.0 Business Transaction Type vocabulary (8 values)."""

    BOL = "bol"
    DESADV = "desadv"
    INV = "inv"
    PO = "po"
    POC = "poc"
    PRODORDER = "prodorder"
    RECADV = "recadv"
    RMA = "rma"
