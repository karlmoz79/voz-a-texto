import unittest

from voz_a_texto.desktop.audio_capture import RecordingBuffer


class RecordingBufferTestCase(unittest.TestCase):
    def test_buffer_marks_recording_as_too_long_when_limit_is_exceeded(self):
        buffer = RecordingBuffer(max_audio_sec=1, sample_rate=4)

        buffer.append(b"12345678")
        buffer.append(b"90")

        self.assertEqual(buffer.consume(), b"12345678")
        self.assertTrue(buffer.recording_too_long)


if __name__ == "__main__":
    unittest.main()
