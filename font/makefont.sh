#!/bin/bash
fontfile=$1
outfile=$2

echo -n "" > $outfile

for ord in `seq 32 126`
do
	printf "\x$(printf %x $ord)" | convert \
		-background black \
		-fill white \
		-resize 8x16\! \
		-antialias \
		-font $fontfile \
		-pointsize 12 \
		-define quantum:format=unsigned \
		-depth 8 \
		label:\@- \
		rgba:- >> $outfile
done