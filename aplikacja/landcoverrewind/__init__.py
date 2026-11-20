"""Land Cover Rewind 1985-2025.

Reconstruction of built-up land and land cover from the Landsat archive for any area,
by transferring labels from present-day 10 m land cover maps to Landsat composites with a
Random Forest classifier and two series constraints (extent mask and monotonic accumulation).
All input data are read anonymously from the Microsoft Planetary Computer STAC catalogue.
"""
__version__ = "1.3.0"
EPOCHS = [1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025]
