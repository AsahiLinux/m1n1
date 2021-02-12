#!/bin/bash
width=$1
height=$2
size=$3
fontfile=$4
outfile=$5
shift 5

(
for ord in $(seq 32 126); do
    printf "\\x$(printf %x $ord)\\n"
done
) | convert \
    -page ${width}x$((height*95)) \
    -background black \
    -fill white \
    -antialias \
    -font $fontfile \
    -density 72 \
    -gravity north \
    -pointsize $size \
    $* \
    -define quantum:format=unsigned \
    -depth 8 \
    label:\@- \
    -crop ${width}x$((height*95)) \
    gray:$outfile
