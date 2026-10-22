# Linux interface font

The unmodified Liberation Sans regular and bold faces provide consistent metrics
when Segoe UI is unavailable on Linux. Qt registers them once before constructing
the interface; no runtime download or system font installation is required.
Windows and macOS keep their existing font selection.

Source: Ubuntu package `fonts-liberation2` version `2.1.5-1`, upstream
<https://github.com/liberationfonts/liberation-fonts>. The complete package
copyright and SIL Open Font License 1.1 are retained in
`LIBERATION-LICENSE.txt`. Font names and outlines are unchanged.

SHA-256:

- `LiberationSans-Bold.ttf`: `ba0e0dc3f7aca5b0afbc31e800531ee43be3aa79ae35b2ef1f6470a9547765c4`
- `LiberationSans-Regular.ttf`: `8d91388f1d3604b3b8ae0e3ee2d140e50cd6122f9214514f4aca772540a4076d`
