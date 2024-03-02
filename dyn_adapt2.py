# Adaptive loudness averaging.
# Hens Zimmerman, 02-05-2023.
# Python 3.

import matplotlib.pyplot as plt
import numpy
import os
import pyloudnorm
import regex
import scipy 
import soundfile
import sys
import warnings

# Suppress pyloudnorm warning about clipping.
# Since we compute in float64, we can fix this ourselves.

warnings.simplefilter("ignore")

# What command line args did we get?

arg_count = len(sys.argv)

if arg_count < 2:
    print("python dyn_adapt.py file div:xx loudness:-xx")
    exit()

# Name of input file.

filename = sys.argv[1]

# Does this file exist at all?

if not os.path.isfile(filename):
    print(filename + " doesn't appear to exist\n")
    exit()

# Default division of file into blocks.

division = 9
seconds = True

# Default crossfade ratio into previous block.

xfade = 0.6

# Default target loudness.

final_loudness = -23.0

# Scan through optional arguments that override defaults
# div:10 div:10s loudness:-16 xfade:90 lower:12 max-up:6 max-down:6 oversample:4 limit:-2

if arg_count > 2:
    for idx in range(2, arg_count):
        arg = sys.argv[idx]

        match = regex.search(r"div:(\d+)", arg, regex.IGNORECASE)
        if match:
            division = int(match.group(1))

        match = regex.search(r"div:(\d+)s", arg, regex.IGNORECASE)
        if match:
            seconds = True

        match = regex.search(r"loudness:-(\d+)", arg, regex.IGNORECASE)
        if match:
            final_loudness = -int(match.group(1))

# Read entire file into ndarray.

audio, samplerate = soundfile.read(filename, frames=-1, dtype='float64', always_2d=True)

# Basic stats about file we got from soundfile.

samples = audio.shape[0]

# Is it a mono file or a multichannel file?

if len(audio.shape) > 1:
    channels = audio.shape[1]
    if channels > 2:
        print("Only stereo audio is currently supported")
        exit()
else:
    print("Mono files are not supported")
    exit()

# Division of file into blocks of size blocksize.
# If user supplied argument in seconds, divide into blocks of that many seconds.

if seconds:
    blocksize = division * samplerate
    division = int(samples / blocksize)
else:
    blocksize = int(samples / division)

# This leads to an integer size for the crossfade.

fadesize = int(blocksize * xfade)

# create BS.1770 meter

meter = pyloudnorm.Meter(samplerate) 

# Buffers to copy data back into.

new_audio = numpy.empty((0, channels))
sub_audio = numpy.empty((0, channels))
prev_audio = numpy.empty((0, channels))

# Geeky draw plot

x_data = numpy.arange(0, division, 1)
y_data = numpy.empty(division)

for idx in range(0, division):
    # Create this block. Last block may have padding samples.
    print("Processing block {0} of {1}".format(idx + 1, division))

    start_idx = (idx * blocksize) - fadesize
    stop_idx = start_idx + blocksize + fadesize

    # First block does not require a crossfade section at the start.

    if start_idx < 0:
        start_idx = 0

    if idx == division - 1:
        sub_audio = audio[start_idx:]
    else:
        sub_audio = audio[start_idx:stop_idx]

    # Loudness adapt this block.

    loudness = meter.integrated_loudness(sub_audio)

    print("Block loudness (LUFS): " + str(loudness))

    sub_audio = pyloudnorm.normalize.loudness(sub_audio, loudness, final_loudness)
    y_data[idx] = final_loudness - loudness

    # This might issue a warning when we are correctly out of bounds [-1.0 .. 1.0]
    # Warning is suppressed so we check and correct for the digital clipping case here.

    # Crossfade into previous block.

    if idx > 0:
        for jdx in range(0, fadesize):
            mult = jdx * (1.0 / fadesize)
            inv_mult = 1.0 - mult

            for ch in range(0, channels):
                prev_audio[jdx + blocksize - fadesize][ch] = inv_mult * prev_audio[jdx + blocksize - fadesize][ch] + mult * sub_audio[jdx][ch]

    # Remove crossfade area at the beginning of this block, but not for first block.

    if idx > 0:
        sub_audio = sub_audio[fadesize:]

        # Append previous block to new_audio.

        new_audio = numpy.append(new_audio, prev_audio, axis = 0)

    # This block becomes previous block for next iteration.

    prev_audio = sub_audio

# Out of the loop we still need to concat the last block.

new_audio = numpy.append(new_audio, prev_audio, axis = 0)

# Gain scale final buffer to requested loudness norm.

loudness = meter.integrated_loudness(new_audio)

new_audio = pyloudnorm.normalize.loudness(new_audio, loudness, final_loudness)

peak_dB = 20.0 * numpy.log10(max(abs(numpy.min(new_audio)), numpy.max(new_audio)))

print("Sample peak at " + str(peak_dB) + " dBFS")

# Remove extension from filename.

ext_length = 4

new_name = filename[:-ext_length] + '_new.wav'

soundfile.write(new_name, new_audio, samplerate, 'PCM_24')

# Stem plot
fig, ax = plt.subplots()
ax.stem(x_data, y_data)
plt.show()
