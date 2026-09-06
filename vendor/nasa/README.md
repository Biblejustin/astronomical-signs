# NASA Eclipse Explorer source

`JSEX_program.js` and `JLEX_program.js` preserve the original NASA-hosted source bytes. Each file carries its original **GPL version 2 or later** notice. [COPYING](COPYING) reproduces that license. The enclosing repository’s MIT license does not replace these upstream notices. `eclipse_harness.cjs` is distributed under GPL version 2 or later as stated in its header.

Sources: [Solar Eclipse Explorer](https://eclipse.gsfc.nasa.gov/JSEX/JSEX-index.html), [Lunar Eclipse Explorer](https://eclipse.gsfc.nasa.gov/JLEX/JLEX-index.html). Source byte hashes and raw copies are retained in `sources/nasa/manifest.json` and `source_pins.json`.

Eclipse Predictions by Fred Espenak and Chris O’Byrne (NASA’s GSFC). Catalog and element predictions by Fred Espenak and Jean Meeus (NASA’s GSFC).

The adapter replaces browser loading/rendering hooks only. It invokes the original numerical routines. It computes duration intersections and date serialization outside those routines; tests cover both wrappers and independent published NASA references.
