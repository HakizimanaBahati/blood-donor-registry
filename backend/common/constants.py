BLOOD_TYPES = (
    ("A+", "A+"),
    ("A-", "A-"),
    ("B+", "B+"),
    ("B-", "B-"),
    ("AB+", "AB+"),
    ("AB-", "AB-"),
    ("O+", "O+"),
    ("O-", "O-"),
)

BLOOD_TYPE_VALUES = frozenset(code for code, _ in BLOOD_TYPES)

REQUEST_STATUSES = (
    ("pending", "Pending"),
    ("fulfilled", "Fulfilled"),
    ("cancelled", "Cancelled"),
)

ROLE_ADMIN = "admin"
ROLE_HOSPITAL = "hospital"
