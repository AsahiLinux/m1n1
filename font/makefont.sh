#!/bin/bash
width=$1
height=$2
size=$3
fontfile=$4
outfile=$5

echo -n "" > $outfile

for ord in `seq 32 126`
do
	printf "\x$(printf %x $ord)" | convert \
		-background black \
		-fill white \
		-resize ${width}x${height}\! \
		-antialias \
		-font $fontfile \
		-pointsize $size \
		-define quantum:format=unsigned \
		-depth 8 \
		label:\@- \
		rgba:- >> $outfile
done
