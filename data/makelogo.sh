#!/usr/bin/env sh
convert bootlogo_48.png -background black -flatten -depth 8 rgba:bootlogo_48.bin
convert bootlogo_128.png -background black -flatten -depth 8 rgba:bootlogo_128.bin
convert bootlogo_256.png -background black -flatten -depth 8 rgba:bootlogo_256.bin
