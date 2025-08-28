# Condensation core

This package implements Glaser-style condensation checks following the
Bulgarian methodology.  The key routine :func:`condensation.core.condensate_amount`
integrates the vapour flux entering and leaving every condensation zone and
returns the accumulated condensate mass ``Wk`` for a design period ``tk``.
The result is also apportioned per layer which enables moisture increase
checks against material limits.

The helper :func:`condensation.core.analyze` combines these calculations with
drying capacity estimates and surface-risk checks, providing a compact summary
for user interfaces and reports.

