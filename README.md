# dynadapt
Dynamic loudness adaptation to even out human errors in mixing
It uses BS.1770 loudness specification. E.g.:

python dynadapt2.py ~/Desktop/your_wav_file.wav div:12s loudness:-23

TODO: Detect boundaries of blocks with different loudness. In its current incarnation, this script just evens out human tendencies in mixing.
