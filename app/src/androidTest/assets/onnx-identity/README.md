# Owned native identity fixture

`identity.onnx` is a locally authored 145-byte graph, not an upstream model or model weight:

- IR version 8, standard ONNX opset 13.
- Single `Identity` node `X -> Y`, FLOAT input/output shape `[1, 4]`.
- No attributes, weights, external files, custom operators, network, or model downloads.
- SHA256: `bc17685c0865d15d61b6c76095b13f4bac4913448c2ec1767c25905a008ef16a`.

Reproduce from this directory with `python generate_identity.py`. It uses only Python's standard library and explicitly encodes protobuf varint/length-delimited fields. No `onnx`, protobuf package, protoc, pip, or native inference is involved in generation.

Field numbers and FLOAT data type follow the adjacent complete, unmodified official `onnx.proto`, from ONNX v1.17.0 commit `b8baa8446686496da4cc8fda09f2b6fe65c2a02c`:

https://raw.githubusercontent.com/onnx/onnx/b8baa8446686496da4cc8fda09f2b6fe65c2a02c/onnx/onnx.proto

Schema SHA256: `2881fcc940635b6a34b7c95e5089b2faa89c3d6e382c1da1706e88c7f32452bc`. Its Apache-2.0 header is retained, with the full official license in `ONNX-LICENSE`. Exact source URLs, commit and hashes are in `provenance.json`; `SHA256SUMS` covers the retained inputs and generated model.

`dev.clickn.translate.ocr.OnnxRuntimeIdentityIntegrationTest` loads this test-APK asset and checks actual ONNX Runtime version 1.21.1, model/session metadata, native `[1, -2.5, 0, 42] -> [1, -2.5, 0, 42]` inference at `[1,4]`, and tensor/result ownership. Inter/intra-op threads are both 1. Input tensor, result/output, session and options are closed; the global shared environment is not closed.

The fixture/test is intended for the minified validation APK as well as debug. Source generation alone is not a device result. A passing native identity test does not establish full Paddle/Manga OCR accuracy, performance, or model compatibility.
