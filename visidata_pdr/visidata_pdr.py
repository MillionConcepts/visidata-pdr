"""
Load tabular data into VisiData using PDR
"""

from visidata import (
    VisiData, Column, TableSheet, TextSheet, asyncthread
)
from visidata.loaders._pandas import PandasSheet
from visidata.loaders.npy import NpySheet


class PDRSource:
    """
    Object to be used as the .source of one of the Lazy sheets below.
    get() loads the relevant data only when needed.
    """

    def __init__(self, container, key):
        self.container = container
        self.key = key
        self.data = None

    def get(self):
        if self.data is None:
            self.data = self.container[self.key]
        return self.data

    def __str__(self):
        return f"pdr.Data({self.container.filename!r}).{self.key}"


class LazyTextSheet(TextSheet):
    def iterload(self):
        yield from self.readlines(self.source.get())


class LazyNpySheet(NpySheet):
    def iterload(self):
        if not hasattr(self, 'npy'):
            self.npy = self.source.get()
        return super().iterload()


class LazyPandasSheet(PandasSheet):
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

    @asyncthread
    def reload(self):
        self._pdr_source = self.source
        self.source = self.source.get()
        # we're already in an async thread
        PandasSheet.reload.__wrapped__(self)


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

        # In this case, guess that we're going to get a table if the
        # HDU's metadata has a "COLUMNS" key, and an image if it doesn't.
        case "Fits":
            md = source.metadata[key]
            return LazyPandasSheet if "COLUMNS" in md else LazyNpySheet

        case other:
            vd.warning(
                f"{stem}/{key}: not yet implemented: sheet type {other}"
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
            # Skip all "header" objects; they are covered by the "label" sheet.
            if (
                key.upper() in ("LABEL", "HEADER")
                or key not in self.source.metadata
                or "HEADER_TYPE" in self.source.metadata[key]
            ):
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
                        source=PDRSource(self.source, key)
                    ),
                    load=False
                )
        self.vd.push(self)

    def iterload(self):
        def il_recursive(md, base):
            if hasattr(md, 'items'):
                for k, v in md.items():
                    yield from il_recursive(v, f"{base}.{k}")
            elif isinstance(md, list):
                for i, v in enumerate(v):
                    yield from il_recursive(v, f"{base}[{i}]")
            else:
                yield (base, md)

        for k, v in self.source.metadata.items():
            yield from il_recursive(v, k)


@VisiData.api
def open_pdr(vd, p):
    pdr = vd.importExternal("pdr")

    try:
        # vd -f pdr accepts either an actual pathname of something that's
        # readable by PDR, in which case everything in that file is read
        # (as multiple sheets, if necessary)...
        data = pdr.open(p)
        stem = p.base_stem
        key = None

    except NotADirectoryError:
        # ... or an actual pathname of something that's readable by PDR
        # with "/sub-object-name" tacked on the end, in which case only that
        # specific sub-object is loaded.  When the user does that, the initial
        # call to pdr.open will fail with an ENOTDIR error.
        pp = p.parent
        data = pdr.open(pp)
        stem = pp.base_stem
        # There seems to be a bug in visidata.Path where the .name property
        # omits suffixes (that's supposed to be .stem).
        key = p.parts[-1]

    if data.standard == "PDS4":
        vd.fail(
            f"sorry, not implemented: "
            f"loading {stem}, whose label format is {data.standard}"
        )

    if key is None:
        return PDSMetaSheet(
            f"{stem}/metadata",
            source=data,
            _pdr_stem=stem,
        )
    else:
        SheetClass = sheet_class_for_obj(vd, stem, key, data)
        if SheetClass is None:
            vd.fail(f"{stem}/{key}: loading failed due to earlier errors")
        return SheetClass(
            f"{stem}/{key}",
            source=PDRSource(data, key),
        )
