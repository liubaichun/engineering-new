"""
Material app migrations.

Migration 0001: Initial - category is CharField with choices (VARCHAR in DB)
Migration 0002: (was attempted FK to MaterialCategory, FAILED - DB column stayed VARCHAR)

Since material_category table is empty and category column in DB is VARCHAR with
string values ('cable', 'network', etc.), we revert to CharField with choices.
"""

