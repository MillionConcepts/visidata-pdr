"""
Load tabular data into VisiData using PDR
"""

from visidata import (
    VisiData, Column, TableSheet, TextSheet, asyncthread
)
from visidata.loaders._pandas import PandasSheet
from visidata.loaders.npy import NpySheet


def a_type(thing):
    """
    Return the name of the type of 'thing', with the correct
    English indefinite article prepended and some of Python's
    cryptic abbreviations expanded, e.g. 'a string', 'an integer'.

    If 'thing' is already a type object, uses the name of 'thing'
    itself, not the name of type(thing) (which would always be "type").
    """
    if not isinstance(thing, type):
        thing = type(thing)
    name = thing.__name__

    # None is unique and therefore doesn't take any articles at all.
    if name in ("None", "NoneType"):
        return "None"

    name = ({
        "bool":    "boolean",
        "dict":    "dictionary",
        "float":   "real number",
        "int":     "integer",
        "ndarray": "numpy array",
        "str":     "string",
    }).get(name, name)

    # Technically, "an" should be used if the word begins with a vowel
    # *sound*, whether or not it begins with a vowel *letter*.
    # However, determining this accurately is difficult: to give just
    # one example, it should be "a numpy array" but "an ndarray".
    # Approximating based on the usual vowel letters is Good Enough For Now.
    # (The rule is also accent-dependent, but that almost exclusively affects
    # words beginning with H, and I can't think of any that would come up.)
    return ("an " if name[0] in "aeiouAEIOU" else "a ") + name


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
        if not hasattr(self, "_lines"):
            lines = self.source.get()
            if isinstance(lines, str):
                lines = lines.splitlines()
            elif isinstance(lines, list):
                if not all(isinstance(l, str) for l in lines):
                    self.vd.fail("LazyTextSheet: source is a list but"
                                 " some of its items are not strings")
            else:
                self.vd.fail(f"LazyTextSheet: source is {a_type(lines)}"
                             " (expected a string or list of strings)")
            self._lines = lines

        yield from self.readlines(self._lines)


class LazyNpySheet(NpySheet):
    def iterload(self):
        if not hasattr(self, "npy"):
            np = self.vd.importExternal("numpy")
            npy = self.source.get()
            if not isinstance(npy, np.ndarray):
                self.vd.fail(f"LazyNpySheet: source is {a_type(npy)}"
                             " (expected a numpy array)")
            self.npy = npy

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
            dtype = dtype.dtype
        return super().dtype_to_type(dtype)

    @asyncthread
    def reload(self):
        if not hasattr(self, '_pdr_source'):
            pd = self.vd.importExternal("pandas")
            df = self.source.get()
            if not isinstance(df, pd.DataFrame):
                self.vd.fail(f"LazyPandasSheet: source is {a_type(df)}"
                             " (expected a DataFrame)")

            self._pdr_source = self.source
            self.source = df

        # we're already in an async thread
        PandasSheet.reload.__wrapped__(self)


def sheet_class_for_obj(vd, stem, key, source):
    # note: Data.type_of() hasn't made it into an official PDR release yet
    try:
        expected_type = source.type_of(key)
    except FileNotFoundError as e:
        vd.warning(
            f"{stem}/{key}: data unavailable (need file {e.filename})"
        )
        return None
    except TypeError as e:
        vd.warning(
            f"{stem}/{key}: PDR cannot load this object ({e})"
        )
        return None
    except Exception as e:
        vd.warning(
            f"{stem}/{key}: unable to determine expected object type ({e})"
        )
        return None

    match expected_type.__name__:
        case "DataFrame":
            return LazyPandasSheet

        case "ndarray":
            return LazyNpySheet

        case "str":
            return LazyTextSheet

        case other:
            # the other possibilities should only come up for headers,
            # which we skip anyway
            vd.warning(
                f"{stem}: skipping {key} with object type {other}"
            )
            return None


def filtered_keys(source):
    # it _seems_ like we don't need to weed out "header" objects in PDS4
    is_pds4 = source.standard == "PDS4"
    return [
        key for key in sorted(source.keys())
        if key.upper() not in ("LABEL", "HEADER") and (
            is_pds4 or (
                key in source.metadata
                and "HEADER_TYPE" not in source.metadata[key]
            )
        )
    ]


class PDSMetaSheet(TableSheet):
    rowtype = "label metadata"  # rowdef: (str, any)
    columns = [
        Column("tag", getter=lambda col,row: row[0]),
        Column("value", getter=lambda col,row: row[1]),
    ]

    def beforeLoad(self):
        for key in filtered_keys(self.source):
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
            if hasattr(md, "items"):
                for k, v in md.items():
                    yield from il_recursive(v, f"{base}.{k}")
            elif isinstance(md, list):
                for i, v in enumerate(v):
                    yield from il_recursive(v, f"{base}[{i}]")
            else:
                yield (base, md)

        yield ("standard", self.source.standard)
        for k, v in self.source.metadata.items():
            yield from il_recursive(v, k)


@VisiData.api
def open_pdr(vd, p):
    pdr = vd.importExternal("pdr")
    data = pdr.open(p)
    stem = p.base_stem
    return PDSMetaSheet(
        f"{stem}/metadata",
        source=data,
        _pdr_stem=stem,
    )


@VisiData.api
def guess_pdr(vd, p):
    pdr = vd.importExternal("pdr")

    # It's easiest to just go ahead and try to open it.  PDR already
    # tries pretty hard to do minimal work at open time.
    try:
        data = pdr.open(p)
    except Exception:
        return None

    if data.standard in ("PDS3", "PDS4"):
        likelihood = 10
    elif data.standard == "FITS":
        likelihood = 7  # leave room for a dedicated FITS loader
    else:
        likelihood = 3

    # If we could pass `data` from here to the *open function*,
    # that would be worth doing, but AFAICT we can't do that.
    return {
        "filetype": "pdr",
        "_likelihood": likelihood
    }
