# visidata_pdr: Load tabular data into VisiData using PDR

This [VisiData][] plugin adds a loader that can load any type of tabular
data understood by the [Planetary Data Reader][PDR] (PDR).

[VisiData]: https://www.visidata.org/
[PDR]: https://github.com/MillionConcepts/pdr

## Installation

It is necessary to install PDR and its dependencies as well as the
plugin’s own code.  The easiest way to do this is to install the
plugin package, `visidata_pdr`, using `pip`, into the Python runtime
context where VisiData looks for its libraries.  For example, if
VisiData is installed via `pipx`,

```sh
pipx inject visidata visidata_pdr
```

will do the job.  If you have installed VisiData some other way, you
will need to use different commands (please suggest additional
examples for this section).

Copying `visidata_pdr.py` into VisiData’s local plugins directory is
not recommended, as this will not install PDR.

## Usage

After installing the plugin and its dependencies, the `pdr` loader can
read any data file that `pdr.open()` would understand.  For example,
suppose you have downloaded the [Mars Global Surveyor][]’s [Thermal
Emission Spectrometer data set][] and you want to look at the first
batch of data (MY24; 1999-02-28T21):

```sh
vd -f pdr TES_COD_IR_MY24_Ls090_Ls120.xml
```

It would also work to specify the `.dat` file.  Either way, both the
data and the label must be available.

The plugin does provide a “guess” function that tries to identify
files that `pdr.open` would understand, but its guesses are treated as
lower priority than all of the built-in loaders for specific file
formats, so, for example, omitting the `-f pdr` from the above command
will cause `TES_COD_IR_MY24_Ls090_Ls120.xml` to be loaded as a generic
XML file, not a PDS4 label.  (We hope to improve this in the future.)

The `pdr` loader will create one sheet for the label itself, and
another sheet for each data object described by the label.  The
sheet for the label itself will be selected initially; use standard
VisiData sheet navigation to reach other sheets.  Data sheets
are not loaded until the first time they are selected.  Images will
be presented as 2D matrices.

We are actively looking for feedback on the user experience of this
plugin.  Please file all commentary, suggestions, etc. as GitHub
issues: https://github.com/MillionConcepts/visidata-pdr/issues

[Mars Global Surveyor]: https://atmos.nmsu.edu/data_and_services/atmospheres_data/MARS/mgs.html
[Thermal Emission Spectrometer data set]: https://atmos.nmsu.edu/data_and_services/atmospheres_data/MARS/montabone.html
