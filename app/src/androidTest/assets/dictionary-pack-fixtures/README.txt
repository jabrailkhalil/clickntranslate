Locally authored dictionary import fixtures, CC0-1.0.
Copied byte-for-byte from .tmp/parity183/fixtures; no upstream ECDICT corpus.
Schema 1 real SQLite; English headwords and Arabic/mixed-script definitions.
These inputs and expected values are not device test results.

owned-english-arabic-v1.bin: 40960 bytes
SHA256 e152df057eb738724101640cbbc46d99899d7ce3de87c8142da269ad0e21ba16
pack_id ecdict; data_version owned-parity183-v1; 4 entries, 5 forms, 5 senses.

owned-english-arabic-v2.db: 40960 bytes
SHA256 9f6a2f42c4cb6e850b7061f8d5c71720a65a1c92434bd0b0416222f4725d50fb
Same schema/entries; first definition changed to reviewed v2.

wrong-pack-id.bin: 40960 bytes
SHA256 8e1abfc64ca9a02acf0ac5c31f2c2e35f8e0f1822e874f24bfa628ab5f865f74
Otherwise valid SQLite with pack_id jmdict; must reject an ECDICT import.

truncated-pack.bin: 1536 bytes
SHA256 f3e1426cc4294b19a46341026d88ef4421505aedee943d7e6c99352950377286
First 1536 bytes of v1; must reject and preserve the installed pack.
