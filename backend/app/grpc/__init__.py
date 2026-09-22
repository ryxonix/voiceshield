"""
VoiceShield AI — gRPC Service Layer (A1)

Generatv stubs live here (`voiceshield_pb2.py`, `voiceshield_pb2_grpc.py`) and
are the external integration contract for SIH26104 ("REST/gRPC APIs and SDKs
for integration with core banking systems, contact center platforms,
enterprise communication tools, and telecom networks"). The servicer in
`app.grpc.servicer` re-implements the same 10-RPC surface exposed over REST in
`app.main`, reusing the exact scoring pipeline so results are byte-identical.
"""
