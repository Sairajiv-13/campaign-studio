"""Offline evaluation for the copy scorer.

Validates that the scorer's ranking agrees with human marketer preference on a
labeled set of A/B copy pairs. Same harness works with the sandbox judge
(deterministic, CI gate) or a real model. See ``python -m evals --help``.
"""
