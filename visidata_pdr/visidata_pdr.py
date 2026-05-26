"""
Load tabular data into VisiData using PDR
"""

from visidata import VisiData, asyncthread
from visidata.loaders._pandas import PandasSheet


class PdrSheet(PandasSheet):

    # workaround for https://github.com/saulpw/visidata/issues/2960
    # (fix not yet released)
    def dtype_to_type(self, dtype):
        pd = self.vd.importExternal("pandas")
        if isinstance(dtype, pd.Series):
            return super().dtype_to_type(dtype.dtype)
        return super().dtype_to_type(dtype)

    @asyncthread
    def reload(self):
        pd = self.vd.importExternal("pandas")

        if not hasattr(self.source, "table"):
            self.vd.fail(
                "sorry, not implemented: source with these attrs: "
                + repr(sorted(dir(self.source)))
            )
        if not isinstance(self.source.table, pd.DataFrame):
            self.vd.fail(
                "sorry, not implemented: source.table is a "
                + type(self.source.table).__name__
            )

        # there must be a better way to do this...
        self._pdr_source = self.source
        self.source = self.source.table

        # we're already in an async thread
        PandasSheet.reload.__wrapped__(self)


@VisiData.api
def open_pdr(vd, p) -> PdrSheet:
    pdr = vd.importExternal("pdr")

    # temporary - in general we need to start loading here, examine the
    # object structure of whatever we get, and pick an appropriate sheet type
    return PdrSheet(p.base_stem, source=pdr.open(p))
