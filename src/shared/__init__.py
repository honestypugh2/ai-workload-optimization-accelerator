"""Shared kernel: cross-cutting types, contracts, configuration, and exceptions.

This package holds the framework-neutral building blocks used by every other
module. It contains no Azure SDK imports so that business logic remains testable
without cloud credentials.
"""
