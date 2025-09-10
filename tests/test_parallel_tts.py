import asyncio
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.backend.services.parallel_tts import ParallelTTSProcessor


class DummyGrpcTTS:
    async def synthesize_chunk_fast(self, text: str) -> bytes:
        return text.encode()


class RecordingARIClient:
    def __init__(self):
        self.played = []

    async def play_audio_data(self, channel_id: str, audio_data: bytes) -> bool:
        self.played.append(audio_data.decode())
        return True


def test_chunks_play_in_order():
    async def run():
        grpc = DummyGrpcTTS()
        ari = RecordingARIClient()
        processor = ParallelTTSProcessor(grpc, ari)
        channel = "test_channel"

        await processor.process_chunk_immediate(
            channel, {"chunk_number": 0, "text": "first", "is_first": True}
        )
        await processor.process_chunk_immediate(channel, {"chunk_number": 1, "text": "second"})

        await asyncio.gather(*processor.tts_tasks[channel])

        while processor.playback_busy[channel] or processor.playback_queues[channel]:
            await asyncio.sleep(0.01)

        assert ari.played == ["first", "second"]

    asyncio.run(run())
