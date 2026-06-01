"""
Load tabular data into VisiData using PDR
"""

from visidata import VisiData, TextSheet
from visidata.loaders._pandas import PandasSheet
from visidata.loaders.xml import XmlSheet


class PatchedPandasSheet(PandasSheet):
    """
    Patch PandasSheet with a workaround for
    https://github.com/saulpw/visidata/issues/2960
    whose fix is not yet released
    """
    def dtype_to_type(self, dtype):
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


def push_data_sheets(vd, stem, blob):
    pd = vd.importExternal("pandas")

    for objname_raw in sorted(blob.keys()):
        objname = objname_raw.lower()
        if objname == "label":
            continue
        obj = blob[objname_raw]
        if isinstance(obj, pd.DataFrame):
            vd.push(PatchedPandasSheet(f"{stem}/{objname}", source=obj))
        else:
            vd.warning(
                f"sorry, not implemented: "
                f"loading {objname}, which is {a_type(obj)}"
            )


class PDS3LabelSheet(TextSheet):
    def beforeLoad(self):
        push_data_sheets(self.vd, self.pdr_stem, self.pdr_data)


class PDS4LabelSheet(XmlSheet):
    def beforeLoad(self):
        push_data_sheets(self.vd, self.pdr_stem, self.pdr_data)


@VisiData.api
def open_pdr(vd, p):
    pdr = vd.importExternal("pdr")

    data = pdr.open(p)
    if hasattr(data, "label"):
        label = data.label
    elif hasattr(data, "LABEL"):
        label = data.LABEL
    else:
        vd.fail(f"{p.base_stem} has no label??? (keys: {' '.join(sorted(data.keys()))})")

    if data.standard == "PDS3":
        if not isinstance(label, str):
            vd.fail(f"PDS label is v3 but label object is {a_type(label)}??? (expected a string)")
        return PDS3LabelSheet(
            f'{p.base_stem}/LABEL',
            source=label.splitlines(),
            pdr_data=data,
            pdr_stem=p.base_stem,
        )

    elif data.standard == "PDS4":
        if not isinstance(label, pdr.pds4_tools.reader.label_objects.Label):
            vd.fail(f"PDS label is v4 but label object is {a_type(label)}??? (expected a pds4_tools Label)")
        return PDS4LabelSheet(
            f'{p.base_stem}/LABEL',
            source=label,
            pdr_data=data,
            pdr_stem=p.base_stem,
        )

    else:
        vd.fail(
            f"sorry, not implemented: "
            f"loading {p.base_stem}, whose label format is {data.standard}"
        )
