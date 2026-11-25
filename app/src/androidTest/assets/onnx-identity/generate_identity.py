"""Owned deterministic Identity graph. Python standard library only; no onnx/protobuf package.

Field numbers follow the adjacent unmodified official onnx.proto, pinned in provenance.json.
This writes a fixture; only Android ONNX Runtime execution establishes its native validity.
"""
from pathlib import Path
import hashlib
import json


def varint(value):
    assert isinstance(value, int) and value >= 0
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def integer(field, value):
    return varint(field << 3) + varint(value)


def message(field, value):
    if isinstance(value, str):
        value = value.encode('utf-8')
    return varint((field << 3) | 2) + varint(len(value)) + value


def value_info(name):
    # Dimension.dim_value=1; TensorShapeProto.dim=1, repeated dimensions [1,4].
    shape = message(1, integer(1, 1)) + message(1, integer(1, 4))
    # TypeProto.Tensor.elem_type=1: TensorProto.FLOAT=1; Tensor.shape=2.
    tensor = integer(1, 1) + message(2, shape)
    # ValueInfoProto.name=1, type=2; TypeProto.tensor_type=1.
    return message(1, name) + message(2, message(1, tensor))


# NodeProto.input=1, output=2, name=3, op_type=4. No attributes/weights/external data.
node = message(1, 'X') + message(2, 'Y') + message(3, 'owned_identity') + message(4, 'Identity')
# GraphProto.node=1, name=2, input=11, output=12.
graph = (message(1, node) + message(2, 'clickn_owned_identity')
         + message(11, value_info('X')) + message(12, value_info('Y')))
# OperatorSetIdProto.domain=1 (empty means standard ONNX), version=2.
opset = message(1, '') + integer(2, 13)
# ModelProto.ir_version=1, producer_name=2, producer_version=3, model_version=5,
# graph=7, opset_import=8. IR8/opset13 are deliberately conservative.
model = (integer(1, 8) + message(2, 'ClicknTranslate-owned-fixture') + message(3, '1')
         + integer(5, 1) + message(7, graph) + message(8, opset))

if __name__ == '__main__':
    output = Path(__file__).with_name('identity.onnx')
    output.write_bytes(model)
    print(json.dumps({'file': output.name, 'bytes': len(model),
                      'sha256': hashlib.sha256(model).hexdigest(),
                      'sha512': hashlib.sha512(model).hexdigest()}, indent=2))
