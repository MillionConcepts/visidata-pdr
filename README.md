# visidata_pdr: Load tabular data into VisiData using PDR

This [VisiData][] plugin adds a loader that can load any type of tabular
data understood by the [Planetary Data Reader][PDR] (PDR).

[VisiData]: https://www.visidata.org/
[PDR]: https://github.com/MillionConcepts/pdr

## Usage

After installing the plugin, the `pdr` loader can read any data file
that `pdr.open()` would understand.  For example, suppose you have
downloaded the [Mars Global Surveyor][]’s
[Thermal Emission Spectrometer data set][] and you want to look at
the first batch of data (MY24; 1999-02-28T21):

```
$ vd -f pdr TES_COD_IR_MY24_Ls090_Ls120.xml
```

It would also work to specify the `.dat` file.  Either way, both the
data and the label must be available.

[Mars Global Surveyor]: https://atmos.nmsu.edu/data_and_services/atmospheres_data/MARS/mgs.html
[Thermal Emission Spectrometer data set]: https://atmos.nmsu.edu/data_and_services/atmospheres_data/MARS/montabone.html
