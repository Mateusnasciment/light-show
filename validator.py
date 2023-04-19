# Requires Python 3.7+
import dataclasses
import struct
import sys
import argparse
import datetime

MEMORY_LIMIT = 3500  # The maximum memory usage allowed for a Light Show

class ValidationError(Exception):
    pass

@dataclasses.dataclass
class ValidationResults:
    frame_count: int
    step_time: int
    duration_s: int
    memory_usage: float

def validate(file):
    """Calculates the memory usage of the provided .fseq file"""
    # Read file header information
    magic = file.read(4)  # The file magic number
    start, minor, major = struct.unpack("<HBB", file.read(4))  # The offset of the light show data, and the file format version
    file.seek(10)
    channel_count, frame_count, step_time = struct.unpack("<IIB", file.read(9))  # The number of channels, frames, and step time in the light show
    file.seek(20)
    compression_type, = struct.unpack("<B", file.read(1))  # The compression type used in the file

    # Validate the file header information
    if (magic != b'PSEQ') or (start < 24) or (frame_count < 1) or (step_time < 15):
        raise ValidationError("Unknown file format, expected FSEQ v2.0")
    if channel_count != 48:
        raise ValidationError(f"Expected 48 channels, got {channel_count}")
    if compression_type != 0:
        raise ValidationError("Expected file format to be V2 Uncompressed")
    duration_s = (frame_count * step_time / 1000)
    if duration_s > 5*60:
        raise ValidationError(f"Expected total duration to be less than 5 minutes, got {datetime.timedelta(seconds=duration_s)}")
    if ((minor != 0) and (minor != 2)) or (major != 2):
        print("")
        print(f"WARNING: FSEQ version is {major}.{minor}. Only version 2.0 and 2.2 have been validated.")
        print(f"If the car fails to read this file, download and older version of XLights at https://github.com/smeighan/xLights/releases")
        print(f"Please report this message at https://github.com/teslamotors/light-show/issues")
        print("")

    # Calculate the memory usage of the light show data
    file.seek(start)

    prev_light = None
    prev_ramp = None
    prev_closure_1 = None
    prev_closure_2 = None
    count = 0

    for frame_i in range(frame_count):
        lights = file.read(30)  # The light states for the current frame
        closures = file.read(16)  # The closure states for the current frame
        file.seek(2, 1)  # Skip over reserved bytes

        # Determine the current state of the lights, ramps, and closures
        light_state = [(b > 127) for b in lights]
        ramp_state = [min((((255 - b) if (b > 127) else (b)) // 13 + 1) // 2, 3) for b in lights[:14]]
        closure_state = [((b // 32 + 1) // 2) for b in closures]

        # Check if the state of the lights, ramps, or closures has changed
        if light_state != prev_light:
            prev_light = light_state
            count += 1
        if ramp_state != prev_ramp:
            prev_ramp = ramp_state
            count += 1
        if closure_state[:10] != prev_closure_1:
            prev_closure_1 = closure_state[:10]
            count += 1
        if closure_state[10:] != prev_closure_2:
            prev_closure_2 = closure_state[10:]
            count += 1
    return ValidationResults(frame_count, step_time, duration_s, count / MEMORY_LIMIT)

if __name__ == "__main__":
    # Expected usage: python3 validator.py lightshow.fseq
    parser = argparse.ArgumentParser(description="Validate .fseq file for Tesla Light Show use")
    parser.add_argument("file")
    args = parser.parse_args()

    with open(args.file, "rb") as file:
        try:
            results = validate(file)
        except ValidationError as e:
            print(e)
            sys.exit(1)

    print(f"Found {results.frame_count} frames, step time of {results.step_time} ms for a total duration of {datetime.timedelta(seconds=results.duration_s)}.")
    print(f"Used {results.memory_usage*100:.2f}% of the available memory")
    if results.memory_usage > 1:
        sys.exit(1)
