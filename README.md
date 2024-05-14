# dynadapt
Dynamic loudness adaptation to even out human errors in mixing
It uses BS.1770 loudness specification. 

usage: dyn_adapt4.py [-h] [-d DIVISION] [-l LOUDNESS] [-m MAXGAIN] [-p] [-q] [-x CROSSFADE] input

Adaptive loudness averaging

positional arguments:
  input                 stereo input file (*.wav)

options:
  -h, --help            show this help message and exit
  -d DIVISION, --division DIVISION
                        block division in EVEN seconds
  -l LOUDNESS, --loudness LOUDNESS
                        target loudness in LUFS
  -m MAXGAIN, --maxgain MAXGAIN
                        maximum positive or negative gain
  -p, --nophase2        skip phase 2
  -q, --quiet           suppress output text
  -x CROSSFADE, --crossfade CROSSFADE
                        block crossfade value between 0 and 1

This work is licensed under CC BY-NC-SA 4.0
