"""
Load tabular data into VisiData using PDR
"""

from visidata import VisiData, Column, Progress, TableSheet, TextSheet
from visidata.loaders._pandas import PandasSheet
from visidata.loaders.npy import NpySheet


class LazyPDRSource:
    """
    Mixin class that makes any sheet's .source property lazily load
    from a pdr.Data object.  To use, inherit from this, then *don't*
    pass source= to the constructor and *do* pass _pdr_data=
    and _pdr_key= arguments.
    """

    def __init__(self, *args, **kwargs):
        if 'source' in kwargs:
            raise ValueError("do not specify source= for a lazy source")
        if '_pdr_source' in kwargs:
            raise ValueError("do not specify _pdr_source= for a lazy source")
        if '_pdr_data' not in kwargs:
            raise ValueError("must specify _pdr_data= for a lazy source")
        if '_pdr_key' not in kwargs:
            raise ValueError("must specify _pdr_key= for a lazy source")

        self._pdr_source = None
        self._pdr_data = kwargs.pop("_pdr_data")
        self._pdr_key = kwargs.pop("_pdr_key")
        super().__init__(*args, **kwargs)

    @property
    def source(self):
        if self._pdr_source is None:
            # indexing pdr.Data does a lazy load of the object
            self._pdr_source = self._pdr_data[self._pdr_key]
        return self._pdr_source

    @source.setter
    def source(self, val):
        self._pdr_source = val


class LazyTableSheet(TableSheet, LazyPDRSource):
    pass


class LazyTextSheet(TextSheet, LazyPDRSource):
    pass


class LazyNpySheet(NpySheet, LazyPDRSource):
    pass


class LazyPandasSheet(PandasSheet, LazyPDRSource):
    def dtype_to_type(self, dtype):
        """
        Patch PandasSheet with a workaround for
        https://github.com/saulpw/visidata/issues/2960
        whose fix is not yet released
        """
        pd = self.vd.importExternal("pandas")
        if isinstance(dtype, pd.Series):
            return super().dtype_to_type(dtype.dtype)
        return super().dtype_to_type(dtype)


def a_type(thing):
    """
    Return the name of the type of 'thing', with the correct
    English indefinite article prepended and some of Python's
    cryptic abbreviations expanded, e.g. 'a string', 'an integer'.

    If 'thing' is already a type object, uses the name of 'thing'
    itself, not the name of type(thing) (which would always be "type").
    """
    if isinstance(thing, type):
        name = thing.__name__
    else:
        name = type(thing).__name__

    name = ({
        "str":           "string",
        "bool":          "boolean",
        "int":           "integer",
        "float":         "real number",
        "dict":          "dictionary",
        "None":          "absent value",
        "NoneType":      "absent value",
    }).get(name, name)

    return ("an " if name[0] in "aeiouAEIOU" else "a ") + name


def sheet_class_for_obj(vd, stem, key, source):
    # if we got here, the pdr library is available
    # this is temporary until an official API is added
    from pdr.loaders.dispatch import pointer_to_loader

    try:
        ldr = type(pointer_to_loader(key, source)).__name__.removeprefix("Read")
    except Exception as e:
        vd.warning(
            f"{stem}/{key}: cannot determine appropriate sheet type: {e}"
        )
        return None

    match ldr:
        case "Table":
            return LazyPandasSheet

        case "Text":
            return LazyTextSheet

        case "Array" | "CompressedImage" | "Image":
            return LazyNpySheet

        case "Header" | "Trivial" | "TBD":
            vd.warning(
                f"{stem}: skipping {key} with sheet type {ldr}"
            )
            return None

        case "Fits":
            vd.warning(
                f"{stem}/{key}: not yet implemented: sheet type {ldr}"
            )
            return None


class PDSMetaSheet(TableSheet):
    rowtype = "label metadata"  # rowdef: (str, any)
    columns = [
        Column("tag", getter=lambda col,row: row[0]),
        Column("value", getter=lambda col,row: row[1]),
    ]

    def beforeLoad(self):
        for key in sorted(self.source.keys()):
            if key.upper() in ("LABEL", "HEADER"):
                continue
            if self.source._target_path(key) is None:
                self.vd.warning(
                    f"data not available for {self._pdr_stem}/{key}"
                )
                continue

            SheetClass = sheet_class_for_obj(
                self.vd,
                self._pdr_stem,
                key,
                self.source
            )
            if SheetClass is not None:
                self.vd.push(
                    SheetClass(
                        f"{self._pdr_stem}/{key}",
                        _pdr_data=self.source,
                        _pdr_key=key
                    ),
                    load=False
                )
        self.vd.push(self)

    def iterload(self):
        yield from self.source.metadata.items()


@VisiData.api
def open_pdr(vd, p):
    pdr = vd.importExternal("pdr")

    data = pdr.open(p)
    if data.standard == "PDS4":
        vd.fail(
            f"sorry, not implemented: "
            f"loading {p.base_stem}, whose label format is {data.standard}"
        )

    return PDSMetaSheet(f"{p.base_stem}/metadata",
                        source=data,
                        _pdr_stem=p.base_stem)
