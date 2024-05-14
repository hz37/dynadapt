# Adaptive loudness averaging.
# Hens Zimmerman, 14-05-2024.
# Python 3.
#
# Input file is a stereo wav file that preferably is already mixed
# around the loudness goal, liberally limited (-3 dBTP or something)
# and phase rotated afterwards.

import argparse
import numpy
import os
import pyloudnorm
import scipy 
import soundfile
import sys
import warnings

# Suppress pyloudnorm warning about clipping.

warnings.simplefilter("ignore")

default_loudness = -16
default_crossfade = 0.6

# What command line args did we get?

parser = argparse.ArgumentParser(description='Adaptive loudness averaging', epilog="This work is licensed under CC BY-NC-SA 4.0")
parser.add_argument('input', type=str, help='stereo input file (*.wav)')
parser.add_argument('-d', '--division', type=int, help='block division in EVEN seconds', default=8)
parser.add_argument('-l', '--loudness', type=int, help='target loudness in LUFS', default=default_loudness)
parser.add_argument('-m', '--maxgain', type=float, help='maximum positive or negative gain', default=2.0)
parser.add_argument('-p', '--nophase2', help='skip phase 2', action="store_true", default=0)
parser.add_argument('-q', '--quiet', help='suppress output text', action="store_true", default=0)
parser.add_argument('-x', '--crossfade', type=float, help='block crossfade value between 0 and 1', default=default_crossfade)

args = parser.parse_args()

# Name of input file.

filename = args.input

# Does this file exist at all?

if not os.path.isfile(filename):
    print(filename + " doesn't appear to exist\n")
    exit()

# Default division in seconds of file into blocks.
# 6 seconds appears to be useful for program material.

division = args.division

# division must be an even number!

if division % 2:
    division += 1

# Default crossfade ratio into previous block.

xfade = args.crossfade

# xfade must be between 0 and 1

if xfade <= 0 or xfade >= 1:
    xfade = default_crossfade

# Default target loudness. Override with cmd line parm.

final_loudness = args.loudness

# final_loudness must be negative

if final_loudness >= 0:
    final_loudness = default_loudness

# maxgain is a positive value.

max_gain = abs(args.maxgain)

if not args.quiet:
    print("Loudness goal: " + str(final_loudness) + " LUFS") 
    print("Division: " + str(division) + " seconds")
    print("Crossfade: " + str(xfade))
    print("Max gain: " + str(max_gain) + " dB")

# Read entire file into 64 bit floating point ndarray.
# All samplerates are supported.

audio, samplerate = soundfile.read(filename, frames=-1, dtype='float64', always_2d=True)

if not args.quiet:
    print("Sample rate: " + str(samplerate) + " Hz")

# Is it a mono file or a multichannel file? We can't handle those.

if len(audio.shape) > 1:
    channels = audio.shape[1]
    if channels > 2:
        print("Only stereo audio is currently supported")
        exit()
else:
    print("Mono files are not supported")
    exit()

# Division of file into blocks of size blocksize (seconds).

samples = audio.shape[0]
blocksize = division * samplerate

# This leads to an integer size for the crossfade.

fadesize = int(blocksize * xfade)

# create BS.1770 meter

meter = pyloudnorm.Meter(samplerate) 

# Buffers to copy data back into.

new_audio = numpy.empty((0, channels))
sub_audio = numpy.empty((0, channels))
prev_audio = numpy.empty((0, channels))
shift_audio = numpy.empty((0, channels))
new_shift_audio = numpy.empty((0, channels))

# ---------------------
# * * * PHASE ONE * * * 
# ---------------------

if not args.quiet and not args.nophase2:
    print("Phase 1")

block_count = int(samples / blocksize)

for idx in range(0, block_count):
    # Create this block. Last block may have padding samples.
    if not args.quiet:
        print("Processing block {0} of {1}".format(idx + 1, block_count))

    start_idx = (idx * blocksize) - fadesize
    stop_idx = start_idx + blocksize + fadesize

    # First block does not require a crossfade section at the start.

    if start_idx < 0:
        start_idx = 0

    if idx == block_count - 1:
        sub_audio = audio[start_idx:]
    else:
        sub_audio = audio[start_idx:stop_idx]

    # Loudness adapt this block.

    loudness = meter.integrated_loudness(sub_audio)

    if not args.quiet:
        print("Block loudness (LUFS): " + str(loudness))

    # Limit the amount of gain we use.

    if abs(final_loudness - loudness) > max_gain:
        if loudness > final_loudness:
            loudness = final_loudness + max_gain
        else:
            loudness = final_loudness - max_gain

    sub_audio = pyloudnorm.normalize.loudness(sub_audio, loudness, final_loudness)

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

if not args.nophase2:

    # ---------------------
    # * * * PHASE TWO * * * 
    # ---------------------

    # Shift division by half for an even smoother loudness curve!

    if not args.quiet:
        print("Phase 2, shifting by half blocksize")

    # Chop off half blocksize from the start. A bit wasteful, but we have enough RAM mem.

    shift_audio = new_audio[int(blocksize/2):]

    shift_samples = shift_audio.shape[0]
    block_count = int(shift_samples / blocksize)

    for idx in range(0, block_count):
        # Create this block. Last block may have padding samples.
        if not args.quiet:
            print("--Processing block {0} of {1}".format(idx + 1, block_count))

        start_idx = (idx * blocksize) - fadesize
        stop_idx = start_idx + blocksize + fadesize

        # First block does not require a crossfade section at the start.

        if start_idx < 0:
            start_idx = 0

        if idx == block_count - 1:
            sub_audio = shift_audio[start_idx:]
        else:
            sub_audio = shift_audio[start_idx:stop_idx]

        # Loudness adapt this block.

        loudness = meter.integrated_loudness(sub_audio)

        if not args.quiet:
            print("--Block loudness (LUFS): " + str(loudness))

        # Limit the amount of gain we use.

        if abs(final_loudness - loudness) > max_gain:
            if loudness > final_loudness:
                loudness = final_loudness + max_gain
            else:
                loudness = final_loudness - max_gain

        sub_audio = pyloudnorm.normalize.loudness(sub_audio, loudness, final_loudness)

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

            new_shift_audio = numpy.append(new_shift_audio, prev_audio, axis = 0)

        # This block becomes previous block for next iteration.

        prev_audio = sub_audio

    # Out of the loop we still need to concat the last block.

    new_shift_audio = numpy.append(new_shift_audio, prev_audio, axis = 0)

    # Out of phase 2, cleaning up.

    # Prepend back the first half blocksize we omitted in phase 2.

    new_audio = numpy.append(new_audio[:int(blocksize/2)], new_shift_audio, axis = 0)

# END OF PHASE 2

# Gain scale final buffer to requested loudness norm.

loudness = meter.integrated_loudness(new_audio)

new_audio = pyloudnorm.normalize.loudness(new_audio, loudness, final_loudness)

if not args.quiet:
    peak_dB = 20.0 * numpy.log10(max(abs(numpy.min(new_audio)), numpy.max(new_audio)))

    print("Sample peak at " + str(round(peak_dB, 3)) + " dBFS")

# Remove extension from filename.

ext_length = 4

new_name = filename[:-ext_length] + '_new.wav'

soundfile.write(new_name, new_audio, samplerate, 'PCM_24')

if not args.quiet:
    print("Done!")
