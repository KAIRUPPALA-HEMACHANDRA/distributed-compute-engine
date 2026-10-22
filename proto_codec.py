import json
from typing import Dict, Any
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

def _create_compute_proto_class():
    """Dynamically builds the Google Protobuf binary class matching compute.proto."""
    pool = descriptor_pool.DescriptorPool()
    file_proto = descriptor_pb2.FileDescriptorProto()
    file_proto.name = "compute.proto"
    file_proto.package = "compute"
    file_proto.syntax = "proto3"

    msg = file_proto.message_type.add()
    msg.name = "ComputePayload"

    fields = [
        ("id", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
        ("op", 2, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
        ("args_json", 3, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
        ("auth_token", 4, descriptor_pb2.FieldDescriptorProto.TYPE_STRING),
        ("timeout", 5, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE),
    ]

    for name, number, field_type in fields:
        field = msg.field.add()
        field.name = name
        field.number = number
        field.label = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
        field.type = field_type

    file_desc = pool.AddSerializedFile(file_proto.SerializeToString())
    return message_factory.GetMessageClass(file_desc.message_types_by_name["ComputePayload"])

ComputePayloadProto = _create_compute_proto_class()

def encode_request_to_protobuf(payload: Dict[str, Any]) -> bytes:
    """Compresses a standard Python request dictionary into raw Protobuf binary bytes."""
    meta = payload.get("meta", {})
    proto_msg = ComputePayloadProto(
        id=str(payload.get("id", "")),
        op=str(payload.get("op", "")),
        args_json=json.dumps(payload.get("args", [])),
        auth_token=str(meta.get("auth_token", "")),
        timeout=float(meta.get("timeout", 5.0)),
    )
    return proto_msg.SerializeToString()

def decode_protobuf_to_request(raw_bytes: bytes) -> Dict[str, Any]:
    """Unpacks raw Protobuf binary bytes back into the dictionary format server.py expects."""
    proto_msg = ComputePayloadProto()
    proto_msg.ParseFromString(raw_bytes)
    return {
        "id": proto_msg.id,
        "op": proto_msg.op,
        "args": json.loads(proto_msg.args_json) if proto_msg.args_json else [],
        "meta": {
            "auth_token": proto_msg.auth_token,
            "timeout": proto_msg.timeout if proto_msg.timeout > 0 else 5.0,
        },
    }