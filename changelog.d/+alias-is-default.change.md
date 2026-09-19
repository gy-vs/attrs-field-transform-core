`field_transformer` hooks now receive fields whose default aliases have already been resolved (private-name handling applied), so parameter names can be derived from them directly.

Whether an alias has been auto-generated or explicitly provided is recorded on the new `attrs.Attribute.alias_is_default` field:
auto-generated aliases follow the field name when it is changed via `attrs.Attribute.evolve()`, while explicit aliases are preserved.
Fields added by a `field_transformer` with `alias=None` still get their default alias resolved after the hook has run.
